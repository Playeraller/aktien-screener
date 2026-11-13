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
- `strategie.py`: monatlicher Rangfolge-Rücktest (Auftrag Schritt 2) mit Datenbereinigung, Prüfregeln und
  Selbsttest (`python3 strategie.py selbsttest`, Ergebnis in `output/selbsttest.md`). Noch ohne Hypothesen.
- `depot.py`: Depot-Simulation je Halbjahr. `weekly.py`: wöchentlicher Probelauf mit Protokoll in `protokoll/`.
- `output/`: Berichte (`ruecktest.md`, `depot.md`, `ausbrueche.md`). `README.md`: Befehle.
- Geplante Aufgabe „Aktien-Probelauf wöchentlich" (samstags 14:12 Uhr deutscher Zeit) ruft `weekly.py` auf.
  Nicht ändern, solange der Nutzer das nicht verlangt.

## Daten und Umgebung

- `data/` ist nicht im Repository (außer `sec_meta.json`). In einem neuen Container zuerst laden:
  `python3 fetch_history.py prices` (ca. 45 bis 60 Minuten für rund 2.800 Aktien), danach baut
  `backtest.load_panel(rebuild=True)` die Kursmatrizen.
- `api.nasdaq.com` liefert Tageskurse für genau 10 Jahre rückwärts ab heute (am 12.11.2026: ab 11.11.2016,
  2.513 Handelstage). Das Fenster wandert, ältere Tage sind später nicht mehr abrufbar. `START` in
  `fetch_history.py` steht auf 2016-11-01, der Abruf holt bis zu 3.000 Zeilen (vorher 2.500, das schnitt ab).
  Kurse sind um Splits bereinigt, Dividenden fehlen (auch bei IWM und SPY).
- IWM und SPY liegen getrennt in `data/etf/` (`python3 fetch_history.py etf`, läuft bei `prices` mit), damit
  sie nicht als Aktien im Kurs-Panel landen.
- Scheitert ein Kursabruf, wird keine leere Datei mehr angelegt; `python3 fetch_history.py prices` erneut
  starten holt nur die fehlenden Aktien nach. Protokoll des Downloads: `data/download.log`.
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

## Festlegungen in `strategie.py` (getroffen vor der ersten Hypothese, danach nicht mehr ändern)

- Stichtag ist der letzte Handelstag des Monats, Kauf und Verkauf zur Eröffnung des nächsten Handelstags.
  Erster Kauf 1.12.2017 (früheste Kennzahl mit 12 Monaten Vorlauf), Ende 30.4.2025 zum Schlusskurs: 89 Monate.
- 15 Halbjahre (Mai bis Oktober, November bis April), das erste ist kurz (Dezember 2017 bis April 2018).
  „Zwei Drittel" heißt also mindestens 10 von 15, gemessen nach 0,4 % Kosten.
- Kosten: 0,4 % für Kauf und Verkauf zusammen (wie `COST` in `backtest.py`), berechnet auf den tatsächlich
  umgeschichteten Anteil; Stressrechnung mit 1,0 %. Markt und IWM laufen ohne Kosten.
- „Ohne die drei besten Aktien je Periode": Periode = Halbjahr; entfernt werden je Halbjahr die drei Aktien mit
  dem größten Beitrag, der Rest muss über den ganzen Zeitraum vor dem Markt liegen.
- Liquide heißt am Stichtag: Kurs ≥ 3 $, 20-Tage-Umsatz im Mittel ≥ 1 Mio. $, an mindestens 15 der 20 Tage und
  am Stichtag selbst gehandelt.
- Datenbereinigung (`bereinige`): Kurssprünge über Faktor 20, die binnen 10 Tagen zurückkehren, gelten als
  fehlend (z. B. LBTYA drei Tage lang 0,0001 $); bei Niveausprüngen über Faktor 20 nach oben ohne Rückkehr wird
  die Historie davor verworfen. Echte Kursstürze bleiben drin. Unbereinigte Splits wurden nicht gefunden.
- Im Entwicklungsmodus schneidet `Daten()` alle Kurse nach dem 30.4.2025 ab. Der Abschlusstest läuft nur über
  `abschluss_freigabe(name)`, das jeden Lauf in `protokoll/abschlusstest.json` festhält und einen zweiten Lauf
  derselben Strategie sowie einen vierten Finalisten verweigert.

## Ergebnis des Selbsttests (Entwicklungszeitraum)

- Markt (Durchschnitt der liquiden Aktien) +6,3 % pro Jahr, IWM +3,3 %, SPY +10,5 % (alle ohne Dividenden).
  Der Markt liegt ohne jede Auswahl 3,0 Punkte pro Jahr vor IWM: „vor IWM" allein beweist nichts.
- Zufallsauswahl von 10 % (500 Läufe): +6,2 bis +6,3 % pro Jahr vor Kosten, also beim Markt. 90 % der Läufe
  liegen zwischen +4,2 und +8,5 %: Unterschiede bis etwa 2 Punkte pro Jahr sind Rauschen.
- Monatlich komplett neu gemischt kostet der Umschlag 4,5 Punkte pro Jahr bei 0,4 % und 11 Punkte bei 1,0 %.
- Auswahl mit Zukunftswissen: +1.365 % pro Jahr; mit nur einem Tag Vorsprung +68 %; dieselbe Kennzahl ohne
  Vorsprung 0 %. Der Rücktest reagiert also auf ein Leck und zeigt ohne Leck nichts.
- Härte der Hürden: Zufall schafft „10 von 15 Halbjahren vor Markt und IWM" in 0,8 % der Läufe, mit der
  Regel „ohne die 3 besten" in keinem. Diese Regel allein kostet rund 4,1 Punkte pro Jahr. Eine Strategie
  braucht also grob 4 Punkte pro Jahr Vorsprung nach Kosten, um zu bestehen.

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
- 12. November 2026, Sitzung 2: `fetch_history.py` auf 10 Jahre umgestellt, IWM und SPY geladen (je 2.513 Tage,
  11.11.2016 bis 11.11.2026). Download der 2.831 Aktien als Hintergrundbefehl gestartet; ob er vollständig
  durchlief, steht am Ende von `data/download.log` (in einem neuen Container neu starten). Nebenbei behoben:
  `weekly.py` wollte in einem frischen Container nur 300 Tage laden, das griff wegen eines festen
  Vorgabewerts nicht; jetzt greift es. Nächster Schritt: Kursmatrizen bauen und prüfen, dann Auftrag
  Schritt 2 (`strategie.py`) mit den zwei Selbsttests des Rücktests (Zufallsauswahl muss beim Markt landen,
  Auswahl mit Zukunftswissen muss unrealistisch gut sein), bevor irgendeine Hypothese gerechnet wird.
- 13. November 2026: Download vollständig (2.826 Aktien geladen, 5 ohne Daten, kein gescheiterter Abruf; Panel
  2.513 Tage × 2.811 Aktien). Auftrag Schritt 2 erledigt: `strategie.py` gebaut, Daten bereinigt, Selbsttest
  bestanden (siehe oben). Noch keine Hypothese gerechnet, der Abschlusszeitraum ist unberührt.
  Nächster Schritt: Hypothesenliste endgültig festschreiben (höchstens 8, je höchstens 2 Varianten, mit Grund),
  dann zuerst die reinen Kurs-Hypothesen 1 und 3 rechnen. Für 2, 4, 5, 6 und 8 fehlen noch Bilanzdaten mit
  Meldedatum (`companyfacts` je Firma von `data.sec.gov`, rund 2.800 Abrufe als Hintergrundbefehl).
