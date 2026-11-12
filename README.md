# Aktien-Screener: Ablaufanleitung

US-Aktien mit 300 Mio. bis 10 Mrd. $ Börsenwert, geprüft auf fünf Kriterien
(Liquidität, Wachstum, Qualität, Bilanz, Trend). Die Schwellen stehen oben in `screener.py`.

## Wöchentlicher Lauf

```bash
python3 screener.py
```

Dauer beim ersten Lauf des Tages ca. 45 Minuten (Kursdaten für rund 2.700 Titel), danach Sekunden,
weil `data/` als Cache dient (Kurse und Bilanzdaten 20 Stunden gültig). Schneller geht es mit zwei
parallelen Vorläufen: `python3 screener.py --prices` und `python3 screener.py --facts`.

Ergebnis in `output/`:

- `report.md`: Kandidaten (alle 5 Kriterien) und Beobachtungsliste (4 von 5) als Tabellen
- `kandidaten.csv`, `watchlist.csv`, `alle_geprueft.csv`: dieselben Daten mit allen Kennzahlen

## Ausbruchs-Scanner (zweite Schiene)

```bash
python3 fetch_history.py update
```

```bash
python3 scan.py 7
```

Der erste Befehl ergänzt die Kurshistorie in `data/hist/` um die neuen Tage (ca. 30 Minuten), der zweite
schreibt `output/ausbrueche.md`: alle Sprünge ≥ 10 % bei ≥ 3-fachem Volumen der letzten 7 Handelstage,
eingeordnet in die Stufen A+, A, – und Meiden. Die Stufen und ihre Rücktest-Werte stehen oben in `scan.py`.

Fehlt `data/hist/` (neuer Container), vorher einmalig `python3 fetch_history.py prices` und
`python3 fetch_history.py sec` laufen lassen (zusammen ca. 40 Minuten).

## Rücktest

```bash
python3 backtest.py
```

Schreibt `output/ruecktest.md` für beide Schienen. Das Universum sind heute gelistete Aktien; Pleiten
und Übernahmen fehlen, die Ergebnisse sind deshalb eher zu günstig.

## Was der Lauf nicht prüft

- Insiderkäufe und Managementbeteiligung (die SEC-Seite dafür weist Skripte ohne Kontaktangabe ab)
- Burggraben, Marktgröße, Gründe für eine Fehlbewertung: Handprüfung der Kandidaten
- Finanz- und Immobilienwerte sind ausgeschlossen, weil ROIC und Nettoschulden dort nicht passen
- Schulden sind eine Näherung aus den gemeldeten Bilanzposten, ohne Leasing

## Datenquellen

- `api.nasdaq.com`: Aktienliste, Börsenwert, Tageskurse
- `data.sec.gov`: Umsätze aller Firmen je Periode (Frames), Stammdaten, Bilanzdaten je Firma
- `query1.finance.yahoo.com`: nur für Nicht-US-Werte im Depot, antwortet zeitweise mit 429

Die Hosts müssen in der Netzwerkfreigabe der Umgebung stehen. Die Skripte melden sich mit einer
ehrlichen Kennung als automatisches Skript; Browser-Kennungen vortäuschen ist nicht vorgesehen.
