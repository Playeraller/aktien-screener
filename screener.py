"""US Small-/Mid-Cap-Wachstumsscreener.

Stufen: Universum (Nasdaq-Liste) -> Grobfilter Umsatzwachstum (SEC-Frames) -> Zuordnung CIK/Ticker
-> genaue Kennzahlen (SEC companyfacts) -> Kurstrend (Nasdaq-Historie) -> Kriterien + Ausgabe.

Aufruf:  python3 screener.py            kompletter Lauf (nutzt Cache in data/)
         python3 screener.py --prices   nur Kursdaten laden (langsamster Teil, ca. 45 Min.)
         python3 screener.py --facts    nur SEC-Bilanzdaten laden (kann parallel zu --prices laufen)
"""
import re, sys, json, datetime, concurrent.futures as cf
import pandas as pd
from common import (DATA, OUT, get_json, cache_load, cache_save, num, nasdaq_history, price_metrics)

TODAY = datetime.date.today()
D = datetime.date.fromisoformat

# ---------------- Schwellen der Strategie ----------------
MCAP_MIN, MCAP_MAX = 3e8, 1e10      # Boersenwert in USD
ADVOL_MIN = 1e6                     # Tagesumsatz in USD (20-Tage-Schnitt)
CAGR_MIN = 0.15                     # Umsatzwachstum p.a. ueber 3 Jahre
QYOY_MIN = 0.10                     # letztes Quartal ggü. Vorjahr (nicht stark abflachend)
ROIC_MIN = 0.15                     # Kapitalrendite
ROIC_MIN_RISING, MARGIN_UP = 0.08, 0.02   # Alternative: ROIC >= 8 % und Marge +2 Punkte
ND_EBITDA_MAX = 2.0
DILUTION_MAX = 0.03                 # neue Aktien p.a.
MOM_PCT_MIN = 2 / 3                 # relative Staerke: oberes Drittel
TAX = 0.21
EXIT_PE, FADE_TO, G_CAP = 20, 0.08, 0.30   # mechanisches Basisszenario
BUY_RETURN_MIN = 0.15

EXCL_SECTORS = {"Finance", "Real Estate"}
EXCL_NAME = re.compile(r"warrant|\bunits?\b|\brights?\b|preferred|depositary|acquisition corp|\bnotes\b|debenture|%|\betf\b|\bfund\b", re.I)

REV_TAGS = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
            "RevenueFromContractWithCustomerIncludingAssessedTax"]


def log(*a):
    print(*a, flush=True)


# ---------------- Stufe 1: Universum ----------------
def load_universe():
    j = cache_load("nasdaq_universe.json", 20)
    if j is None:
        j = get_json("https://api.nasdaq.com/api/screener/stocks",
                     params={"tableonly": "true", "limit": 10000, "offset": 0, "download": "true"}, timeout=120)
        cache_save("nasdaq_universe.json", j)
    rows = j["data"]["rows"]
    out = {}
    for r in rows:
        mc = num(r.get("marketCap")) or 0
        sym = r["symbol"].strip()
        if not (MCAP_MIN <= mc <= MCAP_MAX) or "/" in sym or "^" in sym:
            continue
        out[sym] = {"symbol": sym, "name": r["name"], "mcap": mc, "sector": r.get("sector") or "",
                    "industry": r.get("industry") or "", "country": r.get("country") or "",
                    "eligible": not (r.get("sector") in EXCL_SECTORS or EXCL_NAME.search(r["name"]))}
    return out


def load_prices(symbols):
    """Kurskennzahlen fuer alle Symbole; Cache 20 h, Zwischenspeichern alle 150 Titel."""
    cache = cache_load("price_metrics.json", 20) or {}
    todo = [s for s in symbols if s not in cache]
    if todo:
        log(f"Lade Kurse fuer {len(todo)} Titel ...")
        done = 0
        with cf.ThreadPoolExecutor(6) as ex:
            for sym, m in zip(todo, ex.map(lambda s: price_metrics(nasdaq_history(s)), todo)):
                cache[sym] = m
                done += 1
                if done % 150 == 0:
                    cache_save("price_metrics.json", cache)
                    log(f"  {done}/{len(todo)}")
        cache_save("price_metrics.json", cache)
    return cache


# ---------------- Stufe 2a: Grobfilter ueber SEC-Frames ----------------
def frame(tag, period):
    name = f"frame_{tag}_{period}.json"
    j = cache_load(name, 24)
    if j is None:
        j = get_json(f"https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/USD/{period}.json") or {"data": []}
        j = {"data": [{"cik": d["cik"], "val": d["val"], "entityName": d.get("entityName")} for d in j.get("data", [])]}
        cache_save(name, j)
    return j["data"]


def coarse_filter():
    y = TODAY.year - 1 if TODAY.month >= 4 else TODAY.year - 2          # letztes volles Geschaeftsjahr
    annual = [f"CY{y - 3}", f"CY{y - 2}", f"CY{y - 1}", f"CY{y}"]
    cq = (TODAY.month - 1) // 3                                           # letztes abgeschlossenes Quartal
    qy = TODAY.year if cq > 0 else TODAY.year - 1
    cq = cq if cq > 0 else 4
    quarters = []
    for _ in range(2):                                                    # die zwei juengsten Quartale + Vorjahr
        quarters.append((f"CY{qy}Q{cq}", f"CY{qy - 1}Q{cq}"))
        cq, qy = (cq - 1, qy) if cq > 1 else (4, qy - 1)
    periods = annual + [p for pair in quarters for p in pair]
    rev, names = {p: {} for p in periods}, {}
    for p in periods:
        for t in REV_TAGS:
            for d in frame(t, p):
                if d["val"] and d["val"] > rev[p].get(d["cik"], 0):
                    rev[p][d["cik"]] = d["val"]
                names[d["cik"]] = d["entityName"]
    keep = {}
    for cik, r_last in rev[annual[3]].items():
        if r_last < 50e6:
            continue
        base, n = rev[annual[0]].get(cik), 3
        if not base:
            base, n = rev[annual[1]].get(cik), 2
        if not base or (r_last / base) ** (1 / n) - 1 < 0.12:
            continue
        qyoy = None
        for cur, prev in quarters:
            if cik in rev[cur] and rev[prev].get(cik):
                qyoy = rev[cur][cik] / rev[prev][cik] - 1
                break
        if qyoy is not None and qyoy < 0.05:
            continue
        keep[cik] = names.get(cik)
    log(f"Grobfilter: {len(rev[annual[3]])} Firmen mit Umsatz {annual[3]} -> {len(keep)} mit Wachstum")
    return keep


# ---------------- Stufe 2b: CIK -> Ticker ----------------
def load_submissions(ciks):
    cache = cache_load("submissions.json", 24 * 30) or {}
    todo = [c for c in ciks if str(c) not in cache]
    if todo:
        log(f"Lade Stammdaten fuer {len(todo)} Firmen ...")

        def one(c):
            j = get_json(f"https://data.sec.gov/submissions/CIK{int(c):010d}.json") or {}
            return {"tickers": j.get("tickers") or [], "sic": j.get("sicDescription") or "", "name": j.get("name") or ""}

        with cf.ThreadPoolExecutor(4) as ex:
            for c, s in zip(todo, ex.map(one, todo)):
                cache[str(c)] = s
        cache_save("submissions.json", cache)
    return cache


# ---------------- Stufe 2c: genaue Kennzahlen aus companyfacts ----------------
def _units(cfj, tag, unit="USD", tax="us-gaap"):
    try:
        return cfj["facts"][tax][tag]["units"][unit]
    except (KeyError, TypeError):
        return []


def flow_map(cfj, tag, unit="USD"):
    """{(start, ende): wert}; bei Doppelmeldungen gilt die zuletzt eingereichte (restated) Zahl."""
    best = {}
    for f in _units(cfj, tag, unit):
        if "start" not in f:
            continue
        k = (D(f["start"]), D(f["end"]))
        if k not in best or f.get("filed", "") > best[k][1]:
            best[k] = (f["val"], f.get("filed", ""))
    return {k: v[0] for k, v in best.items()}


def merged_max(cfj, tags):
    out = {}
    for t in tags:
        for k, v in flow_map(cfj, t).items():
            if k not in out or v > out[k]:
                out[k] = v
    return out


def freshest(cfj, tags, unit="USD"):
    """Zeitreihe des Tags mit den juengsten Daten (bei Gleichstand gilt die Reihenfolge)."""
    best, best_end = {}, None
    for t in tags:
        m = flow_map(cfj, t, unit)
        if not m:
            continue
        e = max(k[1] for k in m)
        if best_end is None or (e - best_end).days > 100:
            best, best_end = m, e
    return best


def inst_map(cfj, tag):
    best = {}
    for f in _units(cfj, tag):
        if "start" in f:
            continue
        k = D(f["end"])
        if k not in best or f.get("filed", "") > best[k][1]:
            best[k] = (f["val"], f.get("filed", ""))
    return {k: v[0] for k, v in best.items()}


def at(cfj, tags, bd):
    for t in tags:
        m = inst_map(cfj, t)
        if bd in m:
            return m[bd]
    return None


def annuals(fl):
    return sorted((e, s, v) for (s, e), v in fl.items() if 350 <= (e - s).days <= 380)


def ttm(fl):
    """Letzte 12 Monate = letztes Geschaeftsjahr + laufendes Jahr bis heute - gleicher Vorjahreszeitraum."""
    an = annuals(fl)
    if not an:
        return None, None
    ae, _, av = an[-1]
    if (TODAY - ae).days > 500:
        return None, None
    ytd = [(e, s, v) for (s, e), v in fl.items() if abs((s - ae).days - 1) <= 7 and (e - s).days < 340]
    if not ytd:
        return av, ae
    ye, ys, yv = max(ytd)
    prior = [v for (s, e), v in fl.items() if abs((ys - s).days - 365) <= 10 and abs((ye - e).days - 365) <= 10]
    if not prior:
        return av, ae
    return av + yv - prior[0], ye


def growth_n(fl, years):
    an = annuals(fl)
    if not an:
        return None
    e1, _, v1 = an[-1]
    for e0, _, v0 in an:
        if abs((e1 - e0).days - 365 * years) <= 25 and v0 and v0 > 0 and v1 > 0:
            return (v1 / v0) ** (1 / years) - 1
    return None


def value_years_ago(fl, years):
    an = annuals(fl)
    if not an:
        return None
    e1 = an[-1][0]
    for e0, _, v0 in an:
        if abs((e1 - e0).days - 365 * years) <= 25:
            return v0
    return None


def quarter_yoy(fl):
    """Wachstum des juengsten Quartals ggü. Vorjahr; Q4 wird aus Jahr minus 9 Monate abgeleitet."""
    q = [(e, s, v) for (s, e), v in fl.items() if 80 <= (e - s).days <= 100]
    best = None
    if q:
        qe, _, qv = max(q)
        pr = [v for (e, s, v) in q if abs((qe - e).days - 365) <= 10]
        if pr and pr[0] > 0:
            best = (qe, qv / pr[0] - 1)
    an = annuals(fl)
    if an and (best is None or an[-1][0] > best[0]):
        ae, as_, av = an[-1]
        prev = [(e, s, v) for (e, s, v) in an if abs((ae - e).days - 365) <= 10]

        def nine(start):
            c = [v for (s, e), v in fl.items() if abs((s - start).days) <= 7 and 255 <= (e - s).days <= 290]
            return c[0] if c else None

        if prev:
            n1, n0 = nine(as_), nine(prev[0][1])
            if n1 is not None and n0 is not None and prev[0][2] - n0 > 0:
                best = (ae, (av - n1) / (prev[0][2] - n0) - 1)
    return best if best else (None, None)


def metrics(cfj):
    """Alle Fundamentalkennzahlen einer Firma. None, wenn Kerndaten fehlen."""
    rev = merged_max(cfj, REV_TAGS)
    rev_ttm, rev_end = ttm(rev)
    if not rev_ttm or rev_ttm <= 0:
        return None
    m = {"rev_ttm": rev_ttm, "report_end": rev_end.isoformat()}
    m["cagr3"] = growth_n(rev, 3)
    m["cagr_years"] = 3
    if m["cagr3"] is None:
        m["cagr3"], m["cagr_years"] = growth_n(rev, 2), 2
    m["q_end"], m["q_yoy"] = quarter_yoy(rev)
    m["q_end"] = m["q_end"].isoformat() if m["q_end"] else None

    op = freshest(cfj, ["OperatingIncomeLoss",
                        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"])
    m["op_ttm"], _ = ttm(op)
    m["ni_ttm"], _ = ttm(freshest(cfj, ["NetIncomeLoss", "ProfitLoss"]))
    gp, _ = ttm(freshest(cfj, ["GrossProfit"]))
    if gp is None:
        cogs, _ = ttm(freshest(cfj, ["CostOfRevenue", "CostOfGoodsAndServicesSold"]))
        gp = rev_ttm - cogs if cogs else None
    m["gross_margin"] = gp / rev_ttm if gp is not None else None
    ocf, _ = ttm(freshest(cfj, ["NetCashProvidedByUsedInOperatingActivities",
                                "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"]))
    capex, _ = ttm(freshest(cfj, ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"]))
    m["fcf_ttm"] = ocf - (capex or 0) if ocf is not None else None
    da, _ = ttm(freshest(cfj, ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
                               "DepreciationAmortizationAndAccretionNet"]))
    m["op_margin"] = m["op_ttm"] / rev_ttm if m["op_ttm"] is not None else None
    # Margentrend: operative Marge heute ggü. Geschaeftsjahr vor zwei Jahren
    op2, rev2 = value_years_ago(op, 2), value_years_ago(rev, 2)
    m["margin_delta"] = (m["op_margin"] - op2 / rev2) if (m["op_margin"] is not None and op2 is not None and rev2) else None

    # Bilanz zum juengsten Stichtag
    assets = inst_map(cfj, "Assets") or inst_map(cfj, "StockholdersEquity")
    if not assets:
        return None
    bd = max(assets)
    if (TODAY - bd).days > 250:
        return None
    g = lambda *tags: at(cfj, list(tags), bd) or 0.0
    equity = at(cfj, ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"], bd)
    cash = (g("CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "Cash")
            + max(g("ShortTermInvestments"), g("MarketableSecuritiesCurrent"), g("AvailableForSaleSecuritiesDebtSecuritiesCurrent")))
    debt = max(g("LongTermDebt"),
               g("LongTermDebtNoncurrent") + g("LongTermDebtCurrent"),
               g("LongTermDebtAndCapitalLeaseObligations") + g("LongTermDebtAndCapitalLeaseObligationsCurrent"),
               g("DebtAndCapitalLeaseObligations"), g("DebtLongtermAndShorttermCombinedAmount"),
               g("ConvertibleNotesPayableNoncurrent") + g("ConvertibleNotesPayableCurrent"),
               g("ConvertibleDebtNoncurrent") + g("ConvertibleDebtCurrent"),
               g("SeniorNotes"), g("NotesPayable"), g("LongTermNotesPayable"), g("LongTermLineOfCredit"),
               g("ConvertibleNotesPayable")) + g("ShortTermBorrowings")
    m.update(balance_date=bd.isoformat(), cash=cash, debt=debt, equity=equity)
    if m["op_ttm"] is not None and equity is not None:
        ic = equity + debt - cash
        nopat = m["op_ttm"] * (1 - TAX)
        m["roic"] = (nopat / ic) if ic > 0 else (9.99 if nopat > 0 else -9.99)
    else:
        m["roic"] = None
    nd = debt - cash
    if m["op_ttm"] is None:
        m["nd_ebitda"] = None
    elif nd <= 0:
        m["nd_ebitda"] = 0.0
    else:
        ebitda = m["op_ttm"] + (da or 0)
        m["nd_ebitda"] = nd / ebitda if ebitda > 0 else 99.0
    # Verwaesserung: gewichtete Aktienzahl, letztes Geschaeftsjahr ggü. zwei Jahre zuvor (gleicher Bericht -> splitbereinigt)
    sh = freshest(cfj, ["WeightedAverageNumberOfSharesOutstandingBasic", "WeightedAverageNumberOfDilutedSharesOutstanding"], "shares")
    m["dilution"] = growth_n(sh, 2)
    if m["dilution"] is None:
        m["dilution"] = growth_n(sh, 1)
    return m


def load_facts(ciks):
    cache = cache_load("fact_metrics.json", 20) or {}
    todo = [c for c in ciks if str(c) not in cache]
    if todo:
        log(f"Lade Bilanzdaten fuer {len(todo)} Firmen ...")

        def one(c):
            j = get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(c):010d}.json", timeout=120)
            try:
                return metrics(j) if j else None
            except Exception as e:  # einzelne kaputte Datensaetze sollen den Lauf nicht stoppen
                return {"error": repr(e)}

        done = 0
        with cf.ThreadPoolExecutor(4) as ex:
            for c, m in zip(todo, ex.map(one, todo)):
                cache[str(c)] = m
                done += 1
                if done % 50 == 0:
                    cache_save("fact_metrics.json", cache)
                    log(f"  {done}/{len(todo)}")
        cache_save("fact_metrics.json", cache)
    return cache


# ---------------- Bewertung ----------------
def base_case_return(r):
    """Mechanisches Basisszenario ueber 5 Jahre: Wachstum flacht auf 8 % ab, Marge bleibt, Ausstieg bei KGV 20."""
    if r["op_margin"] is None or r["cagr3"] is None or r["q_yoy"] is None:
        return None
    margin = r["op_margin"] * (1 - TAX)
    if margin <= 0 and r["fcf_ttm"]:
        margin = 0.8 * r["fcf_ttm"] / r["rev_ttm"]
    if margin <= 0:
        return None
    g0 = max(min(r["cagr3"], r["q_yoy"], G_CAP), FADE_TO)
    rev = r["rev_ttm"]
    for i in range(5):
        rev *= 1 + g0 + (FADE_TO - g0) * i / 4
    value = rev * min(margin, 0.30) * EXIT_PE + (r["cash"] - r["debt"])
    return (value / r["mcap"]) ** 0.2 - 1 if value > 0 else None


def evaluate(row):
    k = {}
    k["K1_Liquiditaet"] = bool(row["advol20"] and row["advol20"] >= ADVOL_MIN)
    k["K2_Wachstum"] = bool(row["cagr3"] is not None and row["cagr3"] >= CAGR_MIN
                            and row["q_yoy"] is not None and row["q_yoy"] >= QYOY_MIN)
    profitable = (row["op_ttm"] or 0) > 0 or (row["fcf_ttm"] or 0) > 0
    roic_ok = row["roic"] is not None and (row["roic"] >= ROIC_MIN or (
        row["roic"] >= ROIC_MIN_RISING and (row["margin_delta"] or 0) >= MARGIN_UP))
    k["K3_Qualitaet"] = bool(profitable and roic_ok)
    k["K4_Bilanz"] = bool(row["nd_ebitda"] is not None and row["nd_ebitda"] < ND_EBITDA_MAX
                          and row["dilution"] is not None and row["dilution"] <= DILUTION_MAX)
    k["K5_Trend"] = bool(row["sma200"] and row["close"] > row["sma200"]
                         and row["mom_pct"] is not None and row["mom_pct"] >= MOM_PCT_MIN)
    return k


def pct(x, d=0):
    return "k.A." if x is None or pd.isna(x) else f"{x * 100:.{d}f} %"


def main():
    uni = load_universe()
    log(f"Universum {MCAP_MIN/1e6:.0f} Mio. - {MCAP_MAX/1e9:.0f} Mrd. $: {len(uni)} Titel, davon {sum(u['eligible'] for u in uni.values())} zugelassen")
    facts_only = "--facts" in sys.argv          # nur SEC-Daten vorladen, Kurse ueberspringen
    prices = {} if facts_only else load_prices(sorted(uni))
    if "--prices" in sys.argv:
        return
    # Relative Staerke: Perzentil der 6-Monats-Rendite im gesamten Universum
    r6 = pd.Series({s: p["ret_6m"] for s, p in prices.items() if s in uni and p and p.get("ret_6m") is not None})
    mom_pct = r6.rank(pct=True)

    coarse = coarse_filter()
    subs = load_submissions(sorted(coarse))
    matched = {}
    for cik in coarse:
        ticks = [t for t in subs.get(str(cik), {}).get("tickers", []) if t in uni and uni[t]["eligible"]]
        if ticks:
            matched[cik] = max(ticks, key=lambda t: (prices.get(t) or {}).get("advol20") or 0)
    log(f"Im Universum (ohne Finanz/Immobilien): {len(matched)} Firmen")
    limit = next((int(a.split("=")[1]) for a in sys.argv if a.startswith("--limit=")), None)
    ciks = sorted(matched)[:limit]
    facts = load_facts(ciks)
    if facts_only:
        return

    rows = []
    for cik in ciks:
        f, sym = facts.get(str(cik)), matched[cik]
        p = prices.get(sym)
        if not f or "error" in f or not p:
            continue
        r = {**uni[sym], "cik": cik, "sic": subs[str(cik)]["sic"], **f, **p, "mom_pct": mom_pct.get(sym)}
        r.pop("eligible", None)
        k = evaluate(r)
        r.update(k)
        r["n_pass"] = sum(k.values())
        r["fails"] = ", ".join(n.split("_")[1] for n, ok in k.items() if not ok)
        ev = r["mcap"] + r["debt"] - r["cash"]
        r["ev_sales"] = ev / r["rev_ttm"]
        r["ev_ebit"] = ev / r["op_ttm"] if (r["op_ttm"] or 0) > 0 else None
        r["pe"] = r["mcap"] / r["ni_ttm"] if (r["ni_ttm"] or 0) > 0 else None
        r["base_return"] = base_case_return(r)
        rows.append(r)
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUT}/alle_geprueft.csv", index=False)
    cand = df[df.n_pass == 5].sort_values("base_return", ascending=False, na_position="last")
    watch = df[(df.n_pass == 4) & df.K2_Wachstum].sort_values("base_return", ascending=False, na_position="last")
    cand.to_csv(f"{OUT}/kandidaten.csv", index=False)
    watch.to_csv(f"{OUT}/watchlist.csv", index=False)

    def table(d, with_fail=False):
        head = ["Ticker", "Name", "Branche", "Börsenwert", "Wachstum 3J p.a.", "Letztes Quartal", "Op. Marge", "ROIC",
                "Nettoschulden/EBITDA", "Neue Aktien p.a.", "Kurs zu 200-Tage", "6M-Rendite", "EV/Umsatz", "KGV",
                "Basisrendite p.a."] + (["Scheitert an"] if with_fail else [])
        out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
        for _, r in d.iterrows():
            cells = [r.symbol, re.sub(r"\s+(Common Stock|Class A.*|Ordinary Shares.*)$", "", r["name"])[:32], (r.sic or r.industry)[:30].title(),
                     f"{r.mcap / 1e9:.1f} Mrd. $", pct(r.cagr3), pct(r.q_yoy), pct(r.op_margin),
                     ">100 %" if r.roic and r.roic > 1 else pct(r.roic),
                     "Nettokasse" if r.nd_ebitda == 0 else ("k.A." if pd.isna(r.nd_ebitda) else f"{r.nd_ebitda:.1f}"),
                     pct(r.dilution, 1), pct(r.close / r.sma200 - 1) if r.sma200 else "k.A.", pct(r.ret_6m),
                     f"{r.ev_sales:.1f}", "k.A." if pd.isna(r.pe) else f"{r.pe:.0f}", pct(r.base_return)]
            if with_fail:
                cells.append(r.fails)
            out.append("| " + " | ".join(str(c) for c in cells) + " |")
        return "\n".join(out)

    rep = [f"# Screener-Lauf vom {TODAY.isoformat()}", "",
           f"- Universum: {len(uni)} US-Aktien mit {MCAP_MIN/1e6:.0f} Mio. bis {MCAP_MAX/1e9:.0f} Mrd. $ Börsenwert",
           f"- Umsatzwachstum im Grobfilter: {len(coarse)} Firmen, davon im Universum: {len(matched)}",
           f"- Vollständig geprüft: {len(df)}",
           f"- **Kandidaten (alle 5 Kriterien): {len(cand)}**, Beobachtungsliste (4 von 5): {len(watch)}", "",
           "Die Basisrendite ist eine mechanische Rechnung (Wachstum flacht auf 8 % ab, Marge bleibt, Ausstieg bei KGV 20). "
           f"Kaufschwelle der Strategie: mindestens {BUY_RETURN_MIN*100:.0f} % p.a.", "",
           "## Kandidaten", "", table(cand), "", "## Beobachtungsliste", "", table(watch, True), ""]
    with open(f"{OUT}/report.md", "w") as f:
        f.write("\n".join(rep))
    log(f"Fertig: {len(df)} geprueft, {len(cand)} Kandidaten, {len(watch)} Beobachtungsliste -> {OUT}/report.md")


if __name__ == "__main__":
    main()
