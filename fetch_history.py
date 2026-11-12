"""Daten fuer Ruecktest und Ausbruchs-Scanner laden (fortsetzbar, ueberspringt Vorhandenes).

python3 fetch_history.py prices   5 Jahre Tageskurse (OHLCV) je Aktie -> data/hist/SYM.csv
python3 fetch_history.py update   vorhandene Kurshistorie um die neuen Tage ergaenzen (woechentlich)
python3 fetch_history.py sec      Ticker-Zuordnung + Termine der Quartalsmeldungen (8-K 2.02) -> data/sec_meta.json
"""
import os, sys, json, datetime, concurrent.futures as cf
from common import DATA, get_json, num, cache_save
import screener as s

HIST = os.path.join(DATA, "hist")
os.makedirs(HIST, exist_ok=True)
START = "2021-11-01"
MCAP_FLOOR = 1e8


def bt_universe():
    """Zugelassene Aktien ab 100 Mio. $ Boersenwert (ohne Obergrenze, um Gewinner nicht auszusortieren)."""
    p = os.path.join(DATA, "nasdaq_universe.json")
    if not os.path.exists(p):                      # frischer Container: Aktienliste erst laden
        s.load_universe()
    rows = json.load(open(p))["data"]["rows"]
    out = {}
    for r in rows:
        sym, mc = r["symbol"].strip(), num(r.get("marketCap")) or 0
        if mc >= MCAP_FLOOR and "/" not in sym and "^" not in sym and r.get("sector") not in s.EXCL_SECTORS \
                and not s.EXCL_NAME.search(r["name"]):
            out[sym] = {"name": r["name"], "mcap": mc, "sector": r.get("sector") or ""}
    return out


def _rows(sym, start):
    j = get_json(f"https://api.nasdaq.com/api/quote/{sym}/historical",
                 params={"assetclass": "stocks", "fromdate": start, "todate": datetime.date.today().isoformat(),
                         "limit": 2500}, tries=3, timeout=60)
    try:
        rows = j["data"]["tradesTable"]["rows"] or []
    except (TypeError, KeyError):
        rows = []
    lines = []
    for r in reversed(rows):
        v = [num(r.get(k)) for k in ("open", "high", "low", "close", "volume")]
        if v[3]:
            m, d, y = r["date"].split("/")
            lines.append(f"{y}-{m}-{d}," + ",".join("" if x is None else repr(x) for x in v))
    return lines


def _write(sym, lines):
    p = os.path.join(HIST, f"{sym}.csv")
    with open(p + ".tmp", "w") as f:
        f.write("date,open,high,low,close,volume\n" + "\n".join(lines) + "\n")
    os.replace(p + ".tmp", p)


def fetch_prices(sym, start=START):
    if os.path.exists(os.path.join(HIST, f"{sym}.csv")):
        return True
    lines = _rows(sym, start)
    _write(sym, lines)
    return bool(lines)


def update_prices(sym, ref):
    """Haengt neue Tage an die vorhandene Historie an; ref = juengster Handelstag."""
    p = os.path.join(HIST, f"{sym}.csv")
    if not os.path.exists(p):
        return fetch_prices(sym)
    old = [l for l in open(p).read().strip().split("\n")[1:] if l]
    if old and old[-1][:10] >= ref:
        return True
    start = (datetime.date.fromisoformat(old[-1][:10]) - datetime.timedelta(days=7)).isoformat() if old else START
    new = _rows(sym, start)
    if new:
        _write(sym, [l for l in old if l[:10] < new[0][:10]] + new)
    return bool(new)


def run_update():
    ref = _rows("AAPL", (datetime.date.today() - datetime.timedelta(days=10)).isoformat())[-1][:10]
    syms = sorted(bt_universe())
    print(f"Kurs-Update bis {ref} fuer {len(syms)} Titel", flush=True)
    with cf.ThreadPoolExecutor(8) as ex:
        for i, _ in enumerate(ex.map(lambda x: update_prices(x, ref), syms), 1):
            if i % 400 == 0:
                print(f"  Update {i}/{len(syms)}", flush=True)
    print("Kurs-Update fertig", flush=True)


def run_prices():
    syms = sorted(bt_universe())
    todo = [x for x in syms if not os.path.exists(os.path.join(HIST, f"{x}.csv"))]
    print(f"Kurshistorie: {len(todo)} von {len(syms)} zu laden", flush=True)
    with cf.ThreadPoolExecutor(8) as ex:
        for i, _ in enumerate(ex.map(fetch_prices, todo), 1):
            if i % 200 == 0:
                print(f"  Kurse {i}/{len(todo)}", flush=True)
    print("Kurshistorie fertig", flush=True)


def sec_one(c):
    """Ticker, Branche und Termine der Quartalsmeldungen (8-K mit Punkt 2.02) einer Firma."""
    j = get_json(f"https://data.sec.gov/submissions/CIK{int(c):010d}.json")
    if not j:
        return None
    rec = (j.get("filings") or {}).get("recent") or {}
    forms, items, dates = rec.get("form", []), rec.get("items", []), rec.get("filingDate", [])
    earn = sorted({dates[i] for i in range(len(forms)) if forms[i] in ("8-K", "8-K/A") and "2.02" in (items[i] or "")
                   and dates[i] >= "2021-06-01"})
    return {"tickers": j.get("tickers") or [], "sic": j.get("sicDescription") or "", "name": j.get("name") or "",
            "earnings": earn}


def run_sec():
    ciks = set()
    for period in ("CY2024", "CY2025"):
        for t in s.REV_TAGS:
            ciks |= {d["cik"] for d in s.frame(t, period) if d["val"] and d["val"] >= 1e7}
    p = os.path.join(DATA, "sec_meta.json")
    meta = json.load(open(p)) if os.path.exists(p) else {}
    todo = sorted(c for c in ciks if str(c) not in meta)
    print(f"SEC-Stammdaten: {len(todo)} von {len(ciks)} zu laden", flush=True)

    with cf.ThreadPoolExecutor(4) as ex:
        for i, (c, m) in enumerate(zip(todo, ex.map(sec_one, todo)), 1):
            if m:
                meta[str(c)] = m
            if i % 300 == 0:
                cache_save("sec_meta.json", meta)
                print(f"  SEC {i}/{len(todo)}", flush=True)
    cache_save("sec_meta.json", meta)
    print("SEC-Stammdaten fertig", flush=True)


if __name__ == "__main__":
    {"prices": run_prices, "sec": run_sec, "update": run_update}[sys.argv[1]]()
