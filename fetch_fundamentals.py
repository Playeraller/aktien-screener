"""Bilanzdaten mit Meldedatum je Firma laden (SEC companyfacts) -> data/facts/CIK.json, fortsetzbar.

python3 fetch_fundamentals.py      Je Kennzahl eine Liste [start, ende, wert, meldedatum, formular].

Vorher wird die Zuordnung Ticker -> SEC-Nummer erweitert (data/sec_meta_plus.json): alle Firmen, die 2024/25
eine Bilanzsumme gemeldet haben, nicht nur die mit mindestens 10 Mio. $ Umsatz aus sec_meta.json.
"""
import os, json, concurrent.futures as cf
from common import DATA, get_json
import screener as s
from fetch_history import bt_universe, sec_one

FACTS = os.path.join(DATA, "facts")
os.makedirs(FACTS, exist_ok=True)
TAGS = list(s.REV_TAGS) + ["SalesRevenueNet", "OperatingIncomeLoss", "NetIncomeLoss", "Assets",
                           "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                           "WeightedAverageNumberOfDilutedSharesOutstanding",
                           "WeightedAverageNumberOfSharesOutstandingBasic", "CommonStockSharesOutstanding",
                           "EntityCommonStockSharesOutstanding"]


PLUS = os.path.join(DATA, "sec_meta_plus.json")


def zuordnung_erweitern():
    meta = json.load(open(os.path.join(DATA, "sec_meta.json")))
    plus = json.load(open(PLUS)) if os.path.exists(PLUS) else {}
    ciks = set()
    for per in ("CY2024Q4I", "CY2025Q2I", "CY2025Q4I"):
        j = get_json(f"https://data.sec.gov/api/xbrl/frames/us-gaap/Assets/USD/{per}.json")
        ciks |= {d["cik"] for d in (j or {}).get("data", [])}
    todo = sorted(c for c in ciks if str(c) not in meta and str(c) not in plus)
    print(f"Zuordnung: {len(todo)} Firmen nachzuladen", flush=True)
    with cf.ThreadPoolExecutor(4) as ex:
        for i, (c, m) in enumerate(zip(todo, ex.map(sec_one, todo)), 1):
            if m:
                plus[str(c)] = {"tickers": m["tickers"], "name": m["name"]}
            if i % 500 == 0:
                json.dump(plus, open(PLUS, "w"))
                print(f"  Zuordnung {i}/{len(todo)}", flush=True)
    json.dump(plus, open(PLUS, "w"))


def ticker_cik():
    meta = json.load(open(os.path.join(DATA, "sec_meta.json")))
    if os.path.exists(PLUS):
        meta = {**json.load(open(PLUS)), **meta}
    t2c = {}
    for c, v in sorted(meta.items(), key=lambda x: int(x[0])):
        for t in v["tickers"]:
            t2c.setdefault(t, c)
    return {sym: t2c[sym] for sym in bt_universe() if sym in t2c}


def one(c):
    p = os.path.join(FACTS, f"{c}.json")
    if os.path.exists(p):
        return True
    j = get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(c):010d}.json")
    if j is None:
        return False
    out = {}
    for grp in ("us-gaap", "dei"):
        for t, v in (j.get("facts", {}).get(grp) or {}).items():
            if t in TAGS:
                rows = [x for u, xs in v["units"].items() if u in ("USD", "shares") for x in xs]
                out[t] = [[x.get("start"), x["end"], x["val"], x["filed"], x["form"]] for x in rows]
    json.dump(out, open(p + ".tmp", "w"))
    os.replace(p + ".tmp", p)
    return True


if __name__ == "__main__":
    zuordnung_erweitern()
    ciks = sorted(set(ticker_cik().values()))
    print(f"Bilanzdaten: {len(ciks)} Firmen", flush=True)
    fail = 0
    with cf.ThreadPoolExecutor(4) as ex:
        for i, ok in enumerate(ex.map(one, ciks), 1):
            fail += not ok
            if i % 200 == 0:
                print(f"  {i}/{len(ciks)}", flush=True)
    print(f"Bilanzdaten fertig, {fail} ohne Daten oder gescheitert", flush=True)
