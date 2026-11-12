# Übergabe: Suche nach einer Aktienstrategie, die den Markt schlägt

Diese Datei ist der Einstieg für jede neue Sitzung. Lies sie ganz, bevor du etwas tust, und aktualisiere am
Ende den Abschnitt „Stand".

## Ziel

Eine regelbasierte Auswahl von US-Aktien (kleine und mittlere Werte) finden, die nach Kosten besser abschneidet
als der Markt, und zwar auch in Daten, die beim Entwickeln nicht angesehen wurden. Findet sich nichts
Belastbares, ist genau das das Ergebnis. Erfundene oder schöngerechnete Ergebnisse sind wertlos, weil später
echtes Geld daran hängt.

## Arbeitsregeln des Nutzers

- Antworten auf Deutsch, Anrede „du", kurz und ohne Fachjargon.
- Credits sparen: nach jedem Schritt den nächsten Schritt mit Schwierigkeit nennen (leicht, mittel, schwer) und
  auf „weiter" warten. Keine Unteragenten. Lange Downloads als Hintergrundbefehl starten und nicht abfragen.
- Kein Pull Request; direkt auf `main` committen und pushen.
- Keine Kaufempfehlung mit echtem Geld, solange der Abschlusstest (unten) nicht bestanden ist.

## Was im Repository liegt

- `common.py`: Abruf mit Cache, Kurs-Helfer. `fetch_history.py`: Kurshistorie und SEC-Stammdaten laden.
- `backtest.py`: Kursmatrizen (`load_panel`), Sprung-Ereignisse, SEC-Quartalsdaten, Rücktest beider Schienen.
- `screener.py`: Qualitäts-Screener (5 Kriterien). `scan.py`: Ausbruchs-Scanner mit Stufen A+, A, –, Meiden.
- `depot.py`: Depot-Simulation je Halbjahr. `weekly.py`: wöchentlicher Probelauf mit Protokoll in `protokoll/`.
- `output/`: Berichte (`ruecktest.md`, `depot.md`, `ausbrueche.md`). `README.md`: Befehle.
- Geplante Aufgabe „Aktien-Probelauf wöchentlich" (samstags 14:12 Uhr deutscher Zeit) ruft `weekly.py` auf.
  Nicht ändern, solange der Nutzer das nicht verlangt.

## Daten und Umgebung

- `data/` ist nicht im Repository (außer `sec_meta.json`). In einem neuen Container zuerst laden:
  `python3 fetch_history.py prices` (ca. 45 bis 60 Minuten für rund 2.800 Aktien), danach baut
  `backtest.load_panel(rebuild=True)` die Kursmatrizen.
- `api.nasdaq.com` liefert Tageskurse für 10 Jahre (geprüft: bis November 2016 zurück), auch für die ETFs
  IWM und SPY mit `assetclass=etf`. Bisher wurden nur 5 Jahre geladen (`START` in `fetch_history.py`).
  Kurse sind um Splits bereinigt, Dividenden fehlen.
- `data.sec.gov` liefert Bilanzdaten (Frames je Periode, `companyfacts` je Firma mit Meldedatum `filed`) und
  Termine der Quartalsmeldungen. Höchstens 10 Abrufe je Sekunde.
- `www.sec.gov` weist das Skript ab, deshalb gibt es keine Insiderdaten. Yahoo antwortet oft mit 429.
- Die Skripte melden sich mit einer ehrlichen Skript-Kennung. Keine Browser-Kennung vortäuschen und keine
  persönlichen Daten des Nutzers in Abrufe schreiben.
- Das Universum sind heute gelistete Aktien ab 100 Mio. $ Börsenwert, ohne Finanz- und Immobilienwerte.
  Pleiten und Übernahmen fehlen, alle Ergebnisse sind deshalb eher zu günstig.

## Was schon geprüft wurde und nicht reicht

Zeitraum November 2021 bis November 2026, Abstand zum Durchschnitt der liquiden Aktien nach 60 Handelstagen:

| Ansatz | Ergebnis |
|---|---|
| Qualitäts-Screener, alle 5 Kriterien | +63 % gegen +71 % für den Markt über 8 Halbjahre: kein Vorteil |
| Alle Kurssprünge ≥ 10 % bei ≥ 3-fachem Volumen (6.953) | −0,4 Punkte |
| Stufe A (nach Quartalszahlen, Umsatz ≥ +25 %, profitabel) | +4,2 Punkte bis Mai 2026, danach −2,8 Punkte |
| Stufe A+ (Sprung ≥ 40 % nach Quartalszahlen) | +13,7 Punkte, danach +10,2 Punkte, aber nur 162 Fälle |
| Meiden (Sprung ≥ 40 % ohne Quartalszahlen) | −10,4 Punkte, danach −11,9 Punkte: hält |
| Depot aus A und A+ (`depot.py`) | schlägt den Markt in 4 von 9 Halbjahren, in den letzten drei nicht |

Gründe für das schwache Depot: Die Signale kommen gehäuft in der Berichtssaison, dazwischen liegen im Schnitt
rund 60 % des Geldes ungenutzt herum. Der Vorteil hängt an wenigen großen Gewinnern, nur gut ein Drittel der Käufe
endet im Plus. Die Stufen wurden an denselben Daten gefunden, an denen sie gemessen wurden.

## Auftrag

1. **Daten erweitern (leicht, lange Wartezeit):** Kurse ab 2016 laden, dazu IWM und SPY als Vergleich.
2. **Rangfolge-Rücktest bauen (schwer):** neues Skript `strategie.py`. Monatlich alle Aktien nach einer Kennzahl
   ordnen, die besten kaufen, gleich gewichten, immer voll investiert. Das behebt das Bargeld-Problem.
3. **Hypothesen im Entwicklungszeitraum prüfen (mittel).**
4. **Abschlusstest einmalig (leicht).**
5. **Bericht `output/strategie_suche.md` (leicht):** alle geprüften Hypothesen, auch die gescheiterten.

## Prüfregeln (nicht verhandelbar)

- **Zeitliche Trennung:** Entwicklung bis 30. April 2025. Der Abschlusstest läuft ab 1. Mai 2025 und wird je
  Strategie genau einmal gerechnet, für höchstens 3 Finalisten. Fällt eine Strategie durch, wird sie verworfen
  und nicht nachgebessert.
- **Hypothesen vorher festlegen:** höchstens 8, je höchstens 2 Varianten, jede mit einem sachlichen Grund,
  warum sie funktionieren sollte. Erst aufschreiben, dann rechnen.
- **Kein Blick in die Zukunft:** Bilanzdaten zählen erst ab ihrem Meldedatum (`filed`), Kauf zur Eröffnung des
  Folgetags, Auswahl nur nach Liquidität des Vortags (Kurs ≥ 3 $, 20-Tage-Umsatz ≥ 1 Mio. $).
- **Kosten:** 0,4 % je Kauf und Verkauf, zusätzlich eine Rechnung mit 1,0 %.
- **Vergleich:** Durchschnitt der liquiden Aktien und IWM, beide voll investiert.
- **Erfolg heißt:** im Entwicklungszeitraum in mindestens zwei Dritteln der Halbjahre vor beiden Vergleichen,
  auch ohne die drei besten Aktien je Periode noch im Plus gegenüber dem Markt, und im Abschlusstest nach
  Kosten vor beiden Vergleichen.

## Hypothesen zum Start

Die Reihenfolge ist ein Vorschlag, die Liste darf vor dem Rechnen angepasst werden.

1. Kursstärke: beste 10 % nach 12-Monats-Rendite ohne den letzten Monat.
2. Kursstärke nur unter profitablen Firmen ohne Aktienverwässerung.
3. Nähe zum 52-Wochen-Hoch.
4. Profitabel und günstig: Rang nach operativem Gewinn je Vermögen plus Rang nach Gewinnrendite.
5. Beschleunigung: Umsatzwachstum steigt und Marge weitet sich aus.
6. Sinkende Aktienzahl (Rückkäufe) gegen steigende Aktienzahl.
7. A+ als Beimischung zu einem Markt-Depot statt als eigenes Depot.
8. Ausschlussliste: Markt ohne „Meiden"-Fälle, starke Verwässerer und Verlustfirmen im Abwärtstrend.

## Stand

- 12. November 2026: Datei angelegt. Auftrag Schritt 1 ist offen. Nasdaq-Historie über 10 Jahre und ETF-Abruf
  sind mit je einem Abruf geprüft, ein vollständiger Download ab 2016 ist noch nicht gelaufen.
