"""Ruecktest beider Schienen auf 5 Jahren Kursdaten.

Schiene 2 (Ausbruch): Tagessprung >= 10 % bei >= 3-fachem Volumen, Einstieg am naechsten Tag zur Eroeffnung.
Schiene 1 (Qualitaet): halbjaehrliche Auswahl nach den Screener-Kriterien (vereinfachte Jahresdaten), 6 Monate halten.

Aufruf: python3 backtest.py        (vorher: python3 fetch_history.py prices  und  ... sec)
Einschraenkung: Das Universum sind HEUTE gelistete Aktien; Pleiten und Uebernahmen fehlen (Survivorship-Bias).
"""
import os, json, pickle, datetime, warnings
import numpy as np, pandas as pd
from common import DATA, OUT, get_json, cache_load, cache_save
import screener as s
from fetch_history import HIST

warnings.filterwarnings("ignore")
HS = (5, 20, 60, 120)
COST = 0.004          # Kosten je Kauf+Verkauf (Spanne, Gebuehren)
FIELDS = ("open", "high", "low", "close", "volume")


# ---------------- Daten ----------------
def load_panel(rebuild=False, tail=None):
    """Kursmatrizen aller Aktien. tail=N laedt nur die letzten N Tage (fuer den Scanner, ohne Cache)."""
    p = os.path.join(DATA, "panel.pkl")
    if os.path.exists(p) and not rebuild and not tail:
        return pickle.load(open(p, "rb"))
    cols = {k: {} for k in FIELDS}
    for f in sorted(os.listdir(HIST)):
        if not f.endswith(".csv"):
            continue
        df = pd.read_csv(os.path.join(HIST, f), index_col=0)
        df = df[~df.index.duplicated()]
        if len(df) < 60:
            continue
        if tail:
            df = df.tail(tail)
        for k in FIELDS:
            cols[k][f[:-4]] = df[k]
    P = {k: pd.DataFrame(v).sort_index() for k, v in cols.items()}
    if tail:
        return {k: v.tail(tail) for k, v in P.items()}
    pickle.dump(P, open(p, "wb"))
    return P


def fr(tag, period, unit="USD"):
    """SEC-Frame {cik: wert}, 30 Tage im Cache (historische Perioden aendern sich kaum)."""
    name = f"bt_{tag}_{unit}_{period}.json"
    recent = int(period[2:6]) >= s.TODAY.year - 1          # junge Perioden fuellen sich noch -> taeglich neu laden
    j = cache_load(name, 20 if recent else 24 * 30)
    if j is None:
        r = get_json(f"https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/{unit}/{period}.json") or {}
        j = {str(d["cik"]): d["val"] for d in r.get("data", [])}
        cache_save(name, j)
    return j


def merged(tags, period, unit="USD", how="max"):
    out = {}
    for t in tags:
        for c, v in fr(t, period, unit).items():
            if v is not None and (c not in out or (how == "max" and v > out[c])):
                out[c] = v
    return out


def quarterly(tags, years):
    """{(jahr, quartal): {cik: wert}}; Q4 wird, wo noetig, aus Jahr minus Q1-Q3 abgeleitet."""
    q = {}
    for y in years:
        for k in (1, 2, 3, 4):
            if (y, k) > (s.TODAY.year, (s.TODAY.month - 1) // 3):
                continue
            q[(y, k)] = merged(tags, f"CY{y}Q{k}")
        if (y, 4) in q:
            ann = merged(tags, f"CY{y}")
            for c, a in ann.items():
                if c not in q[(y, 4)] and all(c in q[(y, k)] for k in (1, 2, 3)):
                    q[(y, 4)][c] = a - sum(q[(y, k)][c] for k in (1, 2, 3))
    return q


def sec_meta():
    meta = json.load(open(os.path.join(DATA, "sec_meta.json")))
    t2c = {}
    for cik, m in meta.items():
        for t in m["tickers"]:
            t2c.setdefault(t, cik)
    return meta, t2c


# ---------------- Schiene 2: Ausbruch ----------------
def find_events(P, min_jump=0.10, vol_mult=3.0, gap=20):
    C, H, L, V = P["close"], P["high"], P["low"], P["volume"]
    ret = C / C.shift(1) - 1
    vavg = V.shift(1).rolling(50, min_periods=40).mean()
    dvol = (C * V).shift(1).rolling(20, min_periods=15).mean()
    mask = (ret >= min_jump) & (V >= vol_mult * vavg) & (C >= 3) & (dvol >= 1e6)
    ii, jj = np.where(mask.values)
    ev = pd.DataFrame({"i": ii, "sym": C.columns[jj], "date": C.index[ii], "jump": ret.values[ii, jj],
                       "volx": (V / vavg).values[ii, jj], "low": L.values[ii, jj], "close": C.values[ii, jj],
                       "loc": ((C - L) / (H - L)).values[ii, jj]}).sort_values(["sym", "i"])
    keep, last = [], {}
    for r in ev.itertuples():                      # je Aktie nur ein Signal pro 20 Handelstage
        ok = not (r.sym in last and r.i - last[r.sym] < gap)
        keep.append(ok)
        if ok:
            last[r.sym] = r.i
    return ev[keep].reset_index(drop=True)


def add_forward(ev, P):
    C, O = P["close"].values, P["open"].values
    n = C.shape[0]
    col = {x: j for j, x in enumerate(P["close"].columns)}
    cj = ev.sym.map(col).values
    i1 = ev.i.values + 1
    ok = i1 < n
    # Vergleichsmarkt: nur Aktien, die am selben Tag die Liquiditaetsregeln der Signale erfuellen
    liq = (((P["close"] * P["volume"]).shift(1).rolling(20, min_periods=15).mean() >= 1e6) & (P["close"] >= 3)).values
    for h in HS:
        fw = np.full(C.shape, np.nan)
        fw[:n - h] = C[h:] / np.where(O[:n - h] > 0, O[:n - h], np.nan) - 1
        bench = np.nanmean(np.where(liq, fw, np.nan), axis=1)
        f = np.full(len(ev), np.nan)
        b = np.full(len(ev), np.nan)
        f[ok], b[ok] = fw[i1[ok], cj[ok]], bench[i1[ok]]
        ev[f"fwd{h}"], ev[f"exc{h}"] = f, f - b
    return ev


def simulate(ev, P, max_hold=60, trail=False):
    """Einstieg naechste Eroeffnung, Stopp am Tief des Sprungtages (max. -15 %), Ausstieg nach max_hold Tagen
    oder (trail) bei Schlusskurs unter der 50-Tage-Linie ab dem 10. Tag."""
    O, L, C = P["open"].values, P["low"].values, P["close"].values
    sma = P["close"].rolling(50, min_periods=30).mean().values
    n = C.shape[0]
    col = {x: j for j, x in enumerate(P["close"].columns)}
    out = []
    for r in ev.itertuples():
        j0, c = r.i + 1, col[r.sym]
        if j0 + max_hold >= n:                     # nur vollstaendige Haltefenster
            out.append(np.nan)
            continue
        entry = O[j0, c]
        if not entry > 0 or entry <= r.low:
            out.append(np.nan)
            continue
        stop, exit_, last = max(r.low, entry * 0.85), None, entry
        for j in range(j0, j0 + max_hold + 1):
            o, l, cl = O[j, c], L[j, c], C[j, c]
            if np.isnan(cl):
                continue
            if j > j0 and o <= stop:
                exit_ = o
                break
            if l <= stop:
                exit_ = stop
                break
            if trail and j - j0 >= 10 and cl < sma[j, c]:
                exit_ = cl
                break
            last = cl
        out.append((exit_ if exit_ is not None else last) / entry - 1 - COST)
    return np.array(out)


def known_quarter(e):
    d = datetime.date.fromisoformat(e) - datetime.timedelta(days=14)
    k = (d.month - 1) // 3
    return (d.year - 1, 4) if k == 0 else (d.year, k)


def prev_q(q):
    return (q[0] - 1, 4) if q[1] == 1 else (q[0], q[1] - 1)


def add_fundamentals(ev, dates, meta, t2c, revq, opq):
    earn_flag, growth, margin = [], [], []
    for r in ev.itertuples():
        cik = t2c.get(r.sym)
        e_dates = meta[cik]["earnings"] if cik else []
        lo, hi = dates[r.i - 1], dates[min(r.i + 1, len(dates) - 1)]
        earn_flag.append(any(lo <= d <= hi for d in e_dates) if cik else None)
        past = [d for d in e_dates if d <= hi]
        g = m = None
        if past:
            q = known_quarter(past[-1])
            for qq in (q, prev_q(q)):
                cur, base = revq.get(qq, {}).get(cik), revq.get((qq[0] - 1, qq[1]), {}).get(cik)
                if cur and base and base >= 2.5e6:
                    g = cur / base - 1
                    op = opq.get(qq, {}).get(cik)
                    m = op / cur if op is not None else None
                    break
        growth.append(g)
        margin.append(m)
    ev["earn"], ev["growth"], ev["margin"] = earn_flag, growth, margin
    return ev


def summ(d, label):
    r = {"Gruppe": label, "N": len(d)}
    for h in HS:
        r[f"Ø {h}T"] = d[f"fwd{h}"].mean()
    r["Median 60T"] = d.fwd60.median()
    r["Über Markt 20T"], r["Über Markt 60T"], r["Über Markt 120T"] = d.exc20.mean(), d.exc60.mean(), d.exc120.mean()
    v = d.fwd60.dropna()
    r["≥ +25 %"], r["≤ −20 %"] = (v >= 0.25).mean(), (v <= -0.20).mean()
    t = d.r1.dropna()
    r["Regel A Ø"], r["Regel A Treffer"] = t.mean(), (t > 0).mean()
    r["Regel B Ø"] = d.r2.mean()
    return r


def md(rows):
    df = pd.DataFrame(rows)
    out = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    for _, r in df.iterrows():
        cells = [str(v) if isinstance(v, (str, int, np.integer)) else ("k.A." if pd.isna(v) else f"{v * 100:.1f} %") for v in r]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def breakout_bt(P, meta, t2c):
    dates = list(P["close"].index)
    ev = add_forward(find_events(P), P)
    ev["r1"] = simulate(ev, P, 60, False)
    ev["r2"] = simulate(ev, P, 120, True)
    years = range(2020, s.TODAY.year + 1)
    revq, opq = quarterly(s.REV_TAGS, years), quarterly(["OperatingIncomeLoss"], years)
    ev = add_fundamentals(ev, dates, meta, t2c, revq, opq)
    ev["year"] = ev.date.str[:4]
    ev.to_csv(f"{OUT}/ruecktest_ereignisse.csv", index=False)
    E = ev[ev.earn == True]
    rows = [summ(ev, "Alle Sprünge"), summ(E, "Nach Quartalszahlen"), summ(ev[ev.earn == False], "Ohne Quartalszahlen")]
    g = E[E.growth.notna()]
    rows += [summ(g[g.growth >= 0.25], "Zahlen + Wachstum ≥ 25 %"), summ(g[g.growth < 0.25], "Zahlen + Wachstum < 25 %"),
             summ(g[(g.growth >= 0.25) & (g.margin > 0)], "… ≥ 25 % und profitabel"),
             summ(g[(g.growth >= 0.25) & (g.margin <= 0)], "… ≥ 25 % mit Verlust"),
             summ(E[E.jump < 0.2], "Zahlen, Sprung 10–20 %"), summ(E[(E.jump >= 0.2) & (E.jump < 0.4)], "Zahlen, Sprung 20–40 %"),
             summ(E[E.jump >= 0.4], "Zahlen, Sprung ≥ 40 %"),
             summ(E[E["loc"] >= 0.75], "Zahlen, Schluss im oberen Viertel"), summ(E[E["loc"] < 0.75], "Zahlen, Schluss darunter")]
    yr = [summ(E[E.year == y], f"Zahlen-Sprünge {y}") for y in sorted(E.year.unique())]
    return ev, rows, yr


# ---------------- Schiene 1: Qualitaet ----------------
def quality_bt(P, t2c, revq):
    C, V = P["close"], P["volume"]
    dates = list(C.index)
    sma200 = C.rolling(200, min_periods=150).mean()
    r6 = C / C.shift(126) - 1
    dvol = (C * V).rolling(20, min_periods=15).mean()
    forms = [f"{y}-{m}-01" for y in range(2022, s.TODAY.year + 1) for m in ("05", "11")]
    forms = [f for f in forms if "2022-11-01" <= f < dates[-60]]
    idx = [next(i for i, d in enumerate(dates) if d >= f) for f in forms] + [len(dates) - 1]
    ys = range(2018, s.TODAY.year)
    revA = {y: merged(s.REV_TAGS, f"CY{y}") for y in ys}
    opA = {y: fr("OperatingIncomeLoss", f"CY{y}") for y in ys if y >= 2021}
    daA = {y: merged(["DepreciationDepletionAndAmortization", "DepreciationAndAmortization"], f"CY{y}") for y in ys if y >= 2021}
    shA = {y: fr("WeightedAverageNumberOfSharesOutstandingBasic", f"CY{y}", "shares") for y in ys if y >= 2019}
    eqI = {y: fr("StockholdersEquity", f"CY{y}Q4I") for y in ys if y >= 2021}
    caI = {y: fr("CashAndCashEquivalentsAtCarryingValue", f"CY{y}Q4I") for y in ys if y >= 2021}
    ltd, ltn, ltc = ({y: fr(t, f"CY{y}Q4I") for y in ys if y >= 2021} for t in ("LongTermDebt", "LongTermDebtNoncurrent", "LongTermDebtCurrent"))
    per, picks_all = [], []
    for k, F in enumerate(forms):
        i0, i1 = idx[k], idx[k + 1]
        Y = int(F[:4]) - 1
        qk = (Y, 4) if F[5:7] == "05" else (Y + 1, 2)
        fwd = C.iloc[i1] / C.iloc[i0] - 1
        liquid = (dvol.iloc[i0] >= 1e6) & (C.iloc[i0] >= 3) & fwd.notna()
        mom = r6.iloc[i0][liquid].rank(pct=True)
        grp = {"Wachstum": [], "Fundamental": [], "Alle 5": []}
        for sym in fwd.index[liquid]:
            c = t2c.get(sym)
            r1 = revA[Y].get(c) if c else None
            if not r1 or r1 < 50e6:
                continue
            base, n = revA[Y - 3].get(c), 3
            if not base:
                base, n = revA[Y - 2].get(c), 2
            if not base or (r1 / base) ** (1 / n) - 1 < s.CAGR_MIN:
                continue
            yoy = None
            for qq in (qk, prev_q(qk)):
                cur, b = revq.get(qq, {}).get(c), revq.get((qq[0] - 1, qq[1]), {}).get(c)
                if cur and b:
                    yoy = cur / b - 1
                    break
            if yoy is None or yoy < s.QYOY_MIN:
                continue
            grp["Wachstum"].append(sym)
            op, eq = opA[Y].get(c), eqI[Y].get(c)
            if op is None or eq is None or op <= 0:
                continue
            debt = max(ltd[Y].get(c, 0), ltn[Y].get(c, 0) + ltc[Y].get(c, 0))
            nd = debt - caI[Y].get(c, 0)
            ic = eq + nd
            if ic > 0 and op * (1 - s.TAX) / ic < s.ROIC_MIN:
                continue
            if nd > 0 and nd / (op + daA[Y].get(c, 0)) >= s.ND_EBITDA_MAX:
                continue
            s1, s0 = shA[Y].get(c), shA[Y - 2].get(c)
            if not s1 or not s0 or (s1 / s0) ** 0.5 - 1 > s.DILUTION_MAX:
                continue
            grp["Fundamental"].append(sym)
            if C.iloc[i0][sym] > sma200.iloc[i0][sym] and mom.get(sym, 0) >= s.MOM_PCT_MIN:
                grp["Alle 5"].append(sym)
        row = {"Start": dates[i0], "Ende": dates[i1], "Markt": fwd[liquid].mean()}
        for name, syms in grp.items():
            row[f"{name} N"], row[name] = len(syms), fwd[syms].mean() if syms else np.nan
        per.append(row)
        picks_all += [(dates[i0], x, fwd[x]) for x in grp["Alle 5"]]
    return per, pd.DataFrame(picks_all, columns=["start", "sym", "ret"])


def main():
    P = load_panel()
    meta, t2c = sec_meta()
    dates = list(P["close"].index)
    ev, rows, yr = breakout_bt(P, meta, t2c)
    years = range(2020, s.TODAY.year + 1)
    per, picks = quality_bt(P, t2c, quarterly(s.REV_TAGS, years))
    picks.to_csv(f"{OUT}/ruecktest_qualitaet_titel.csv", index=False)
    qd = pd.DataFrame(per)
    tot = {"Start": "Gesamt (verkettet)", "Ende": ""}
    for c in ("Markt", "Wachstum", "Fundamental", "Alle 5"):
        tot[c] = (1 + qd[c].fillna(0)).prod() - 1
        if c != "Markt":
            tot[f"{c} N"] = int(qd[f"{c} N"].sum())
    qrows = [{k: (int(v) if k.endswith(" N") else v) for k, v in r.items()} for r in per] + [tot]
    qcols = ["Start", "Ende", "Markt", "Wachstum N", "Wachstum", "Fundamental N", "Fundamental", "Alle 5 N", "Alle 5"]
    rep = [f"# Rücktest vom {s.TODAY.isoformat()}", "",
           f"Daten: {P['close'].shape[1]} heute gelistete US-Aktien, {dates[0]} bis {dates[-1]}. "
           "Pleiten und übernommene Firmen fehlen, die Ergebnisse sind deshalb eher zu günstig.", "",
           "## Schiene 2: Ausbruch (Sprung ≥ 10 % bei ≥ 3-fachem Volumen)", "",
           "Renditen ab Eröffnung des Folgetags. „Über Markt“ = Abstand zum Durchschnitt aller Aktien im selben Zeitraum. "
           "Regel A: Stopp am Tief des Sprungtages (höchstens −15 %), Verkauf nach 60 Tagen. "
           "Regel B: gleicher Stopp, Verkauf bei Schluss unter der 50-Tage-Linie, spätestens nach 120 Tagen. "
           f"Beide nach {COST * 100:.1f} % Kosten.", "", md(rows), "", "### Nach Jahren", "", md(yr), "",
           "## Schiene 1: Qualität (Auswahl jeweils im Mai und November, 6 Monate gehalten)", "",
           md([{c: r.get(c, "") for c in qcols} for r in qrows]), "",
           f"Einzeltitel der Auswahl „Alle 5“: {len(picks)}, davon ≥ +25 %: {(picks.ret >= 0.25).mean() * 100:.0f} %, "
           f"≤ −20 %: {(picks.ret <= -0.2).mean() * 100:.0f} %, Median {picks.ret.median() * 100:.1f} %.", ""]
    open(f"{OUT}/ruecktest.md", "w").write("\n".join(rep))
    print("\n".join(rep))


if __name__ == "__main__":
    main()
