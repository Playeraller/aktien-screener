"""Gemeinsame Helfer: HTTP-Abruf mit ehrlicher Kennung, Drosselung, Cache, Kursdaten."""
import os, json, time, threading, datetime
from statistics import mean
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "output")
os.makedirs(DATA, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

HEADERS = {"User-Agent": "equity-screener/1.0 (automated research script)", "Accept": "application/json"}
# Mindestabstand zwischen zwei Anfragen je Host (SEC erlaubt max. 10 pro Sekunde)
MIN_INTERVAL = {"data.sec.gov": 0.13, "api.nasdaq.com": 0.0, "query1.finance.yahoo.com": 0.6}

_tl = threading.local()
_lock = threading.Lock()
_next_slot = {}


def _throttle(host):
    gap = MIN_INTERVAL.get(host, 0.2)
    with _lock:
        now = time.time()
        slot = max(now, _next_slot.get(host, 0))
        _next_slot[host] = slot + gap
    if slot > now:
        time.sleep(slot - now)


def get_json(url, params=None, tries=4, timeout=60):
    """GET -> JSON. None bei 404 oder wenn alle Versuche scheitern."""
    host = url.split("/")[2]
    s = getattr(_tl, "s", None)
    if s is None:
        s = _tl.s = requests.Session()
        s.headers.update(HEADERS)
    for i in range(tries):
        _throttle(host)
        try:
            r = s.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
        except (requests.RequestException, ValueError):
            pass
        time.sleep(2 * (i + 1))
    return None


def cache_load(name, max_age_h):
    p = os.path.join(DATA, name)
    if os.path.exists(p) and (time.time() - os.path.getmtime(p)) < max_age_h * 3600:
        with open(p) as f:
            return json.load(f)
    return None


def cache_save(name, obj):
    p = os.path.join(DATA, name)
    with open(p + ".tmp", "w") as f:
        json.dump(obj, f)
    os.replace(p + ".tmp", p)


def num(x):
    try:
        return float(str(x).replace("$", "").replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return None


# ---------- Kursdaten ----------

def nasdaq_history(sym, days=420):
    """Tagesschlusskurse einer US-Aktie, neueste zuerst: [(datum_iso, schluss, stueckumsatz)]."""
    today = datetime.date.today()
    j = get_json(
        f"https://api.nasdaq.com/api/quote/{sym}/historical",
        params={"assetclass": "stocks", "fromdate": (today - datetime.timedelta(days=days)).isoformat(),
                "todate": today.isoformat(), "limit": days},
        tries=3, timeout=40)
    try:
        rows = j["data"]["tradesTable"]["rows"]
    except (TypeError, KeyError):
        return None
    out = []
    for r in rows or []:
        c, v = num(r.get("close")), num(r.get("volume"))
        if c:
            m, d, y = r["date"].split("/")
            out.append((f"{y}-{m}-{d}", c, v or 0.0))
    return out or None


def yahoo_history(sym, rng="2y"):
    """Wie nasdaq_history, aber ueber Yahoo (fuer Nicht-US-Werte, z. B. SAP.DE). Liefert auch die Waehrung."""
    j = get_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                 params={"range": rng, "interval": "1d"}, tries=4, timeout=40)
    try:
        res = j["chart"]["result"][0]
        ts = res["timestamp"]
        q = res["indicators"]["quote"][0]
        cur = res["meta"].get("currency")
    except (TypeError, KeyError, IndexError):
        return None, None
    out = []
    for t, c, v in zip(ts, q["close"], q["volume"]):
        if c:
            out.append((datetime.datetime.fromtimestamp(t, datetime.timezone.utc).date().isoformat(), c, v or 0.0))
    out.reverse()
    return (out or None), cur


def price_metrics(rows):
    """Kennzahlen aus Tageskursen (neueste zuerst)."""
    if not rows or len(rows) < 30:
        return None
    c = [r[1] for r in rows]
    v = [r[2] for r in rows]
    m = {"close": c[0], "date": rows[0][0], "n": len(c)}
    m["sma200"] = mean(c[:200]) if len(c) >= 200 else None
    m["sma50"] = mean(c[:50]) if len(c) >= 50 else None
    m["ret_6m"] = c[0] / c[126] - 1 if len(c) > 126 else None
    m["ret_12m"] = c[0] / c[252] - 1 if len(c) > 252 else None
    m["advol20"] = mean(ci * vi for ci, vi in zip(c[:20], v[:20]))
    m["high_52w"] = max(c[:252])
    m["from_high"] = c[0] / m["high_52w"] - 1
    # Wochenschluss (letzter Handelstag der Vorwoche) fuer die 200-Tage-Regel
    last = datetime.date.fromisoformat(rows[0][0])
    wk = [r for r in rows if datetime.date.fromisoformat(r[0]).isocalendar()[:2] != last.isocalendar()[:2]]
    m["week_close"] = wk[0][1] if wk else c[0]
    m["split_flag"] = any(c[i] / c[i + 1] > 1.9 or c[i] / c[i + 1] < 0.52 for i in range(min(len(c) - 1, 252)))
    return m
