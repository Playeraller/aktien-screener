"""Depot-Simulation: so tun, als haette man ab einem Stichtag jedes A-/A+-Signal gekauft.

Aufruf: python3 depot.py      (braucht data/panel.pkl und output/ruecktest_ereignisse.csv aus backtest.py)

Regeln: Startkapital 10.000, je Signal 4 % des aktuellen Depotwerts (hoechstens 25 Positionen, sonst wird
das Signal ausgelassen), Kauf zur naechsten Eroeffnung, Stopp am Tief des Sprungtages (max. -15 %),
Verkauf nach 60 Handelstagen, 0,4 % Kosten je Kauf+Verkauf. Vergleich: Durchschnitt der liquiden Aktien.
"""
import numpy as np, pandas as pd
import backtest as b
from scan import tier
from common import OUT

START, SIZE, HOLD = 10000.0, 0.04, 60


def market(P):
    C = P["close"]
    liq = ((C >= 3) & ((C * P["volume"]).rolling(20).mean() >= 1e6)).shift(1).fillna(False)
    return C.pct_change(fill_method=None).where(liq).mean(axis=1).fillna(0)


def run(ev, P, d0, d1, tiers=("A", "A+")):
    O, L, C = P["open"].values, P["low"].values, P["close"].values
    dates = list(P["close"].index)
    col = {x: j for j, x in enumerate(P["close"].columns)}
    i0 = next(i for i, d in enumerate(dates) if d >= d0)
    i1 = max(i for i, d in enumerate(dates) if d <= d1)
    sig = {}
    for r in ev[ev.stufe.isin(tiers)].itertuples():
        if i0 <= r.i + 1 <= i1:
            sig.setdefault(r.i + 1, []).append(r)
    cash, pos, curve, trades, skipped, inv = START, [], [], [], 0, []
    for j in range(i0, i1 + 1):
        eq_prev = cash + sum(p["sh"] * p["last"] for p in pos)
        for r in sig.get(j, []):                                   # Kaeufe zur Eroeffnung
            c = col[r.sym]; entry = O[j, c]
            if not entry > 0 or entry <= r.low:
                continue
            amt = SIZE * eq_prev
            if amt > cash or len(pos) >= int(1 / SIZE):
                skipped += 1
                continue
            cash -= amt
            pos.append(dict(sym=r.sym, c=c, j0=j, entry=entry, sh=amt * (1 - b.COST) / entry, last=entry,
                            stop=max(r.low, entry * 0.85), stufe=r.stufe, date=dates[j]))
        keep = []
        for p in pos:
            o, l, cl, c = O[j, p["c"]], L[j, p["c"]], C[j, p["c"]], p["c"]
            ex = None
            if not np.isnan(cl):
                if j > p["j0"] and o <= p["stop"]:
                    ex = o
                elif l <= p["stop"]:
                    ex = p["stop"]
                elif j - p["j0"] >= HOLD:
                    ex = cl
                else:
                    p["last"] = cl
            if ex is not None:
                cash += p["sh"] * ex
                trades.append(dict(sym=p["sym"], stufe=p["stufe"], kauf=p["date"], verkauf=dates[j],
                                   rendite=p["sh"] * ex / (p["sh"] * p["entry"] / (1 - b.COST)) - 1, offen=False))
            else:
                keep.append(p)
        pos = keep
        eq = cash + sum(p["sh"] * p["last"] for p in pos)
        curve.append(eq); inv.append(1 - cash / eq)
    for p in pos:
        trades.append(dict(sym=p["sym"], stufe=p["stufe"], kauf=p["date"], verkauf="offen",
                           rendite=p["last"] * (1 - b.COST) / p["entry"] - 1, offen=True))
    return pd.Series(curve, index=dates[i0:i1 + 1]), pd.DataFrame(trades), skipped, float(np.mean(inv))


def main():
    P = b.load_panel()
    ev = pd.read_csv(f"{OUT}/ruecktest_ereignisse.csv")
    ev["earn"] = ev.earn.map({True: True, False: False, "True": True, "False": False})
    ev["stufe"] = [tier(r) for r in ev.itertuples()]
    dates = list(P["close"].index)
    mk = market(P)
    last = dates[-1]
    wins = [(f"{y}-{m}-15", f"{y + (m == '11')}-{'05' if m == '11' else '11'}-14") for y in range(2022, 2027) for m in ("05", "11")]
    wins = [(a, min(z, last)) for a, z in wins if a < last]
    rows, detail = [], None
    for a, z in wins:
        cv, tr, sk, inv = run(ev, P, a, z)
        m = (1 + mk[cv.index[0]:cv.index[-1]].iloc[1:]).prod() - 1
        dd = (cv / cv.cummax() - 1).min()
        rows.append({"Start": a, "Ende": z, "Depot": cv.iloc[-1] / START - 1, "Markt": m,
                     "Abstand": cv.iloc[-1] / START - 1 - m, "Markt × Investitionsgrad": m * inv,
                     "Größter Rückgang": dd, "Käufe": len(tr), "ausgelassen": sk,
                     "Gewinner": (tr.rendite > 0).mean() if len(tr) else np.nan, "Ø investiert": inv})
        if (a, z) == wins[-1]:
            detail = (cv, tr, m)
    df = pd.DataFrame(rows)
    # Regeln nur mit Daten vor dem Stichtag pruefen
    cut = wins[-1][0]
    oos = []
    for st in ("A+", "A", "Meiden", "–"):
        for lab, d in (("bis " + cut, ev[(ev.stufe == st) & (ev.date < cut)]), ("ab " + cut, ev[(ev.stufe == st) & (ev.date >= cut)])):
            oos.append({"Stufe": st, "Zeitraum": lab, "Fälle": len(d), "davon 60 Tage abgelaufen": int(d.exc60.notna().sum()),
                        "Abstand zum Markt 60 T.": d.exc60.mean(), "Regel A Ø": d.r1.mean(),
                        "Abstand 20 T.": d.exc20.mean()})
    oos = pd.DataFrame(oos)
    cv, tr, m = detail
    tr = tr.sort_values("rendite", ascending=False)
    tr.to_csv(f"{OUT}/depot_kaeufe.csv", index=False)
    cv.to_csv(f"{OUT}/depot_kurve.csv", header=["depot"])
    pc = lambda x: "k.A." if pd.isna(x) else f"{x * 100:+.1f} %"
    def table(d, pcols):
        h = list(d.columns)
        out = ["| " + " | ".join(h) + " |", "|" + "---|" * len(h)]
        for r in d.itertuples(index=False):
            out.append("| " + " | ".join(pc(v) if k in pcols else str(v) for k, v in zip(h, r)) + " |")
        return "\n".join(out)
    pcols = {"Depot", "Markt", "Abstand", "Markt × Investitionsgrad", "Größter Rückgang", "Gewinner", "Ø investiert",
             "Abstand zum Markt 60 T.", "Regel A Ø", "Abstand 20 T.", "rendite"}
    top = pd.concat([tr.head(8), tr.tail(8)])[["sym", "stufe", "kauf", "verkauf", "rendite"]]
    rep = ["# Depot-Simulation: jedes A-/A+-Signal gekauft", "",
           f"Regeln: Startkapital {START:,.0f}, je Signal {SIZE * 100:.0f} % des Depotwerts, höchstens {int(1 / SIZE)} Positionen, "
           f"Stopp am Tief des Sprungtages (max. −15 %), Verkauf nach {HOLD} Handelstagen, {b.COST * 100:.1f} % Kosten je Kauf und Verkauf.",
           "", f"## Letztes Halbjahr ({wins[-1][0]} bis {wins[-1][1]})", "",
           f"Depot {pc(cv.iloc[-1] / START - 1)} (Endwert {cv.iloc[-1]:,.0f}), Markt {pc(m)}. {len(tr)} Käufe, davon {int(tr.offen.sum())} noch offen, "
           f"{pc((tr.rendite > 0).mean())[1:]} im Plus, Median je Kauf {pc(tr.rendite.median())}.", "",
           "Beste und schlechteste Käufe:", "", table(top, pcols), "",
           "## Alle Halbjahre seit 2022", "", table(df, pcols), "",
           f"## Hätten die Regeln schon vor dem {cut} gegolten?", "", table(oos, pcols), ""]
    open(f"{OUT}/depot.md", "w").write("\n".join(rep))
    print("\n".join(rep))


if __name__ == "__main__":
    main()
