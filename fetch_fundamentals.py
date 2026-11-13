"""Bilanzdaten mit Meldedatum je Firma laden (SEC companyfacts) -> data/facts/CIK.json, fortsetzbar.

python3 fetch_fundamentals.py      Je Kennzahl eine Liste [start, ende, wert, meldedatum, formular].
"""
import os, json, concurrent.futures as cf
from common import DATA, get_json
import screener as s
from fetch_history import bt_universe

FACTS = os.path.join(DATA, "facts")
os.makedirs(FACTS, exist_ok=True)
TAGS = list(s.REV_TAGS) + ["OperatingIncomeLoss", "NetIncomeLoss", "Assets",
                           "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                           "WeightedAverageNumberOfDilutedSharesOutstanding",
                           "WeightedAverageNumberOfSharesOutstandingBasic", "CommonStockSharesOutstanding",
                           "EntityCommonStockSharesOutstanding"]


def ticker_cik():
    meta = json.load(open(os.path.join(DATA, "sec_meta.json")))
    t2c = {}
    for c, v in meta.items():
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
    ciks = sorted(set(ticker_cik().values()))
    print(f"Bilanzdaten: {len(ciks)} Firmen", flush=True)
    fail = 0
    with cf.ThreadPoolExecutor(4) as ex:
        for i, ok in enumerate(ex.map(one, ciks), 1):
            fail += not ok
            if i % 200 == 0:
                print(f"  {i}/{len(ciks)}", flush=True)
    print(f"Bilanzdaten fertig, {fail} ohne Daten oder gescheitert", flush=True)
