"""Ausbruchs-Scanner: Kurssprünge der letzten Tage, eingeordnet nach dem Ergebnis des Rücktests.

Aufruf: python3 scan.py [tage]     (Standard 7 Handelstage; vorher: python3 fetch_history.py update)

Stufen laut Rücktest 2022-2026 (Abstand zum Markt nach 60 Handelstagen):
  A+  Sprung >= 40 % nach Quartalszahlen                         ca. +13 Punkte, aber nur 162 Fälle
  A   nach Quartalszahlen, Umsatzwachstum >= 25 %, profitabel    ca. +4 Punkte, 476 Fälle
  –   übrige Sprünge                                             kein belegter Vorteil
  Meiden  Sprung >= 40 % ohne Quartalszahlen                     ca. -11 Punkte, jeder zweite verliert >= 20 %
"""
import sys
import pandas as pd
import backtest as b
import screener as s
from common import OUT, cache_save
from fetch_history import bt_universe, sec_one


def tier(r):
    if r.earn is True and r.jump >= 0.40:
        return "A+"
    if r.earn is True and (r.growth or 0) >= 0.25 and (r.margin or 0) > 0:
        return "A"
    if r.earn is False and r.jump >= 0.40:
        return "Meiden"
    return "–"


def main(days=7):
    P = b.load_panel(tail=200)
    C = P["close"]
    dates, n = list(C.index), len(C)
    ev = b.find_events(P)
    ev = ev[ev.i >= n - days].copy()
    meta, t2c = b.sec_meta()
    for cik in sorted({t2c[x] for x in ev.sym if x in t2c}):          # Meldetermine der Treffer auffrischen
        m = sec_one(cik)
        if m:
            meta[cik] = m
    cache_save("sec_meta.json", meta)
    years = range(s.TODAY.year - 2, s.TODAY.year + 1)
    ev = b.add_fundamentals(ev, dates, meta, t2c, b.quarterly(s.REV_TAGS, years), b.quarterly(["OperatingIncomeLoss"], years))
    uni = bt_universe()
    ev["name"] = [uni.get(x, {}).get("name", "")[:34] for x in ev.sym]
    ev["mcap"] = [uni.get(x, {}).get("mcap") for x in ev.sym]
    ev["now"] = [C[x].dropna().iloc[-1] for x in ev.sym]
    ev["since"] = ev.now / ev.close - 1
    ev["valid"] = ev.now > ev.low
    ev["stufe"] = [tier(r) for r in ev.itertuples()]
    order = {"A+": 0, "A": 1, "–": 2, "Meiden": 3}
    ev = ev.sort_values(["stufe", "jump"], key=lambda c: c.map(order) if c.name == "stufe" else -c)
    ev.to_csv(f"{OUT}/ausbrueche.csv", index=False)

    pc = lambda x: "k.A." if x is None or pd.isna(x) else f"{x * 100:.0f} %"
    head = ["Stufe", "Ticker", "Name", "Börsenwert", "Datum", "Sprung", "Volumen", "Nach Zahlen", "Umsatzwachstum",
            "Op. Marge", "Seit Sprung", "Stopp (Tief Sprungtag)", "Signal"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in ev.itertuples():
        lines.append("| " + " | ".join([
            r.stufe, r.sym, r.name, f"{r.mcap / 1e9:.1f} Mrd. $" if r.mcap else "k.A.", r.date, pc(r.jump), f"{r.volx:.0f}-fach",
            {True: "ja", False: "nein"}.get(r.earn, "unbekannt"), pc(r.growth), pc(r.margin), pc(r.since),
            f"{r.low:.2f} $", "gültig" if r.valid else "verfallen (unter Tief)"]) + " |")
    cnt = ev.stufe.value_counts().to_dict()
    rep = [f"# Ausbrüche der letzten {days} Handelstage (Stand {dates[-1]})", "",
           f"{len(ev)} Sprünge ≥ 10 % bei ≥ 3-fachem Volumen: " + ", ".join(f"{k}: {v}" for k, v in cnt.items()), "",
           "Regel: Einstieg nur bei A und A+, kleine Position, Stopp am Tief des Sprungtages (höchstens −15 % vom Einstieg), "
           "Verkauf nach 60 Handelstagen. Im Rücktest gewann nur etwa jeder dritte Kauf.", "",
           "Das Umsatzwachstum stammt aus dem jüngsten bei der SEC verfügbaren Quartal; direkt nach der Meldung ist das oft noch das Vorquartal.",
           "", "\n".join(lines), ""]
    open(f"{OUT}/ausbrueche.md", "w").write("\n".join(rep))
    print(f"{len(ev)} Sprünge, Stufen: {cnt} -> {OUT}/ausbrueche.md")
    return ev


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 7)
