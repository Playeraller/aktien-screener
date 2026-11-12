"""Woechentlicher Probelauf (ohne Geld): Kurse laden, Ausbrueche suchen, A/A+-Signale protokollieren und auswerten.

Aufruf: python3 weekly.py      Ergebnis: protokoll/signale.csv, protokoll/stand.md, output/ausbrueche.md
"""
import os, datetime
import numpy as np, pandas as pd
import fetch_history as fh
import backtest as b
import scan
from common import BASE

LOG = os.path.join(BASE, "protokoll")
os.makedirs(LOG, exist_ok=True)
CSV = os.path.join(LOG, "signale.csv")


def main():
    # Ein frischer Container hat keine Kurshistorie: dann reichen 300 Tage statt 5 Jahre
    if len(os.listdir(fh.HIST)) < 1000:
        fh.START = (datetime.date.today() - datetime.timedelta(days=300)).isoformat()
        fh.run_prices()
    else:
        fh.run_update()
    if not os.path.exists(os.path.join(fh.DATA, "sec_meta.json")):
        fh.run_sec()
    ev = scan.main(7)
    new = ev[ev.stufe.isin(["A", "A+"])][["date", "sym", "name", "stufe", "jump", "growth", "margin", "close", "low"]]
    log = pd.concat([pd.read_csv(CSV), new]) if os.path.exists(CSV) else new
    log = log.drop_duplicates(["date", "sym"]).sort_values(["date", "sym"])
    log.to_csv(CSV, index=False)

    # Auswertung: Einstieg zur Eroeffnung am Folgetag, Stand heute bzw. nach 60 Handelstagen, Vergleich mit dem Markt
    P = b.load_panel(tail=200)
    O, C, L, V = P["open"], P["close"], P["low"], P["volume"]
    dates = list(C.index)
    liq = ((C * V).shift(1).rolling(20, min_periods=15).mean() >= 1e6) & (C >= 3)
    rows = []
    for r in log.itertuples():
        if r.date not in dates or r.sym not in C.columns or dates.index(r.date) + 1 >= len(dates):
            continue
        j0 = dates.index(r.date) + 1
        j1 = min(j0 + 60, len(dates) - 1)
        entry = O[r.sym].iloc[j0]
        if not entry > 0:
            continue
        stop = max(r.low, entry * 0.85)
        hit = (L[r.sym].iloc[j0:j1 + 1] <= stop).any()
        ret = C[r.sym].iloc[j1] / entry - 1
        m = (C.iloc[j1] / O.iloc[j0] - 1)[liq.iloc[j0]].mean()
        rows.append({"Datum": r.date, "Ticker": r.sym, "Stufe": r.stufe, "Tage": j1 - j0, "Rendite": ret, "Markt": m,
                     "Über Markt": ret - m, "Stopp ausgelöst": "ja" if hit else "nein"})
    d = pd.DataFrame(rows)
    out = [f"# Probelauf-Stand {dates[-1]}", "", f"Protokollierte Signale: {len(log)}, davon auswertbar: {len(d)}", ""]
    if len(d):
        out += [f"Durchschnitt: Rendite {d['Rendite'].mean() * 100:.1f} %, Markt {d['Markt'].mean() * 100:.1f} %, "
                f"über Markt {d['Über Markt'].mean() * 100:.1f} Punkte, im Plus {(d['Rendite'] > 0).mean() * 100:.0f} %, "
                f"Stopp ausgelöst bei {(d['Stopp ausgelöst'] == 'ja').mean() * 100:.0f} %", "",
                "| " + " | ".join(d.columns) + " |", "|" + "---|" * len(d.columns)]
        for r in d.itertuples(index=False):
            out.append("| " + " | ".join(f"{x * 100:.1f} %" if isinstance(x, float) else str(x) for x in r) + " |")
    open(os.path.join(LOG, "stand.md"), "w").write("\n".join(out) + "\n")
    print("\n".join(out[:5]))


if __name__ == "__main__":
    main()
