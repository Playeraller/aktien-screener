"""Abschlussgrafik: Depotkurve der Kursstaerke-Strategie (1a) gegen Markt und IWM, Start = 100.

python3 grafik.py     -> output/depotkurve.png und output/depotkurve.csv (Tabellenansicht der Kurven)
Oben der Entwicklungszeitraum, unten der Abschlusstest. Kosten 0,4 % bei der Strategie, Markt und IWM ohne Kosten.
"""
import os, numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates
import matplotlib.pyplot as plt
import strategie as S
from common import OUT

SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
FARBE = {"Kursstärke 12 Monate": "#2a78d6", "Markt (alle handelbaren Aktien)": "#eb6834", "IWM": "#1baf7a"}


def kurven(abschluss):
    D = S.Daten(abschluss=abschluss)
    sel = S.top(S.kurs_kennzahlen(D)["m12"], D.LIQ, 0.10)
    strat, _ = S.kurve(D, sel, S.KOSTEN[0])
    markt, _ = S.kurve(D, D.LIQ)
    roh = pd.read_csv(os.path.join(S.ETF, "IWM.csv"), index_col=0).reindex(D.tage)
    iwm = pd.Series(D.etf["IWM_tag"], index=D.tage).loc[strat.index] / roh["open"].bfill().iloc[D.e[0]]
    # Strategie und Markt starten bei 1,0 zur Eroeffnung des ersten Kauftags, IWM ebenso (wie in strategie.py)
    df = pd.DataFrame({"Kursstärke 12 Monate": strat, "Markt (alle handelbaren Aktien)": markt.reindex(strat.index),
                       "IWM": iwm})
    return (df * 100).ffill()


def zeichne(ax, df, titel, marke=None):
    ax.set_facecolor(SURF)
    x = pd.to_datetime(df.index)
    for name, c in FARBE.items():
        ax.plot(x, df[name], color=c, lw=2, solid_capstyle="round", solid_joinstyle="round")
    ende = df.iloc[-1]
    lo_y, hi_y = ax.get_ylim()
    luecke = (hi_y - lo_y) * 0.075
    lage, letzte = {}, None
    for name, v in sorted(ende.items(), key=lambda kv: kv[1]):      # Endbeschriftungen von unten, mit Mindestabstand
        lage[name] = v if letzte is None else max(v, letzte + luecke)
        letzte = lage[name]
    for name, v in ende.items():
        ax.scatter([x[-1]], [v], s=40, color=FARBE[name], edgecolor=SURF, linewidth=2, zorder=5)
        ax.annotate(f"{name.split(' (')[0]}  {v - 100:+.0f} %", (x[-1], v), xytext=(x[-1] + pd.Timedelta(days=(x[-1] - x[0]).days * 0.03), lage[name]),
                    textcoords="data", va="center", fontsize=9, color=INK2, annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=GRID, lw=1, shrinkA=0, shrinkB=4) if abs(lage[name] - v) > 1e-9 else None)
    if marke:
        ax.axvline(pd.Timestamp(marke), color=INK2, lw=1, alpha=.6)
        ax.annotate("1.11.2025", (pd.Timestamp(marke), ax.get_ylim()[1]), xytext=(4, -12), textcoords="offset points",
                    fontsize=8, color=INK2)
    ax.axhline(100, color=GRID, lw=1, zorder=0)
    ax.grid(axis="y", color=GRID, lw=1)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %y" if marke else "%Y"))
    ax.set_title(titel, loc="left", fontsize=11, color=INK, pad=8)


def main():
    dev, abs_ = kurven(False), kurven(True)
    pd.concat({"entwicklung": dev, "abschlusstest": abs_}, names=["zeitraum", "datum"]).round(2).to_csv(
        os.path.join(OUT, "depotkurve.csv"))
    fig, axs = plt.subplots(2, 1, figsize=(10, 8.2), dpi=200, facecolor=SURF)
    fig.subplots_adjust(left=.07, right=.78, top=.84, hspace=.34, bottom=.07)
    zeichne(axs[0], dev, "Entwicklungszeitraum Dez 2017 – Apr 2025 (Regeln darauf gefunden)")
    zeichne(axs[1], abs_, "Abschlusstest Mai 2025 – Nov 2026 (einmalig gerechnet)", marke="2025-11-01")
    fig.text(.07, .95, "Kursstärke über 12 Monate: Der Vorsprung im Abschlusstest ist fast aufgebraucht",
             fontsize=13, color=INK, weight="bold")
    fig.text(.07, .92, "Depotwert, Start = 100. Strategie nach 0,4 % Kosten; Markt und IWM ohne Kosten und ohne Dividenden. "
             "Jeder Teil hat eine eigene Skala.", fontsize=9, color=INK2)
    fig.text(.07, .895, "Abschlusstest: Vorsprung vor dem Markt Anfang Nov 2025 rund 31 Punkte, Höchststand 51 Punkte (Mai 2026), am Ende 4.",
             fontsize=9, color=INK2)
    fig.savefig(os.path.join(OUT, "depotkurve.png"), facecolor=SURF)
    print(abs_.iloc[-1].round(1).to_dict(), dev.iloc[-1].round(1).to_dict())


if __name__ == "__main__":
    main()
