"""Woechentlicher Probelauf (ohne Geld): Kurse laden, Ausbrueche suchen, Signale protokollieren und auswerten.

Aufruf: python3 weekly.py
Ergebnis: protokoll/signale.csv (A, A+ und Meiden), protokoll/abgeschlossen.csv (Faelle nach 60 Handelstagen,
einmal festgeschrieben), protokoll/stand.md, output/ausbrueche.md

Die Auswertung von A+ folgt den vorab festgelegten Regeln in THEORIE.md, Abschnitt "Pruefung". Nicht aendern.
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
DONE = os.path.join(LOG, "abgeschlossen.csv")
DONE_COLS = ["date", "sym", "stufe", "einstieg", "schluss", "rendite", "markt", "hinweis"]
STUFEN = ["A", "A+", "Meiden"]
HALTEN = 60            # Handelstage
KOSTEN = 0.010         # festgelegt in THEORIE.md: 1,0 % je Kauf und Verkauf zusammen
START_APLUS = "2026-11-03"
ERSTE_AUSWERTUNG = 40


def pkt(x):
    return f"{x * 100:+.1f}".replace(".", ",")


def auswerten(log, P, done):
    """Rechnet laufende Faelle und schreibt abgeschlossene fest. Gibt (Tabelle laufend, done) zurueck.

    Einstieg zur Eroeffnung am Folgetag, Schlusskurs 60 Handelstage spaeter, Markt = Durchschnitt der Aktien,
    die am Einstiegstag handelbar sind (wie backtest.add_forward). Ein abgeschlossener Fall wird nie neu gerechnet.
    """
    O, C, L, V = P["open"], P["close"], P["low"], P["volume"]
    dates = list(C.index)
    pos = {d: i for i, d in enumerate(dates)}
    liq = ((C * V).shift(1).rolling(20, min_periods=15).mean() >= 1e6) & (C >= 3)
    fest = set(zip(done.date, done.sym))
    rows, neu = [], []
    for r in log.itertuples():
        if (r.date, r.sym) in fest or r.date not in pos or pos[r.date] + 1 >= len(dates):
            continue
        j0 = pos[r.date] + 1
        j1 = min(j0 + HALTEN, len(dates) - 1)
        fertig = j1 - j0 == HALTEN
        o0 = O.iloc[j0].where(O.iloc[j0] > 0)
        m = (C.iloc[j1] / o0 - 1)[liq.iloc[j0]].mean()
        entry = o0[r.sym] if r.sym in C.columns else np.nan
        ende = C[r.sym].iloc[j1] if r.sym in C.columns else np.nan
        if fertig:
            if entry > 0 and ende > 0:
                neu.append([r.date, r.sym, r.stufe, entry, ende, ende / entry - 1, m, ""])
            else:
                # Kein Kurs am Tag 60 (Uebernahme, Boersenabgang, Datenluecke): Fall bleibt sichtbar, zaehlt aber
                # nicht im Durchschnitt, weil die festgelegten Regeln dafuer nichts vorsehen.
                k = C[r.sym].iloc[j0:j1 + 1].dropna() if r.sym in C.columns else pd.Series(dtype=float)
                hinweis = f"kein Kurs am Tag 60, letzter Kurs {k.iloc[-1]:.2f} vom {k.index[-1]}" if len(k) else "keine Kursdaten"
                neu.append([r.date, r.sym, r.stufe, entry, np.nan, np.nan, m, hinweis])
            continue
        if not (entry > 0 and ende > 0):
            continue
        stop = max(r.low, entry * 0.85)
        hit = (L[r.sym].iloc[j0:j1 + 1] <= stop).any()
        ret = ende / entry - 1
        rows.append({"Datum": r.date, "Ticker": r.sym, "Stufe": r.stufe, "Tage": j1 - j0, "Rendite": ret, "Markt": m,
                     "Über Markt": ret - m, "Stopp ausgelöst": "ja" if hit else "nein"})
    if neu:
        add = pd.DataFrame(neu, columns=DONE_COLS)
        done = add if done.empty else pd.concat([done, add])
        done = done.sort_values(["date", "sym"]).reset_index(drop=True)
    return pd.DataFrame(rows), done


def tabelle(d):
    out = ["| " + " | ".join(d.columns) + " |", "|" + "---|" * len(d.columns)]
    for r in d.itertuples(index=False):
        out.append("| " + " | ".join(f"{x * 100:.1f} %" if isinstance(x, float) else str(x) for x in r) + " |")
    return out


def bericht(log, lauf, done, stand):
    """Text fuer protokoll/stand.md."""
    out = [f"# Probelauf-Stand {stand}", "", "Ohne Geld. Keine Kaufempfehlung.", ""]

    # ---- A+ nach der festgelegten Messgroesse ----
    ap = log[(log.stufe == "A+") & (log.date >= START_APLUS)]
    dA = done[(done.stufe == "A+") & (done.date >= START_APLUS)]
    ok, ohne = dA[dA.rendite.notna()], dA[dA.rendite.isna()]
    exc = (ok.rendite - ok.markt).sort_values(ascending=False)
    n = len(exc)
    out += ["## A+ (festgelegte Auswertung, siehe THEORIE.md „Prüfung“)", "",
            f"- A+-Signale seit {START_APLUS}: {len(ap)}",
            f"- Abgeschlossene 60-Tage-Fälle: {n} (erste Auswertung bei {ERSTE_AUSWERTUNG}, zweite bei {2 * ERSTE_AUSWERTUNG})"]
    if n:
        out.append(f"- Durchschnitt über Markt nach 1,0 % Kosten: {pkt(exc.mean() - KOSTEN)} Punkte")
    else:
        out.append("- Durchschnitt über Markt nach 1,0 % Kosten: noch kein abgeschlossener Fall")
    if n > 3:
        out.append(f"- Derselbe Wert ohne die drei besten Fälle: {pkt(exc.iloc[3:].mean() - KOSTEN)} Punkte")
    else:
        out.append("- Derselbe Wert ohne die drei besten Fälle: erst ab 4 abgeschlossenen Fällen")
    offen = len(ap) - len(dA)
    lfd = int((lauf.Stufe == "A+").sum()) if len(lauf) else 0
    out.append(f"- Noch nicht abgeschlossen: {offen}, davon mit laufendem Kurs: {lfd}")
    if offen - lfd:
        out.append(f"- {offen - lfd} A+-Signal(e) derzeit ohne Kurs (Einstieg steht noch aus, Kursdaten fehlen oder "
                   "Signal älter als das Kursfenster). Bleibt das so, fehlen sie in der Auswertung.")
    if len(ohne):
        out.append(f"- **Achtung:** {len(ohne)} Fall/Fälle ohne Kurs am Tag 60, nicht im Durchschnitt: "
                   + "; ".join(f"{r.sym} ({r.date}: {r.hinweis})" for r in ohne.itertuples())
                   + ". Dafür gibt es keine festgelegte Regel.")
    if n < ERSTE_AUSWERTUNG:
        out.append(f"- Vor {ERSTE_AUSWERTUNG} Fällen sind die Zahlen kein Urteil. Wenige Fälle schwanken stark.")
    if n:
        t = ok.assign(ueber=ok.rendite - ok.markt, netto=ok.rendite - ok.markt - KOSTEN)
        t = t[["date", "sym", "rendite", "markt", "ueber", "netto"]]
        t.columns = ["Datum", "Ticker", "Rendite", "Markt", "Über Markt", "Nach 1,0 % Kosten"]
        out += [""] + tabelle(t)

    # ---- Meiden: nur Beobachtung ----
    me = log[log.stufe == "Meiden"]
    dM = done[(done.stufe == "Meiden") & done.rendite.notna()]
    out += ["", "## Meiden (Sprung ≥ 40 % ohne Quartalszahlen, nur Beobachtung, nie kaufen)", "",
            f"- Protokollierte Meiden-Signale: {len(me)} (mitgeschrieben ab Mitte November 2026)",
            f"- Abgeschlossene 60-Tage-Fälle: {len(dM)}"]
    if len(dM):
        out.append(f"- Durchschnitt über Markt (ohne Kosten): {pkt((dM.rendite - dM.markt).mean())} Punkte")

    # ---- Zwischenstand der laufenden Faelle ----
    out += ["", "## Laufende Fälle (Zwischenstand, noch keine 60 Handelstage)", "",
            f"Protokollierte Signale: {len(log)}, abgeschlossen: {len(done)}, laufend: {len(lauf)}", ""]
    if len(lauf):
        k = lauf[lauf.Stufe.isin(["A", "A+"])]
        if len(k):
            out += [f"A und A+ zusammen: Rendite {k['Rendite'].mean() * 100:.1f} %, Markt {k['Markt'].mean() * 100:.1f} %, "
                    f"über Markt {k['Über Markt'].mean() * 100:.1f} Punkte, im Plus {(k['Rendite'] > 0).mean() * 100:.0f} %, "
                    f"Stopp ausgelöst bei {(k['Stopp ausgelöst'] == 'ja').mean() * 100:.0f} %", ""]
        out += tabelle(lauf)
    return out


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
    new = ev[ev.stufe.isin(STUFEN)][["date", "sym", "name", "stufe", "jump", "growth", "margin", "close", "low"]]
    # Alte Eintraege stehen vorn und gewinnen bei Dubletten: ein protokolliertes Signal wird nie ueberschrieben
    log = pd.concat([pd.read_csv(CSV), new]) if os.path.exists(CSV) else new
    log = log.drop_duplicates(["date", "sym"]).sort_values(["date", "sym"])
    log.to_csv(CSV, index=False)

    P = b.load_panel(tail=200)
    done = pd.read_csv(DONE) if os.path.exists(DONE) else pd.DataFrame(columns=DONE_COLS)
    done["hinweis"] = done["hinweis"].fillna("")
    lauf, done = auswerten(log, P, done)
    done.to_csv(DONE, index=False)
    out = bericht(log, lauf, done, P["close"].index[-1])
    open(os.path.join(LOG, "stand.md"), "w").write("\n".join(out) + "\n")
    print("\n".join(out[:12]))


if __name__ == "__main__":
    main()
