"""Bilanz-Kennzahlen je Stichtag, streng nach Meldedatum (kein Blick in die Zukunft).

Quelle: data/facts/CIK.json aus fetch_fundamentals.py. Je Periode zaehlt nur der zuerst gemeldete Wert, und
zwar erst ab seinem Meldedatum. Spaetere Korrekturen werden nicht benutzt. Ein Wert gilt hoechstens 200 Tage
nach Periodenende, danach als veraltet.

kennzahlen(D) liefert Matrizen [Perioden x Aktien] passend zu strategie.Daten:
  oi_ttm   operativer Gewinn der letzten 4 Quartale        assets  Bilanzsumme
  boerse   Boersenwert am Stichtag                         akt_vj  Veraenderung der Aktienzahl zum Vorjahr
  d_wachs  Umsatzwachstum zum Vorjahresquartal minus dasselbe ein Quartal frueher
  d_marge  operative Marge minus Marge im Vorjahresquartal
"""
import os, json, datetime, functools
import numpy as np
import screener as s
from common import DATA
from fetch_fundamentals import FACTS, ticker_cik

FRISCH = 200
OI_TAGS = ["OperatingIncomeLoss", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"]
REV_TAGS = list(s.REV_TAGS) + ["SalesRevenueNet"]      # SalesRevenueNet: Name bis 2018
# unverwaesserte Zahl zuerst: die verwaesserte aendert sich auch durch Bilanzregeln, das stoert die Split-Erkennung
AKT_TAGS = ["WeightedAverageNumberOfSharesOutstandingBasic", "WeightedAverageNumberOfDilutedSharesOutstanding"]


@functools.lru_cache(maxsize=None)
def o(d):
    return datetime.date.fromisoformat(d).toordinal()


def quartale(rows):
    """{Periodenende: (Quartalswert, verfuegbar ab)} aus Erstmeldungen; fehlende Quartale aus Summen abgeleitet."""
    erst = {}
    for st, en, v, fl, _ in rows:
        if st is None or v is None:
            continue
        k = (o(st), o(en))
        if k not in erst or o(fl) < erst[k][1]:
            erst[k] = (v, o(fl))
    q, je_start = {}, {}
    for (st, en), (v, fl) in erst.items():
        if 75 <= en - st <= 105:
            q[en] = (v, fl)
        je_start.setdefault(st, []).append((en, v, fl))
    for st, lst in je_start.items():                   # z. B. Jahr minus 9 Monate = 4. Quartal
        lst.sort()
        for i in range(1, len(lst)):
            en, v, fl = lst[i]
            if en in q:
                continue
            for en2, v2, fl2 in lst[:i]:
                if 75 <= en - en2 <= 105:
                    q[en] = (v - v2, max(fl, fl2))
                    break
    return q


def misch(qs):
    """Mehrere Kennzahl-Namen zusammenfuehren: je Periodenende der frueher gemeldete Wert."""
    out = {}
    for q in qs:
        for en, (v, fl) in q.items():
            if en not in out or fl < out[en][1]:
                out[en] = (v, fl)
    return out


def davor(q, en, k):
    """Quartal k Quartale vor en (Toleranz 20 Tage) oder None."""
    ziel = en - 91.31 * k
    best = min(q, key=lambda x: abs(x - ziel), default=None)
    return q[best] if best is not None and abs(best - ziel) <= 20 else None


def firma(f):
    """Zeitreihen einer Firma, jeweils Listen von (verfuegbar ab, Periodenende, Wert), nach Meldedatum sortiert."""
    rev = misch([quartale(f.get(t, [])) for t in REV_TAGS])
    oi = quartale(f.get(OI_TAGS[0], []))
    for en, x in quartale(f.get(OI_TAGS[1], [])).items():     # Vorsteuergewinn nur, wo der operative Gewinn fehlt
        oi.setdefault(en, x)
    out = {"oi_ttm": [], "d_wachs": [], "d_marge": [], "assets": [], "akt_vj": [], "aktien": [], "splits": []}
    for en in sorted(oi):
        xs = [davor(oi, en, k) for k in range(4)]
        if all(xs):
            out["oi_ttm"].append((max(x[1] for x in xs), en, sum(x[0] for x in xs)))
    for en in sorted(rev):
        r = [davor(rev, en, k) for k in (0, 1, 4, 5)]
        if all(r) and r[2][0] > 0 and r[3][0] > 0:
            out["d_wachs"].append((max(x[1] for x in r), en, (r[0][0] / r[2][0] - 1) - (r[1][0] / r[3][0] - 1)))
        m = [davor(rev, en, 0), davor(oi, en, 0), davor(rev, en, 4), davor(oi, en, 4)]
        if all(m) and m[0][0] > 0 and m[2][0] > 0:
            out["d_marge"].append((max(x[1] for x in m), en, m[1][0] / m[0][0] - m[3][0] / m[2][0]))
    erst = {}
    for _, en, v, fl, _ in f.get("Assets", []):
        if v is not None and (o(en) not in erst or o(fl) < erst[o(en)][0]):
            erst[o(en)] = (o(fl), v)
    out["assets"] = [(fl, en, v) for en, (fl, v) in erst.items()]
    # Aktienzahl: Vergleich zum Vorjahr nur innerhalb derselben Meldung (dort sind beide Werte splitbereinigt)
    rows = next((f[t] for t in AKT_TAGS if f.get(t)), [])
    werte = [r[2] for r in rows if r[0] is not None and r[2] and r[2] > 0]
    mitte = float(np.median(werte)) if werte else 1.0
    je_meldung, je_periode = {}, {}
    for st, en, v, fl, _ in rows:
        if st is None or not v or v <= 0:
            continue
        while v / mitte > 300:                         # Meldefehler: Angabe in Stueck statt Tausend oder umgekehrt
            v /= 1000
        while v / mitte < 1 / 300:
            v *= 1000
        je_meldung.setdefault(o(fl), []).append((o(en), o(en) - o(st), v))
        je_periode.setdefault((o(st), o(en)), []).append((o(fl), v))
    for fl, xs in je_meldung.items():
        en = max(x[0] for x in xs)
        dauer, v = min((x[1], x[2]) for x in xs if x[0] == en)
        out["aktien"].append((fl, en, v))
        alt = [x[2] for x in xs if abs(x[1] - dauer) <= 15 and abs(en - 365 - x[0]) <= 20]
        if alt:
            out["akt_vj"].append((fl, en, v / alt[0] - 1))
    # Splits: dieselbe Periode wird spaeter mit glattem Faktor neu gemeldet
    ereignisse = []
    for xs in je_periode.values():
        xs.sort()
        stand = xs[0][1]
        for fl, v in xs[1:]:
            r = v / stand
            if not 0.8 <= r <= 1.25:
                g = r if r > 1 else 1 / r
                if g <= 100 and abs(g - round(g * 2) / 2) / g <= 0.02 and (g <= 3 or abs(g - round(g)) / g <= 0.02):
                    ereignisse.append((fl, r))
                stand = v
    gruppen = []
    for fl, r in sorted(ereignisse):
        for g in gruppen:
            if abs(r / g[1] - 1) <= 0.08 and fl - g[0] <= 400:
                g[2] += 1
                break
        else:
            gruppen.append([fl, r, 1])
    out["splits"] = [(g[0], g[1]) for g in gruppen if g[2] >= 2]
    for k in out:
        out[k].sort()
    return out


def stand(reihe, t):
    """Juengster Wert, der am Tag t gemeldet und noch frisch ist."""
    best = None
    for fl, en, v in reihe:
        if fl > t:
            break
        if best is None or en >= best[0]:
            best = (en, v)
    return best[1] if best and t - best[0] <= FRISCH else np.nan


def kennzahlen(D):
    t2c = ticker_cik()
    K, N = len(D.s), len(D.sym)
    names = ("oi_ttm", "assets", "akt_vj", "d_wachs", "d_marge", "boerse")
    M = {k: np.full((K, N), np.nan) for k in names}
    A = np.full((K, N), np.nan)                        # Aktienzahl in heutigen Stueck (splitbereinigt)
    ts = [o(D.tage[i]) for i in D.s]
    for j, sym in enumerate(D.sym):
        p = os.path.join(FACTS, f"{t2c.get(sym)}.json")
        if sym not in t2c or not os.path.exists(p):
            continue
        z = firma(json.load(open(p)))
        for k, t in enumerate(ts):
            for name in ("oi_ttm", "assets", "akt_vj", "d_wachs", "d_marge"):
                M[name][k, j] = stand(z[name], t)
            aktien = stand(z["aktien"], t)
            faktor = np.prod([r for fl, r in z["splits"] if fl > t]) if z["splits"] else 1.0
            A[k, j] = aktien * faktor
            M["boerse"][k, j] = D.Cf[D.s[k], j] * aktien * faktor
    with np.errstate(invalid="ignore"):                # Boersenwert kleiner als zwei Tagesumsaetze: Datenfehler
        M["boerse"][M["boerse"] < 2 * D.umsatz20] = np.nan
        # Gegenprobe: Veraenderung der bereinigten Aktienzahl ueber 12 Monate gegen den Vorjahresvergleich aus
        # derselben Meldung. Weicht das grob ab (unerkannter Split, Umbau der Firma), gilt der Boersenwert in
        # diesen 12 Monaten als unbekannt.
        q = A[12:] / A[:-12] / (1 + M["akt_vj"][12:])
        for k, j in zip(*np.where((q > 1.6) | (q < 0.625))):
            M["boerse"][k:k + 13, j] = np.nan
    return M
