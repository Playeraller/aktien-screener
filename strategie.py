"""Rangfolge-Ruecktest: monatlich alle liquiden Aktien nach einer Kennzahl ordnen, die besten kaufen,
gleich gewichten, immer voll investiert.

python3 strategie.py selbsttest    prueft den Ruecktest selbst (Zufallsauswahl, Auswahl mit Zukunftswissen)

Ablauf je Monat: Stichtag = letzter Handelstag des Monats (nur Daten bis zu diesem Schlusskurs),
Kauf und Verkauf zur Eroeffnung des naechsten Handelstags. Im Entwicklungsmodus werden alle Kurse nach
dem 30.04.2025 abgeschnitten, damit der Abschlusszeitraum nicht versehentlich angesehen wird.
"""
import os, sys, json, datetime
import numpy as np, pandas as pd
import backtest as b
from common import DATA, OUT, BASE
from fetch_history import ETF

DEV_START = "2017-12-01"     # erster Kauf: frueheste Kennzahl mit 12 Monaten Vorlauf (Kurse ab 11.11.2016)
DEV_END = "2025-04-30"       # Ende Entwicklungszeitraum, danach Abschlusstest
KOSTEN = (0.004, 0.010)      # je Kauf und Verkauf zusammen (wie COST in backtest.py), Normal- und Stressrechnung
MIN_KURS, MIN_UMSATZ = 3.0, 1e6
SPERRE = os.path.join(BASE, "protokoll", "abschlusstest.json")


# ---------------- Datenbereinigung ----------------
def bereinige(P):
    """Offensichtliche Datenfehler entfernen. Echte Kursstuerze (auch -90 % an einem Tag) bleiben drin.

    A) Ausreisser: Schlusskurs springt um mehr als Faktor 20 und ist binnen 10 Handelstagen wieder beim alten
       Niveau (Faktor 0,5 bis 2) -> diese Tage gelten als fehlend.
    B) Niveausprung nach oben um mehr als Faktor 20 ohne Rueckkehr (Platzhalterkurse vor der Notierung,
       Neustart nach Insolvenz) -> alles davor gilt als fehlend.
    Liefert die Zahl der Faelle (A, B)."""
    C = P["close"]
    r = (C / C.shift(1)).values
    cols = np.where(np.nansum((r > 20) | (r < 0.05), axis=0) > 0)[0]
    na = nb = 0
    for j in cols:
        c = C.iloc[:, j].values.copy()
        kill = np.zeros(len(c), bool)
        last = np.nan                                  # letzter gueltiger Kurs
        i = 0
        while i < len(c):
            if np.isnan(c[i]):
                i += 1
                continue
            if last == last and (c[i] / last > 20 or c[i] / last < 0.05):
                back = [k for k in range(i + 1, min(i + 11, len(c))) if c[k] == c[k] and 0.5 < c[k] / last < 2]
                if back:                               # A) Ausreisser
                    kill[i:back[0]] = True
                    na += 1
                    i = back[0]
                    continue
                if c[i] / last > 20:                   # B) Niveausprung nach oben
                    kill[:i] = True
                    nb += 1
            last = c[i]
            i += 1
        if kill.any():
            for k in b.FIELDS:
                col = P[k].iloc[:, j].values.copy()
                col[kill] = np.nan
                P[k].iloc[:, j] = col
    return na, nb


# ---------------- Daten je Monat ----------------
class Daten:
    """Kurse und daraus abgeleitete Monatsmatrizen. Zeilen = Halteperioden, Spalten = Aktien."""

    def __init__(self, abschluss=False):
        P = b.load_panel()
        self.fehler = bereinige(P)
        alle_tage = list(P["close"].index)
        # Monatsenden aus dem vollen Kalender bestimmen, danach erst abschneiden
        monatsende = {d for d, n in zip(alle_tage, alle_tage[1:]) if d[:7] != n[:7]}
        if not abschluss:
            P = {k: v.loc[:DEV_END] for k, v in P.items()}
        self.abschluss = abschluss
        C, O, V = P["close"], P["open"], P["volume"].fillna(0)
        self.tage = list(C.index)
        self.sym = list(C.columns)
        self.C, self.O = C.values, O.values
        self.Cf = C.ffill().values                     # Bewertung an Tagen ohne Handel: letzter Kurs
        Ob = O.bfill().values                          # Ausfuehrung an Tagen ohne Handel: naechste Eroeffnung
        umsatz = (C * V).fillna(0)
        liq = ((C >= MIN_KURS) & (umsatz.rolling(20).mean() >= MIN_UMSATZ) & ((V > 0).rolling(20).sum() >= 15)
               & (V > 0)).values
        self.umsatz20_tag = umsatz.rolling(20).mean().values
        start = TEST_START if abschluss else DEV_START
        T = len(self.tage) - 1
        # Stichtage s (Monatsende) mit Kauftag e = s + 1 im Zeitraum
        self.s = [i for i, d in enumerate(self.tage) if d in monatsende and i + 1 <= T and self.tage[i + 1] >= start]
        self.e = [i + 1 for i in self.s]
        K = len(self.s)
        self.ende = self.e[1:] + [T]                   # letzte Periode endet am Schlusskurs des letzten Tages
        px0 = Ob[self.e]
        px1 = np.vstack([Ob[self.e[k + 1]] if k + 1 < K else self.Cf[T] for k in range(K)])
        px1 = np.where(np.isnan(px1), self.Cf[self.ende], px1)
        self.px0 = px0
        self.R = px1 / px0 - 1                         # Rendite je Periode, Eroeffnung bis Eroeffnung
        self.LIQ = liq[self.s] & np.isfinite(self.R)
        self.umsatz20 = self.umsatz20_tag[self.s]
        self.R = np.nan_to_num(self.R)
        self.jahre = (datetime.date.fromisoformat(self.tage[T]) - datetime.date.fromisoformat(self.tage[self.e[0]])).days / 365.25
        # Halbjahre: Mai bis Oktober und November bis April, benannt nach dem ersten Monat
        self.hj = []
        for i in self.e:
            y, m = int(self.tage[i][:4]), int(self.tage[i][5:7])
            self.hj.append(f"{y}-05" if 5 <= m <= 10 else f"{y}-11" if m >= 11 else f"{y - 1}-11")
        self.hj = np.array(self.hj)
        self.hj_namen = list(dict.fromkeys(self.hj))
        self.etf = {}
        for x in ("IWM", "SPY"):
            df = pd.read_csv(os.path.join(ETF, f"{x}.csv"), index_col=0).reindex(self.tage)
            o, c = df["open"].bfill().values, df["close"].ffill().values
            self.etf[x] = np.array([(o[self.e[k + 1]] if k + 1 < K else c[T]) / o[self.e[k]] - 1 for k in range(K)])
            self.etf[x + "_tag"] = c

    def tagesmatrix(self, df_func):
        """Hilfe fuer Kennzahlen: liefert Matrix [Perioden x Aktien] aus einer Tagesmatrix am Stichtag."""
        return df_func[self.s]


TEST_START = "2025-05-01"


# ---------------- Rechenkern ----------------
def top(score, liq, anteil=0.10):
    """Beste `anteil` der liquiden Aktien mit gueltiger Kennzahl je Periode -> Auswahlmatrix (bool)."""
    sel = np.zeros(liq.shape, bool)
    for k in range(liq.shape[0]):
        ok = np.where(liq[k] & np.isfinite(score[k]))[0]
        if len(ok) == 0:
            continue
        n = max(1, int(round(anteil * len(ok))))
        sel[k, ok[np.argsort(-score[k, ok], kind="stable")[:n]]] = True
    return sel


def lauf(D, sel, kosten=0.0):
    """Monatsrenditen eines gleich gewichteten Depots aus der Auswahlmatrix, nach Kosten.

    Kosten fallen auf den tatsaechlich umgeschichteten Anteil an (auch das Zurueckstellen auf gleiche Gewichte).
    Liefert (Nettorendite je Periode, Umschlag je Periode als Anteil des Depots)."""
    n = sel.sum(1, keepdims=True)
    W = sel / np.maximum(n, 1)
    brutto = (W * D.R).sum(1)
    drift = W * (1 + D.R) / (1 + brutto)[:, None]      # Gewichte am Periodenende vor dem Umschichten
    um = np.empty(len(brutto))
    um[0] = 0.5                                        # Erstkauf: nur die Kaufseite
    um[1:] = 0.5 * np.abs(W[1:] - drift[:-1]).sum(1)
    return (1 + brutto) * (1 - kosten * um) - 1, um


def halbjahre(D, r):
    """Rendite je Halbjahr aus Periodenrenditen."""
    return np.array([np.prod(1 + r[D.hj == h]) - 1 for h in D.hj_namen])


def gesamt(r):
    return float(np.prod(1 + r) - 1)


def pa(D, r):
    """Rendite pro Jahr."""
    return float(np.prod(1 + r) ** (1 / D.jahre) - 1)


def ohne_beste3(D, sel):
    """Auswahl ohne die drei Aktien mit dem groessten Beitrag je Halbjahr."""
    out = sel.copy()
    beitrag = sel / np.maximum(sel.sum(1, keepdims=True), 1) * D.R
    for h in D.hj_namen:
        ks = np.where(D.hj == h)[0]
        best = np.argsort(beitrag[ks].sum(0))[-3:]
        out[np.ix_(ks, best)] = False
    return out


def kurve(D, sel, kosten=0.0):
    """Depotwert je Handelstag (Start 1,0 zur ersten Eroeffnung), fuer Grafik und groessten Rueckgang."""
    r, um = lauf(D, sel, kosten)
    brutto = (1 + r) / (1 - kosten * um)
    wert, v = np.full(len(D.tage), np.nan), 1.0
    for k in range(len(D.e)):
        v *= 1 - kosten * um[k]
        cols = np.where(sel[k])[0]
        a, z = D.e[k], (D.e[k + 1] if k + 1 < len(D.e) else len(D.tage))
        wert[a:z] = v * np.nanmean(D.Cf[a:z][:, cols] / D.px0[k, cols], axis=1)
        v *= brutto[k]
    return pd.Series(wert, index=D.tage).dropna(), v


def rueckgang(s):
    """Groesster Rueckgang vom Hoechststand."""
    return float((s / s.cummax() - 1).min())


def bewertung(D, sel, kosten=KOSTEN[0]):
    """Kennzahlen und Pruefregeln fuer eine Auswahl. Vergleich: Markt (alle liquiden, ohne Kosten) und IWM."""
    r, um = lauf(D, sel, kosten)
    markt, _ = lauf(D, D.LIQ)
    iwm = D.etf["IWM"]
    h, hm, hi = halbjahre(D, r), halbjahre(D, markt), halbjahre(D, iwm)
    r3, _ = lauf(D, ohne_beste3(D, sel), kosten)
    vorn = int(((h > hm) & (h > hi)).sum())
    noetig = int(np.ceil(len(h) * 2 / 3))
    return {"pa": pa(D, r), "markt_pa": pa(D, markt), "iwm_pa": pa(D, iwm), "gesamt": gesamt(r),
            "markt_gesamt": gesamt(markt), "umschlag": float(um[1:].mean()), "titel": float(sel.sum(1).mean()),
            "hj": h, "hj_markt": hm, "hj_iwm": hi, "vorn": vorn, "vorn_markt": int((h > hm).sum()), "noetig": noetig,
            "ohne3_pa": pa(D, r3), "ohne3_ok": gesamt(r3) > gesamt(markt),
            "bestanden": vorn >= noetig and gesamt(r3) > gesamt(markt)}


# ---------------- Abschlusstest-Sperre ----------------
def abschluss_freigabe(name):
    """Jede Strategie darf genau einmal in den Abschlusstest, insgesamt hoechstens 3. Wird protokolliert."""
    log = json.load(open(SPERRE)) if os.path.exists(SPERRE) else {}
    if name in log:
        raise SystemExit(f"Abschlusstest fuer '{name}' ist schon gelaufen ({log[name]['datum']}). Kein zweiter Lauf.")
    if len(log) >= 3:
        raise SystemExit("Es sind schon 3 Finalisten im Abschlusstest gewesen. Kein weiterer Lauf.")
    log[name] = {"datum": datetime.date.today().isoformat()}
    json.dump(log, open(SPERRE, "w"), indent=1)
    return log


# ---------------- Selbsttest ----------------
def pz(x, n=1):
    return f"{x * 100:+.{n}f} %".replace(".", ",")


def kz(x, n=1):
    return f"{x:.{n}f}".replace(".", ",")


def selbsttest(laeufe=500):
    D = Daten()
    K, N = D.R.shape
    out = []
    w = out.append
    markt, _ = lauf(D, D.LIQ)
    iwm, spy = D.etf["IWM"], D.etf["SPY"]
    w("# Selbsttest des Rücktests\n")
    w(f"Zeitraum {D.tage[D.e[0]]} bis {D.tage[-1]} ({kz(D.jahre)} Jahre, {K} Monate, {len(D.hj_namen)} Halbjahre). "
      f"Je Monat im Schnitt {D.LIQ.sum(1).mean():.0f} liquide Aktien (von {D.LIQ.sum(1).min()} bis {D.LIQ.sum(1).max()}). "
      f"Bereinigte Datenfehler: {D.fehler[0]} Ausreißer, {D.fehler[1]} Niveausprünge.\n")

    # 0) Buchhaltung
    w("## 0. Stimmt die Buchhaltung?\n")
    j = D.sym.index("AAPL")
    roh = pd.read_csv(os.path.join(DATA, "hist", "AAPL.csv"), index_col=0)["open"]
    hand = roh[D.tage[D.e[1]]] / roh[D.tage[D.e[0]]] - 1
    w(f"- Stichprobe AAPL, erster Monat: aus der Rohdatei von Hand {pz(hand, 3)}, im Rücktest {pz(D.R[0, j], 3)}.")
    kv, v_end = kurve(D, D.LIQ)
    w(f"- Zwei getrennte Rechenwege für den Markt (Monatsrenditen und Tageskurve) enden bei {gesamt(markt) + 1:.6f} "
      f"und {kv.iloc[-1]:.6f}.")
    assert abs(hand - D.R[0, j]) < 1e-9 and abs(kv.iloc[-1] - gesamt(markt) - 1) < 1e-9
    w(f"- Letzter verwendeter Kurstag: {D.tage[-1]} (nichts aus dem Abschlusszeitraum).\n")

    # Vergleichswerte
    w("## 1. Vergleichswerte im Entwicklungszeitraum\n")
    w("| | Rendite pro Jahr | gesamt | größter Rückgang |\n|---|---|---|---|")
    kt = lambda x: pd.Series(D.etf[x + "_tag"][D.e[0]:], index=D.tage[D.e[0]:])
    for name, r, dd in (("Durchschnitt der liquiden Aktien (Markt)", markt, rueckgang(kv)),
                        ("IWM (kleine Werte, Kurs ohne Dividende)", iwm, rueckgang(kt("IWM"))),
                        ("SPY (große Werte, Kurs ohne Dividende)", spy, rueckgang(kt("SPY")))):
        w(f"| {name} | {pz(pa(D, r))} | {pz(gesamt(r), 0)} | {pz(dd, 0)} |")
    hm, hi = halbjahre(D, markt), halbjahre(D, iwm)
    w(f"\nDer Markt-Durchschnitt liegt {pz(pa(D, markt) - pa(D, iwm))}-Punkte pro Jahr vor IWM und in "
      f"{int((hm > hi).sum())} von {len(hm)} Halbjahren vorn, ohne jede Auswahl.\n")

    # 2) Zufall
    w("## 2. Zufallsauswahl (muss beim Markt landen)\n")
    rng = np.random.default_rng(1)
    res = {"neu": [], "fest": []}
    for art in res:
        for _ in range(laeufe):
            score = rng.random((K, N)) if art == "neu" else np.repeat(rng.random((1, N)), K, 0)
            sel = top(score, D.LIQ, 0.10)
            r0, um = lauf(D, sel)
            r4, _ = lauf(D, sel, KOSTEN[0])
            r10, _ = lauf(D, sel, KOSTEN[1])
            bw = bewertung(D, sel)
            res[art].append((pa(D, r0), pa(D, r4), pa(D, r10), um[1:].mean(), (halbjahre(D, r0) > hm).sum(),
                             bw["vorn"], bw["vorn"] >= bw["noetig"], bw["bestanden"], bw["ohne3_pa"] - bw["pa"]))
    w(f"Je {laeufe} Durchläufe, jeweils 10 % der liquiden Aktien. Markt: {pz(pa(D, markt))} pro Jahr.\n")
    w("| Zufallsauswahl | Rendite pro Jahr vor Kosten (Mittel) | 90 % der Läufe zwischen | Umschlag je Monat | "
      "nach 0,4 % Kosten | nach 1,0 % Kosten | Halbjahre vor dem Markt (vor Kosten, Mittel) |\n|---|---|---|---|---|---|---|")
    for art, name in (("neu", "jeden Monat neu gelost"), ("fest", "einmal gelost, dann gehalten")):
        a = np.array(res[art], float)
        w(f"| {name} | {pz(a[:, 0].mean())} | {pz(np.percentile(a[:, 0], 5))} und {pz(np.percentile(a[:, 0], 95))} | "
          f"{a[:, 3].mean() * 100:.0f} % | {pz(a[:, 1].mean())} | {pz(a[:, 2].mean())} | "
          f"{kz(a[:, 4].mean())} von {len(hm)} |")
    w("\nWie oft besteht reiner Zufall die Hürden des Entwicklungszeitraums (nach 0,4 % Kosten)?\n")
    w(f"| Zufallsauswahl | in mind. {bw['noetig']} von {len(hm)} Halbjahren vor Markt und IWM | "
      "zusätzlich ohne die 3 besten Aktien je Halbjahr vor dem Markt |\n|---|---|---|")
    for art, name in (("neu", "jeden Monat neu gelost"), ("fest", "einmal gelost, dann gehalten")):
        a = np.array(res[art], float)
        w(f"| {name} | {kz(a[:, 6].mean() * 100)} % der Läufe | {kz(a[:, 7].mean() * 100)} % der Läufe |")
    a = np.array(res["fest"], float)
    w(f"\nDie Regel „ohne die 3 besten Aktien je Halbjahr“ kostet eine Zufallsauswahl von rund "
      f"{np.mean([x.sum(1).mean() for x in [top(rng.random((K, N)), D.LIQ, 0.10)]]):.0f} Aktien im Mittel "
      f"{pz(a[:, 8].mean())}-Punkte pro Jahr. So viel Vorsprung muss eine Strategie mindestens mitbringen.")

    # 3) Zukunftswissen
    w("\n## 3. Auswahl mit Zukunftswissen (muss unrealistisch gut sein)\n")
    C = D.C
    s, e = np.array(D.s), np.array(D.e)
    tests = (("kennt die Rendite des kommenden Monats", D.R.copy()),
             ("kennt nur den Schlusskurs des Kauftags (1 Tag Vorsprung)", C[e] / C[s] - 1),
             ("dieselbe Kennzahl ohne Vorsprung (Tagesrendite am Stichtag)", C[s] / C[s - 1] - 1))
    w("| Auswahl der besten 10 % | Rendite pro Jahr vor Kosten | nach 0,4 % Kosten | je Monat im Mittel | "
      "Halbjahre vor dem Markt |\n|---|---|---|---|---|")
    for name, score in tests:
        sel = top(score, D.LIQ, 0.10)
        r0, _ = lauf(D, sel)
        r4, _ = lauf(D, sel, KOSTEN[0])
        w(f"| {name} | {pz(pa(D, r0), 0)} | {pz(pa(D, r4), 0)} | {pz(r0.mean())} | "
          f"{int((halbjahre(D, r4) > hm).sum())} von {len(hm)} |")
    w(f"| zum Vergleich: Markt | {pz(pa(D, markt), 0)} | | {pz(markt.mean())} | |")
    txt = "\n".join(out) + "\n"
    open(os.path.join(OUT, "selbsttest.md"), "w").write(txt)
    print(txt)


# ---------------- Hypothesen ----------------
ERG = os.path.join(OUT, "strategie_ergebnisse.json")


def zeile(D, name, sel):
    """Eine Ergebniszeile fuer eine Variante; wird in output/strategie_ergebnisse.json festgehalten."""
    bw, bw10 = bewertung(D, sel), bewertung(D, sel, KOSTEN[1])
    kv, _ = kurve(D, sel, KOSTEN[0])
    z = {"name": name, "titel": round(bw["titel"]), "umschlag": bw["umschlag"], "pa": bw["pa"], "pa10": bw10["pa"],
         "markt_pa": bw["markt_pa"], "iwm_pa": bw["iwm_pa"], "vorn": bw["vorn"], "noetig": bw["noetig"],
         "n_hj": len(bw["hj"]), "ohne3_pa": bw["ohne3_pa"], "ohne3_ok": bool(bw["ohne3_ok"]),
         "rueckgang": rueckgang(kv), "bestanden": bool(bw["bestanden"]),
         "hj": [float(x) for x in bw["hj"]], "hj_markt": [float(x) for x in bw["hj_markt"]],
         "hj_iwm": [float(x) for x in bw["hj_iwm"]], "hj_namen": D.hj_namen}
    alle = json.load(open(ERG)) if os.path.exists(ERG) else {}
    alle[name] = z
    json.dump(alle, open(ERG, "w"), indent=1)
    return z


def tabelle(zs):
    out = ["| Variante | Aktien | Umschlag je Monat | pro Jahr nach 0,4 % | nach 1,0 % | Markt | IWM | Halbjahre vor beiden | "
           "ohne 3 beste pro Jahr | größter Rückgang | Urteil |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for z in zs:
        out.append(f"| {z['name']} | {z['titel']} | {z['umschlag'] * 100:.0f} % | {pz(z['pa'])} | {pz(z['pa10'])} | "
                   f"{pz(z['markt_pa'])} | {pz(z['iwm_pa'])} | {z['vorn']} von {z['n_hj']} (nötig {z['noetig']}) | "
                   f"{pz(z['ohne3_pa'])} | {pz(z['rueckgang'], 0)} | {'bestanden' if z['bestanden'] else 'durchgefallen'} |")
    return "\n".join(out)


def kurs_kennzahlen(D):
    """Kennzahlen nur aus Kursen, je Stichtag. Alles endet am Schlusskurs des Stichtags."""
    s = np.array(D.s)
    Cf = D.Cf
    alt = np.isfinite(Cf[s - 252])                      # mindestens 12 Monate Historie
    hoch = np.vstack([np.nanmax(Cf[i - 251:i + 1], axis=0) for i in s])
    return {"m12": np.where(alt, Cf[s - 21] / Cf[s - 252] - 1, np.nan),
            "m6": np.where(alt, Cf[s - 21] / Cf[s - 126] - 1, np.nan),
            "hoch": np.where(alt, Cf[s] / hoch, np.nan),
            "ueber200": Cf[s] > np.vstack([np.nanmean(Cf[i - 199:i + 1], axis=0) for i in s])}


def kurs_hypothesen():
    D = Daten()
    k = kurs_kennzahlen(D)
    zs = [zeile(D, "1a Kursstärke 12 Monate", top(k["m12"], D.LIQ, 0.10)),
          zeile(D, "1b Kursstärke 6 Monate", top(k["m6"], D.LIQ, 0.10)),
          zeile(D, "3a Nähe zum 52-Wochen-Hoch, beste 10 %", top(k["hoch"], D.LIQ, 0.10)),
          zeile(D, "3b Nähe zum 52-Wochen-Hoch, beste 20 %", top(k["hoch"], D.LIQ, 0.20))]
    print(tabelle(zs))
    for z in zs:
        print(z["name"], "| Abstand zum Markt je Halbjahr:", " ".join(f"{(a - m) * 100:+.0f}" for a, m in zip(z["hj"], z["hj_markt"])))


def rang(x, ok):
    """Rang je Periode als Anteil (0 bis 1) unter den zugelassenen Aktien, sonst NaN."""
    out = np.full(x.shape, np.nan)
    for k in range(x.shape[0]):
        i = np.where(ok[k])[0]
        if len(i) > 1:
            out[k, i] = np.argsort(np.argsort(x[k, i])) / (len(i) - 1)
    return out


def bilanz_kennzahlen(D):
    """Bilanz-Kennzahlen je Stichtag, zwischengespeichert (nur Entwicklungszeitraum)."""
    import pickle, bilanz
    p = os.path.join(DATA, "bilanz_abschluss.pkl" if D.abschluss else "bilanz_dev.pkl")
    if os.path.exists(p):
        return pickle.load(open(p, "rb"))
    M = bilanz.kennzahlen(D)
    pickle.dump(M, open(p, "wb"))
    return M


def bilanz_auswahlen(D):
    """Auswahlmatrizen der Hypothesen 2, 4, 5, 6, 7 genau wie in UEBERGABE.md festgeschrieben."""
    k, B = kurs_kennzahlen(D), bilanz_kennzahlen(D)
    f = np.isfinite
    oi, akt = B["oi_ttm"], B["akt_vj"]
    with np.errstate(invalid="ignore", divide="ignore"):
        solide = D.LIQ & f(oi) & f(akt) & (oi > 0)
        ok4 = D.LIQ & f(oi) & (B["assets"] > 0) & (B["boerse"] > 0)
        roa, rendite = oi / B["assets"], oi / B["boerse"]
        ok4 &= np.abs(rendite) <= 1                     # Gewinn groesser als der Boersenwert: Datenfehler
        ok4b = ok4 & (k["m12"] > 0)
        ok5 = D.LIQ & f(B["d_wachs"]) & f(B["d_marge"])
        s5 = np.where((B["d_wachs"] > 0) & (B["d_marge"] > 0),
                      np.clip(B["d_wachs"], -1, 1) + np.clip(B["d_marge"], -1, 1), np.nan)
        ok6 = D.LIQ & f(akt)
        ok7 = D.LIQ & f(oi) & f(akt)
        verlust_ab = (oi <= 0) & ~k["ueber200"]

    def top_n(score, basis, ok):                        # so viele Aktien wie 10 % der Basis, nur aus `ok`
        sel = np.zeros(basis.shape, bool)
        for r in range(basis.shape[0]):
            i = np.where(ok[r] & f(score[r]))[0]
            n = max(1, int(round(0.10 * basis[r].sum())))
            sel[r, i[np.argsort(-score[r, i], kind="stable")[:n]]] = True
        return sel

    return {"gruppe": ok7, "liste": [
        ("2a Kursstärke, profitabel, Aktienzahl ≤ +2 %", top(k["m12"], solide & (akt <= 0.02), 0.10)),
        ("2b Kursstärke, profitabel, Aktienzahl ≤ 0 %", top(k["m12"], solide & (akt <= 0), 0.10)),
        ("4a Profitabel und günstig", top(rang(roa, ok4) + rang(rendite, ok4), ok4, 0.10)),
        ("4b Profitabel und günstig, Kurs im Plus", top(rang(roa, ok4b) + rang(rendite, ok4b), ok4b, 0.10)),
        ("5a Beschleunigung", top_n(s5, ok5, ok5)),
        ("5b Beschleunigung, profitabel", top_n(s5, ok5 & (oi > 0), ok5 & (oi > 0))),
        ("6a Stärkster Rückgang der Aktienzahl", top(-akt, ok6, 0.10)),
        ("6b Rückkäufe ≥ 1 %, profitabel", solide & (akt <= -0.01)),
        ("7a Ausschlussliste", ok7 & ~verlust_ab & ~(akt > 0.10)),
        ("7b Ausschlussliste, ohne alle Verlustfirmen", ok7 & (oi > 0) & ~(akt > 0.10))]}


def bilanz_hypothesen():
    D = Daten()
    A = bilanz_auswahlen(D)
    g, _ = lauf(D, A["gruppe"])
    print(f"Aktien mit Bilanzdaten je Monat: {A['gruppe'].sum(1).mean():.0f} von {D.LIQ.sum(1).mean():.0f} handelbaren. "
          f"Ihr Durchschnitt: {pz(pa(D, g))} pro Jahr (Markt {pz(pa(D, lauf(D, D.LIQ)[0]))}).")
    zs = [zeile(D, name, sel) for name, sel in A["liste"]]
    print(tabelle(zs))
    hg = halbjahre(D, g)
    for z in zs:
        print(z["name"], "| Abstand zum Markt je Halbjahr:", " ".join(f"{(a - m) * 100:+.0f}" for a, m in zip(z["hj"], z["hj_markt"])),
              "| Halbjahre vor der Gruppe mit Bilanzdaten:", int((np.array(z["hj"]) > hg).sum()))


FINALIST = "1a Kursstärke 12 Monate"


def abschluss_rechnung(D):
    """Reine Rechnung fuer Finalist 1a auf den Daten von D (keine Sperre, keine Datei). Erfolg laut Regel:
    Gesamtrendite nach 0,4 % Kosten vor Markt und IWM."""
    sel = top(kurs_kennzahlen(D)["m12"], D.LIQ, 0.10)
    r4, um = lauf(D, sel, KOSTEN[0])
    r10, _ = lauf(D, sel, KOSTEN[1])
    markt, _ = lauf(D, D.LIQ)
    iwm, spy = D.etf["IWM"], D.etf["SPY"]
    kv, _ = kurve(D, sel, KOSTEN[0])
    return {"von": D.tage[D.e[0]], "bis": D.tage[-1], "monate": len(D.e), "titel": float(sel.sum(1).mean()),
            "umschlag": float(um[1:].mean()), "strategie": gesamt(r4), "strategie_1pct": gesamt(r10),
            "markt": gesamt(markt), "iwm": gesamt(iwm), "spy": gesamt(spy), "rueckgang": rueckgang(kv),
            "strategie_pa": pa(D, r4), "markt_pa": pa(D, markt), "iwm_pa": pa(D, iwm),
            "hj": dict(zip(D.hj_namen, halbjahre(D, r4))), "hj_markt": dict(zip(D.hj_namen, halbjahre(D, markt))),
            "hj_iwm": dict(zip(D.hj_namen, halbjahre(D, iwm))),
            "bestanden": bool(gesamt(r4) > gesamt(markt) and gesamt(r4) > gesamt(iwm))}


def abschlusstest():
    """EINMALIGER Abschlusstest fuer den Finalisten. Die Sperre wird vor der Rechnung gesetzt."""
    abschluss_freigabe(FINALIST)
    res = abschluss_rechnung(Daten(abschluss=True))
    json.dump(res, open(os.path.join(OUT, "abschlusstest.json"), "w"), indent=1)
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    {"selbsttest": selbsttest, "kurs": kurs_hypothesen, "bilanz": bilanz_hypothesen,
     "abschluss": abschlusstest, "abschluss_probe": lambda: print(abschluss_rechnung(Daten()))}[sys.argv[1]]()
