"""Hypothese 8: Was passiert nach grossen Tagesstuerzen? (Festlegung in UEBERGABE.md, vor der Rechnung)

python3 sturz.py     rechnet einmal, schreibt output/sturz.md und output/sturz.json

Ereignis: Schlusskurs >= 10 % unter Vortag bei >= 3-fachem Stueckumsatz (Schnitt der 20 Tage davor),
Vortag: Kurs >= 3 $, 20-Tage-Umsatz >= 1 Mio. $. Kauf zur Eroeffnung des Folgetags, gemessen wird der Abstand
zum Durchschnitt der liquiden Aktien nach 5, 20, 60 Handelstagen, abzueglich 0,4 % Kosten.
Je Aktie hoechstens ein Ereignis in 60 Handelstagen. Nur Daten bis 30.4.2025.
a) mit Quartalsmeldung (8-K 2.02) am selben Tag oder seit dem Vortag, b) ohne. Termine gibt es erst ab 6/2021.
"""
import os, json, bisect
import numpy as np, pandas as pd
import backtest as b
import strategie as st
from common import OUT

HS = (5, 20, 60)
KOSTEN = 0.004
MELDUNGEN_AB = "2021-06-01"
ABSTAND = 60


def ereignisse(P):
    C, V = P["close"], P["volume"].fillna(0)
    ret = C / C.shift(1) - 1
    vavg = V.shift(1).rolling(20, min_periods=15).mean()
    umsatz = (C * V).shift(1).rolling(20, min_periods=15).mean()
    mask = (ret <= -0.10) & (V >= 3 * vavg) & (vavg > 0) & (C.shift(1) >= 3) & (umsatz >= 1e6)
    ii, jj = np.where(mask.values)
    ev = pd.DataFrame({"i": ii, "sym": C.columns[jj], "date": C.index[ii], "ret": ret.values[ii, jj]})
    ev = ev.sort_values(["sym", "i"])
    keep, last = [], {}
    for r in ev.itertuples():
        ok = not (r.sym in last and r.i - last[r.sym] < ABSTAND)
        keep.append(ok)
        if ok:
            last[r.sym] = r.i
    return ev[keep].reset_index(drop=True)


def vorwaerts(ev, P):
    """Rendite Eroeffnung Folgetag bis Schluss h Tage spaeter, minus Durchschnitt der liquiden Aktien."""
    C, O, V = P["close"], P["open"], P["volume"].fillna(0)
    Cf, Ov = C.ffill().values, O.values
    n = Cf.shape[0]
    liq = ((C.shift(1) >= 3) & ((C * V).shift(1).rolling(20, min_periods=15).mean() >= 1e6)).values
    col = {x: j for j, x in enumerate(C.columns)}
    cj, i1 = ev.sym.map(col).values, ev.i.values + 1
    for h in HS:
        fw = np.full(Cf.shape, np.nan)
        fw[:n - h] = Cf[h:] / np.where(Ov[:n - h] > 0, Ov[:n - h], np.nan) - 1
        bench = np.nanmean(np.where(liq, fw, np.nan), axis=1)
        ok = i1 < n
        f, m = np.full(len(ev), np.nan), np.full(len(ev), np.nan)
        f[ok], m[ok] = fw[i1[ok], cj[ok]], bench[i1[ok]]
        ev[f"roh{h}"], ev[f"abst{h}"] = f, f - m - KOSTEN
    return ev


def gruppe(ev, tage, meta, t2c):
    """'mit' / 'ohne' Quartalsmeldung, 'unbekannt' ohne SEC-Zuordnung oder vor Beginn der Termine."""
    out = []
    for r in ev.itertuples():
        cik = t2c.get(r.sym)
        e = meta[cik].get("earnings") if cik else None
        if not e or r.date < MELDUNGEN_AB:
            out.append("unbekannt")
            continue
        vortag = tage[r.i - 1]
        k = bisect.bisect_left(e, vortag)
        out.append("mit" if k < len(e) and e[k] <= r.date else "ohne")
    ev["gruppe"] = out
    return ev


def kennzahlen(d, h):
    x = d[f"abst{h}"].dropna()
    if len(x) < 20:
        return {"n": int(len(x))}
    # Ereignisse haeufen sich an einzelnen Tagen: Unsicherheit ueber Monatsmittel statt ueber Einzelfaelle
    mon = x.groupby(d.loc[x.index, "date"].str[:7]).mean()
    t = float(mon.mean() / (mon.std(ddof=1) / np.sqrt(len(mon)))) if len(mon) > 3 else float("nan")
    return {"n": int(len(x)), "mittel": float(x.mean()), "median": float(x.median()), "plus": float((x > 0).mean()),
            "roh": float(d.loc[x.index, f"roh{h}"].mean()), "monate": int(len(mon)),
            "monate_plus": float((mon > 0).mean()), "t": t,
            "jahre": {y: [int(len(g)), float(g.mean())] for y, g in x.groupby(d.loc[x.index, "date"].str[:4])}}


def main():
    P = b.load_panel()
    st.bereinige(P)
    P = {k: v.loc[:st.DEV_END] for k, v in P.items()}        # nichts nach dem 30.4.2025 ansehen
    tage = list(P["close"].index)
    meta, t2c = b.sec_meta()
    ev = gruppe(vorwaerts(ereignisse(P), P), tage, meta, t2c)
    teile = {"a) mit Quartalszahlen (ab 6/2021)": ev[ev.gruppe == "mit"],
             "b) ohne Quartalszahlen (ab 6/2021)": ev[ev.gruppe == "ohne"],
             "nur zur Einordnung: alle Stürze 2016 bis 4/2025, ungetrennt": ev}
    erg = {"ereignisse": int(len(ev)), "gruppen": ev.gruppe.value_counts().to_dict(), "von": tage[0], "bis": tage[-1],
           "teile": {name: {str(h): kennzahlen(d, h) for h in HS} for name, d in teile.items()}}
    json.dump(erg, open(os.path.join(OUT, "sturz.json"), "w"), indent=1, ensure_ascii=False)

    pz = lambda v: f"{v * 100:+.1f} %".replace(".", ",")
    L = ["# Hypothese 8: nach großen Tagesstürzen", "",
         f"Zeitraum {tage[0]} bis {tage[-1]}, {len(ev)} Ereignisse "
         f"(mit Quartalszahlen {erg['gruppen'].get('mit', 0)}, ohne {erg['gruppen'].get('ohne', 0)}, "
         f"nicht zuzuordnen {erg['gruppen'].get('unbekannt', 0)}).",
         "Abstand = Rendite ab Eröffnung des Folgetags minus Durchschnitt der liquiden Aktien minus 0,4 % Kosten.",
         "Pleiten und Übernahmen fehlen in den Daten: „kaufen nach dem Sturz“ sieht deshalb zu gut aus.", ""]
    for name, k in erg["teile"].items():
        L += [f"## {name}", "", "| Tage | Fälle | Abstand Mittel | Median | Anteil im Plus | Monate im Plus | t-Wert |",
              "|---|---|---|---|---|---|---|"]
        for h in HS:
            z = k[str(h)]
            if "mittel" not in z:
                L.append(f"| {h} | {z['n']} | zu wenige | | | | |")
                continue
            L.append(f"| {h} | {z['n']} | {pz(z['mittel'])} | {pz(z['median'])} | {z['plus'] * 100:.0f} % | "
                     f"{z['monate_plus'] * 100:.0f} % von {z['monate']} | {z['t']:.1f} |".replace(".", ","))
        z = k["20"]
        if "jahre" in z:
            L += ["", "Nach 20 Tagen je Jahr: " + ", ".join(f"{y}: {pz(m)} ({n})" for y, (n, m) in z["jahre"].items())]
        L.append("")
    open(os.path.join(OUT, "sturz.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
