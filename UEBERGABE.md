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
- Nach jeder abgeschlossenen großen Aufgabe einen fertigen Prompt für einen neuen Chat ausgeben (spart
  Tokens): Rolle, Repository, „lies UEBERGABE.md", die nächste Aufgabe. Vorher den Stand hier eintragen.
- Kein Pull Request; direkt auf `main` committen und pushen.
- Keine Kaufempfehlung mit echtem Geld, solange der Abschlusstest (unten) nicht bestanden ist.

## Was im Repository liegt

- `common.py`: Abruf mit Cache, Kurs-Helfer. `fetch_history.py`: Kurshistorie und SEC-Stammdaten laden.
- `backtest.py`: Kursmatrizen (`load_panel`), Sprung-Ereignisse, SEC-Quartalsdaten, Rücktest beider Schienen.
- `screener.py`: Qualitäts-Screener (5 Kriterien). `scan.py`: Ausbruchs-Scanner mit Stufen A+, A, –, Meiden.
- `strategie.py`: monatlicher Rangfolge-Rücktest (Auftrag Schritt 2) mit Datenbereinigung, Prüfregeln und
  Selbsttest (`python3 strategie.py selbsttest`, Ergebnis in `output/selbsttest.md`). Noch ohne Hypothesen.
- `fetch_fundamentals.py`: Bilanzdaten mit Meldedatum je Firma (`data/facts/`), vorher erweiterte Zuordnung
  Ticker → SEC-Nummer (`data/sec_meta_plus.json`, 2.500 von 2.831 Aktien). `bilanz.py`: daraus Kennzahlen je
  Stichtag, nur Erstmeldungen ab Meldedatum, Aktienzahl splitbereinigt mit Gegenprobe.
- `grafik.py` (Depotkurve gegen Markt und IWM, `output/depotkurve.png` und `.csv`) und `bericht.py`
  (`output/strategie_suche.md` aus den gespeicherten Ergebnissen): Abschlussarbeiten der Strategiesuche.
- `sturz.py`: Hypothese 8, Verlauf nach großen Tagesstürzen (`output/sturz.md`, `output/sturz.json`).
- `THEORIE.md`: Theorie „Fakten vor Geschichten", Strategie (Kern Indexfonds, Aufsatz A+) und die vorab
  festgelegten Regeln für die Auswertung des Probelaufs. Ohne neue Rechnung entstanden.
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

## Hypothesen (endgültig festgeschrieben am 13.11.2026, vor der ersten Rechnung)

Immer: monatlich, beste 10 % der handelbaren Aktien mit gültiger Kennzahl, gleich gewichtet (außer wo anders
angegeben). Bilanz-Hypothesen laufen nur auf den rund 2.170 Aktien mit SEC-Zuordnung, Werte zählen ab `filed`.

1. **Kursstärke.** Grund: Anleger reagieren zu langsam auf gute Nachrichten, Trends laufen weiter.
   a) Rendite der letzten 12 Monate ohne den letzten Monat. b) dasselbe über 6 Monate ohne den letzten Monat.
2. **Kursstärke nur bei soliden Firmen.** Grund: Trends bei Verlustfirmen und Verwässerern brechen öfter ab.
   a) Kennzahl 1a, nur Firmen mit positivem operativem Gewinn (letzte 4 Quartale) und Aktienzahl höchstens
   +2 % zum Vorjahr. b) wie a, aber Aktienzahl nicht gestiegen (≤ 0 %).
3. **Nähe zum 52-Wochen-Hoch.** Grund: Anleger zögern, über alte Höchstkurse zu kaufen, Kurse laufen nach.
   a) Schlusskurs geteilt durch höchsten Schlusskurs der letzten 252 Tage, beste 10 %. b) beste 20 %.
4. **Profitabel und günstig.** Grund: gute Firmen zu niedrigen Preisen werden unterschätzt.
   a) Rang nach operativem Gewinn je Vermögen plus Rang nach operativem Gewinn je Börsenwert.
   b) wie a, nur Aktien mit positiver Kennzahl 1a.
5. **Beschleunigung.** Grund: der Markt schreibt altes Wachstum fort und unterschätzt Wendepunkte.
   a) Umsatzwachstum zum Vorjahresquartal höher als im Quartal davor und operative Marge höher als im
   Vorjahresquartal; Rang nach Summe beider Veränderungen. b) wie a, nur Firmen mit positivem operativem Gewinn.
6. **Sinkende Aktienzahl.** Grund: Rückkäufe zeigen, dass die Firma Geld übrig hat und sich für günstig hält.
   a) die 10 % mit dem stärksten Rückgang der Aktienzahl zum Vorjahr. b) alle Firmen mit Rückgang ≥ 1 % und
   positivem operativem Gewinn.
7. **Ausschlussliste.** Grund: Verlierer meiden ist leichter als Gewinner finden.
   a) alle handelbaren Aktien ohne Verlustfirmen unter ihrem 200-Tage-Schnitt und ohne Firmen mit Aktienzahl
   über +10 % zum Vorjahr. b) zusätzlich ohne alle Verlustfirmen.

Gestrichen: „A+ als Beimischung" und der „Meiden"-Teil der Ausschlussliste. Beide Stufen wurden an Daten bis
November 2026 gefunden, der Abschlusszeitraum ist für sie also schon verbraucht; ein sauberer Test ist nicht
mehr möglich. Sie laufen weiter nur im wöchentlichen Probelauf ohne Geld.

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
- 13. November 2026, später: Hypothesenliste festgeschrieben (7 Hypothesen, A+ und Meiden gestrichen).
  Kurs-Hypothesen gerechnet (`python3 strategie.py kurs`, Zahlen in `output/strategie_ergebnisse.json`):
  1a Kursstärke 12 Monate **besteht knapp** (+14,4 % pro Jahr nach 0,4 % Kosten gegen Markt +6,3 %, genau 10 von
  15 Halbjahren vor beiden, ohne 3 beste +8,0 %). Vorbehalt: Vorsprung stammt vor allem aus 2020 bis 2022, in den
  letzten 5 Halbjahren −12, +1, +7, +2, −2 Punkte; fehlende Pleiten begünstigen gerade diese Kennzahl.
  1b (6 Monate), 3a und 3b (52-Wochen-Hoch) fallen durch (je 7 von 15). Verbraucht: 4 Varianten.
  Bilanz-Download gestartet (`python3 fetch_fundamentals.py`, Ziel `data/facts/`, Protokoll `data/facts.log`).
  Nächster Schritt: Bilanz-Kennzahlen mit Meldedatum bauen und Hypothesen 2, 4, 5, 6, 7 rechnen.
- 13. November 2026, Bilanz-Hypothesen: Zuordnung erweitert (vorher nur Firmen mit ≥ 10 Mio. $ Umsatz in
  2024/25, das war eine versteckte Auswahl mit Zukunftswissen), Bilanzdaten für 2.480 Firmen geladen,
  Abdeckung 79 % der handelbaren Aktien. Gerechnet mit `python3 strategie.py bilanz`: **alle 10 Varianten der
  Hypothesen 2, 4, 5, 6, 7 fallen durch.** Am nächsten dran: 5a Beschleunigung (11 von 15 Halbjahren vorn,
  +10,9 % pro Jahr, scheitert an „ohne 3 beste": +5,0 % gegen Markt +6,3 %) und 6b Rückkäufe (ohne 3 beste
  +7,3 %, aber nur 7 von 15 Halbjahren). Profitabel und günstig (4a) liegt nur in 3 von 15 Halbjahren vorn.
  Damit sind alle 14 Varianten verbraucht; einziger Finalist ist 1a Kursstärke 12 Monate.
  In den Bilanz-Regeln zusätzlich festgelegt (vor der Rechnung): Gewinnrendite über 100 % und Börsenwert unter
  zwei Tagesumsätzen gelten als Datenfehler; bei 5 werden beide Veränderungen auf ±100 Punkte begrenzt.
  Nächster Schritt: Abschlusstest für 1a, genau einmal (`abschluss_freigabe`), danach Bericht
  `output/strategie_suche.md` und Grafik Depotkurve gegen Markt (Skill dataviz).
- 13. November 2026, **Abschlusstest für 1a Kursstärke 12 Monate gelaufen, genau einmal** (Sperre in
  `protokoll/abschlusstest.json`, Zahlen in `output/abschlusstest.json`). 1.5.2025 bis 11.11.2026, 19 Monate, im
  Schnitt 226 Aktien: Strategie **+51.0 %** nach 0,4 % Kosten, Markt +47.4 %, IWM
  +44.6 %, SPY +35.6 %. Nach der Regel („nach Kosten vor beiden Vergleichen") **formal bestanden**,
  aber knapp (+3.6 Punkte in 19 Monaten, Rauschen liegt bei ±2 Punkten pro Jahr) und mit
  1,0 % Kosten +45.5 % gegen Markt +47.4 %: dann **hinter dem Markt**. Der ganze
  Vorsprung stammt aus Mai bis Oktober 2025 (+56 % gegen +26 %). Seit 1.11.2025:
  Strategie -3.5 %, Markt +17.4 %, IWM +15.0 %. Halbjahr Mai 2026: -15.6 % gegen Markt
  +2.9 %. Größter Rückgang -32 %. Keine Nachbesserung, keine Wiederholung.
  Keine Kaufempfehlung. Nächster Schritt: Bericht `output/strategie_suche.md` (alle 14 Varianten, auch die
  gescheiterten) und Abschlussgrafik Depotkurve gegen Markt (Skill dataviz).
- 13. November 2026, **Strategiesuche abgeschlossen.** Bericht `output/strategie_suche.md` mit allen 14 Varianten
  (auch den gescheiterten), Grafik `output/depotkurve.png` (Skill dataviz, Palette validiert; Aqua hat
  Kontrast 2,7:1, deshalb Endbeschriftungen plus CSV als Tabellenansicht). Ergebnis: **nichts Belastbares
  gefunden.** 1a bestand den Abschlusstest formal (+51,0 % gegen Markt +47,4 %), aber knapp, bei 1,0 % Kosten
  dahinter, Vorsprung aus einem Halbjahr, seit November 2025 klar hinter dem Markt. Keine Kaufempfehlung.
  Der Abschlusszeitraum (ab 1.5.2025) ist verbraucht: neue Hypothesen brauchen neue, ungesehene Monate oder
  andere Märkte. Der wöchentliche Probelauf läuft unverändert weiter. Offen und freiwillig: Pleiten und
  Übernahmen in die Daten holen (Überlebensverzerrung), Dividenden ergänzen, Hypothese 1a nach einem weiteren
  halben Jahr neuer Daten als reinen Beobachtungstest erneut ansehen (nicht als zweiten Abschlusstest).
- 13. November 2026, **Quelle für verschwundene Aktien geprüft** (nur wenige Abrufe, nichts Großes geladen, kein
  Code geändert). Ohne Anmeldung gibt es keine: `api.nasdaq.com` meldet „Symbol not exists" (TWTR, SHLD), Yahoo
  „may be delisted", Alpha Vantage mit Probeschlüssel liefert eine leere Liste, Stooq ist von diesem Container
  nicht erreichbar (Verbindung bricht ab, also ungeprüft). Frei abrufbar ist nur die Tiingo-Liste
  (`https://apimedia.tiingo.com/docs/tiingo/daily/supported_tickers.zip`, 0,8 MB): 7.420 US-Aktien-Einträge mit
  Kursende zwischen 11/2016 und 9/2026, davon 3.760 mit normalem Kürzel (3.052 mit mindestens einem Jahr Kursen).
  Übernahmen stehen drin (TWTR bis 28.10.2022), Pleiten unter dem späteren Kürzel mit Q (BBBYQ, SHLDQ) samt der
  Zeit nach dem Börsenrauswurf; einzelne fehlen (J.C. Penney, Frontier, Pier 1 nicht gefunden). Die Kurse selbst
  brauchen einen kostenlosen Tiingo-Schlüssel (50 Abrufe je Stunde, 1.000 je Tag, eventuell nur 500 Aktien je
  Monat, das ist unbestätigt) und sind deshalb ungetestet. **Der Nutzer will sich dort nicht anmelden.** Der Punkt
  bleibt offen, die Überlebensverzerrung bleibt in allen Ergebnissen; nicht erneut vorschlagen, außer er fragt.
- 13. November 2026, Nebenaufgabe: wikifolio „Unrecognized potential" (`wfunrecpot`, Trader TomKoehler) angesehen,
  Frage des Nutzers: wie hat der Trader die Aktien vor den Kurssprüngen gefunden? Nur gelesen, was ein Besucher
  ohne Anmeldung sieht (keine Registrierung durch das Skript, keine versteckten Abrufe). Sichtbar: Handelsidee
  (kleine und mittlere Aktien, Finanzkennzahlen, RSI und SMA für den Einstieg, Management), Kennzahlen (+94,8 %
  seit 24.6.2023, 1 Jahr −3,1 %, 1 Monat −20,0 %, Höchststand 341,0, Stand 194,9, also −43 % unter dem Hoch,
  Schwankung 52,6 % pro Jahr, investiert 11.104 €), heutige Zusammensetzung (11 Aktien: 45 % in sechs kleinen
  Bergbau- und Explorationsfirmen, davon 24 % allein Tectonic Metals; 49 % Öl, Tanker, Bohrinseln; 5 % Sea),
  letzter Kauf Chevron am 30.10.2026. Seine zwei anderen wikifolios liegen bei +11,5 % seit 2/2024 und +0,2 %
  seit 11/2025. **Nicht sichtbar ohne Anmeldung: Trades (Kaufdaten), Kommentare, Kursverlauf.** Die Frage ist
  deshalb noch nicht beantwortet; ohne Kaufdaten lässt sich Können nicht von einer Rohstoffwette unterscheiden.
- 13. November 2026, **Hypothese 8 festgeschrieben, noch nicht gerechnet** (Nutzer wollte nach dem wikifolio-Blick
  wissen, ob es nach großen Tagesstürzen einen Trend gibt). Vorbehalte, die der Nutzer kennt: die Liste war als
  endgültig festgelegt, dies ist die letzte erlaubte Hypothese (Obergrenze 8); der Zeitraum ab 1.5.2025 ist
  verbraucht, also nur Beobachtung, keine Grundlage für Geld; fehlende Pleiten machen „nach dem Sturz kaufen"
  zu günstig, glaubwürdig wäre nur ein Ergebnis „fällt weiter, meiden".
  **8. Sturz-Ereignisse.** Grund: Nach schlechten Quartalszahlen reagieren Anleger zu langsam (Fortsetzung); ohne
  Nachricht wird ein Teil der Überreaktion oft aufgeholt. Ereignis: Tagesverlust ≥ 10 % bei ≥ 3-fachem
  20-Tage-Umsatz, Kurs des Vortags ≥ 3 $, 20-Tage-Umsatz ≥ 1 Mio. $. a) mit Quartalsmeldung (8-K 2.02) am selben
  Tag oder Vortag, b) ohne. Messung: Kauf zur Eröffnung des Folgetags, Abstand zum Durchschnitt der liquiden
  Aktien nach 5, 20 und 60 Handelstagen, 0,4 % Kosten, nur bis 30.4.2025, ohne Überlappung je Aktie.
  Kurs-Download für diese Aufgabe als Hintergrundbefehl gestartet (`python3 fetch_history.py prices`, Protokoll
  `data/download.log`). Nächster Schritt (mittel): Ereignisse zählen und rechnen, Ergebnis ehrlich berichten.
- 13. November 2026, **Hypothese 8 (Sturz-Ereignisse) gerechnet, einmal: durchgefallen.** `python3 sturz.py`,
  Ergebnis in `output/sturz.md`. Bis 30.4.2025 gab es 6.850 Ereignisse; Quartalstermine liegen erst ab 6/2021 vor,
  deshalb a) 2.250 mit und b) 1.125 ohne Quartalszahlen, der Rest nicht zuzuordnen. Abstand zum Markt nach 0,4 %
  Kosten: a) −0,7 % / −1,0 % / −0,8 % nach 5 / 20 / 60 Tagen, b) +0,1 % / −0,7 % / −1,2 %; alle Stürze seit 2016
  ungetrennt −1,0 % / −1,2 % / −0,9 %. Nur 43 bis 48 % der Fälle enden im Plus, kein Jahr klar positiv.
  **Keine Erholung nach Stürzen, also kein Kaufsignal**, und wegen der fehlenden Pleiten ist die Wahrheit eher
  noch schlechter. Als Meide-Signal ist der Effekt echt, aber klein (vor Kosten rund −0,6 % in 20 Tagen) und
  zwischen „mit" und „ohne" Quartalszahlen nicht unterscheidbar. Der Zeitraum ab 1.5.2025 wurde nicht angesehen.
  Damit sind alle 8 Hypothesen verbraucht; keine weitere rechnen. Festgelegt beim Bauen (vor dem Ergebnis):
  Mindestabstand 60 Handelstage je Aktie, Unsicherheit über Monatsmittel.
- 13. November 2026, **Theorie und Strategie aufgeschrieben, nichts gerechnet** (`THEORIE.md`). Auftrag des
  Nutzers: eine Theorie und Strategie, wie mehr Wachstum als der Markt zu holen ist, ohne neue Rechnung, ohne
  Wiederholung, ohne Nachbesserung. Ergebnis: Eine verlässliche Strategie gibt es nicht. Die einzige Stelle mit
  einer Erklärung, wer den Vorsprung bezahlt, ist der Unterschied zwischen Sprüngen mit Quartalszahlen (A+, rund
  +13 Punkte) und ohne (Meiden, rund −10 Punkte): „bei kleinen Aktien ist der Markt langsam mit Fakten und
  schnell mit Geschichten". Strategie: Kern mindestens 80 % Indexfonds, Aufsatz höchstens 20 % nur A+ (2 % je
  Kauf, höchstens 10 Positionen, 60 Handelstage, kein Stopp), Stufe A gehört nicht dazu. Eigene Einschätzung:
  etwa eins zu drei, dass nach Kosten etwas bleibt. **Auswertung des Probelaufs vorab festgelegt** (vor dem
  ersten abgeschlossenen 60-Tage-Fall, der Anfang Februar 2027 endet): Abstand zum Markt nach 60 Handelstagen
  abzüglich 1,0 % Kosten, ohne Stopp, alle A+-Signale ab 3.11.2026; erste Auswertung nach 40 Fällen, zweite nach
  80; verwerfen bei Durchschnitt ≤ 0; kleines echtes Geld erst bei ≥ +5 Punkten und ohne die drei besten Fälle
  noch über 0; dazwischen weiter ohne Geld. Bis dahin keine Kaufempfehlung. Diese Regeln nicht mehr ändern,
  sobald der erste Fall abgeschlossen ist. Nächster Schritt (leicht, nur auf „weiter"): `weekly.py` so ergänzen,
  dass `protokoll/stand.md` A+ getrennt nach genau dieser Messgröße zeigt (Zahl abgeschlossener Fälle, Durchschnitt
  nach 1,0 % Kosten, ohne die drei besten) und Meiden-Signale mitschreibt. Das ändert das Skript der geplanten
  Aufgabe, deshalb nur mit Zustimmung des Nutzers.
