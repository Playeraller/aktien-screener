"""Bericht output/strategie_suche.md aus output/strategie_ergebnisse.json und output/abschlusstest.json erzeugen."""
import json, os
import numpy as np
from common import OUT

E = json.load(open(os.path.join(OUT, "strategie_ergebnisse.json")))
A = json.load(open(os.path.join(OUT, "abschlusstest.json")))
pz = lambda x, n=1: f"{x * 100:+.{n}f} %".replace(".", ",")
pk = lambda x, n=1: f"{x * 100:.{n}f}".replace(".", ",")
GRUND = {"1a": "Anleger reagieren zu langsam, Trends laufen weiter", "1b": "wie 1a, kürzerer Zeitraum",
         "3a": "Anleger zögern bei alten Höchstkursen", "3b": "wie 3a, breiter",
         "2a": "Trends bei Verlustfirmen und Verwässerern brechen öfter ab", "2b": "wie 2a, strenger",
         "4a": "gute Firmen zu niedrigen Preisen werden unterschätzt", "4b": "wie 4a, nur bei steigendem Kurs",
         "5a": "der Markt unterschätzt Wendepunkte im Wachstum", "5b": "wie 5a, nur profitable Firmen",
         "6a": "Rückkäufe zeigen Geld und Vertrauen", "6b": "wie 6a, als Filter",
         "7a": "Verlierer meiden ist leichter als Gewinner finden", "7b": "wie 7a, strenger"}
out = ["# Strategiesuche: Gibt es eine regelbasierte US-Aktienauswahl, die den Markt nach Kosten schlägt?", "",
       "Stand: 13. November 2026. Alle Zahlen stammen aus `strategie.py`, `output/strategie_ergebnisse.json` und "
       "`output/abschlusstest.json`.", "", "## Ergebnis in Kürze", "",
       f"- **Von 14 geprüften Varianten (7 Hypothesen) hat genau eine den Entwicklungszeitraum bestanden:** "
       f"Kursstärke über 12 Monate (1a). Alle anderen 13 sind durchgefallen.",
       f"- **Im einmaligen Abschlusstest** (1.5.2025 bis 11.11.2026, 19 Monate) lag 1a nach 0,4 % Kosten bei "
       f"{pz(A['strategie'])}, der Markt bei {pz(A['markt'])}, IWM bei {pz(A['iwm'])}. Nach der Regel formal bestanden.",
       f"- **Belastbar ist das nicht.** Der Vorsprung beträgt {pk(A['strategie'] - A['markt'])} Punkte in 19 Monaten "
       f"(Zufall schwankt um ±2 Punkte pro Jahr), verschwindet bei 1,0 % Kosten ({pz(A['strategie_1pct'])} gegen Markt "
       f"{pz(A['markt'])}) und stammt aus Mai bis Oktober 2025. Seit November 2025 lief die Strategie deutlich hinter dem "
       f"Markt.", "- **Empfehlung: kein Geld auf diese Strategie.** Ein ehrliches „nichts Belastbares gefunden“ ist das Ergebnis.", "",
       "![Depotkurve gegen Markt](depotkurve.png)", "",
       "Tabellenansicht der Kurven: `output/depotkurve.csv`.", "", "## So wurde geprüft", "",
       "- Monatlich alle handelbaren Aktien (Kurs ≥ 3 $, 20-Tage-Umsatz ≥ 1 Mio. $) nach einer Kennzahl ordnen, "
       "die besten 10 % kaufen, gleich gewichten, immer voll investiert. Kauf zur Eröffnung des Folgetags.",
       "- Kosten 0,4 % für Kauf und Verkauf zusammen, zusätzlich eine Rechnung mit 1,0 %.",
       "- Vergleich: Durchschnitt der handelbaren Aktien und IWM, beide voll investiert, ohne Kosten.",
       "- Entwicklung Dezember 2017 bis April 2025 (89 Monate, 15 Halbjahre), Abschlusstest ab Mai 2025, "
       "je Strategie genau einmal. Hypothesen vorher festgeschrieben (Commit „Hypothesenliste vor der ersten Rechnung "
       "festgeschrieben“).",
       "- Bilanzdaten zählen erst ab ihrem Meldedatum (SEC `filed`), nur Erstmeldungen.",
       "- Bestanden heißt im Entwicklungszeitraum: in mindestens 10 von 15 Halbjahren vor Markt **und** IWM, und auch "
       "ohne die drei besten Aktien je Halbjahr noch vor dem Markt.", "",
       "### Prüfung des Rücktests selbst (`output/selbsttest.md`)", "",
       "- Zufallsauswahl landet beim Markt (+6,2 bis +6,3 % pro Jahr gegen +6,3 %, 500 Läufe, 90 % der Läufe zwischen "
       "+4,2 und +8,5 %).",
       "- Auswahl mit Zukunftswissen ist unrealistisch gut (+1.365 % pro Jahr; mit nur einem Tag Vorsprung +68 %), "
       "dieselbe Kennzahl ohne Vorsprung bringt 0 %.",
       "- Die Regel „ohne die 3 besten“ kostet allein rund 4 Punkte pro Jahr. Reiner Zufall besteht die Hürden in "
       "höchstens 0,8 % der Läufe.", "", "## Alle geprüften Varianten (Entwicklungszeitraum)", "",
       f"Markt {pz(E['1a Kursstärke 12 Monate']['markt_pa'])} pro Jahr, IWM {pz(E['1a Kursstärke 12 Monate']['iwm_pa'])} pro Jahr "
       "(beide ohne Dividenden).", "",
       "| Variante | Grund (vorher festgelegt) | Aktien | pro Jahr nach 0,4 % | nach 1,0 % | Halbjahre vor beiden (nötig 10) | "
       "ohne 3 beste pro Jahr | Urteil |", "|---|---|---|---|---|---|---|---|"]
for name, z in sorted(E.items()):
    out.append(f"| {name} | {GRUND.get(name[:2], '')} | {z['titel']} | {pz(z['pa'])} | {pz(z['pa10'])} | {z['vorn']} von "
               f"{z['n_hj']} | {pz(z['ohne3_pa'])} | {'bestanden' if z['bestanden'] else 'durchgefallen'} |")
out += ["", "Nicht gerechnet, weil kein sauberer Test mehr möglich ist: „A+ als Beimischung“ und der „Meiden“-Teil der "
        "Ausschlussliste. Beide Regeln wurden an Daten bis November 2026 gefunden, der Abschlusszeitraum ist für sie "
        "also verbraucht. Sie laufen nur im wöchentlichen Probelauf ohne Geld weiter.", "",
        "## Abschlusstest für 1a im Detail", "",
        "| Zeitraum | Strategie | Markt | IWM |", "|---|---|---|---|"]
for h in A["hj"]:
    out.append(f"| Halbjahr ab {h} | {pz(A['hj'][h])} | {pz(A['hj_markt'][h])} | {pz(A['hj_iwm'][h])} |")
out += [f"| **gesamt (19 Monate)** | **{pz(A['strategie'])}** | **{pz(A['markt'])}** | **{pz(A['iwm'])}** |",
        f"| gesamt mit 1,0 % Kosten | {pz(A['strategie_1pct'])} | | |", "",
        "Das Halbjahr ab November 2026 enthält nur die ersten Tage (bis 11.11.2026). Größter Rückgang der Strategie im "
        f"Abschlusstest {pz(A['rueckgang'], 0)}.", "", "## Warum ich der bestandenen Variante nicht traue", "",
        "1. **Zu knapp.** 3,6 Punkte Vorsprung in 19 Monaten liegen im Rauschen der Zufallsauswahl.",
        "2. **Kosten.** Mit 1,0 % Kosten (realistisch für kleine, wenig gehandelte Aktien) liegt sie hinter dem Markt.",
        "3. **Ein einziges gutes Halbjahr.** Mai bis Oktober 2025 liefert den ganzen Vorsprung. Im Halbjahr ab Mai 2026 "
        "verlor die Strategie 15,6 %, der Markt gewann 2,9 %.",
        "4. **Gleiches Muster im Entwicklungszeitraum.** Der Vorsprung stammt dort vor allem aus 2020 bis 2022, in den "
        "letzten fünf Halbjahren war er kaum noch vorhanden. Typisch für einen Effekt, der verschwindet, sobald ihn "
        "viele nutzen.",
        "5. **Momentum-Rückschläge sind bekannt.** Aktien, die stark gestiegen sind, fallen bei einer Marktwende oft "
        "gemeinsam und stark. Der größte Rückgang im Abschlusstest lag bei −32 %.", "",
        "## Grenzen der Daten", "",
        "- **Überlebensverzerrung.** Das Universum sind heute gelistete Aktien ab 100 Mio. $ Börsenwert. Pleiten und "
        "Übernahmen fehlen. Das begünstigt vor allem Kursstärke, die echten Ergebnisse waren schlechter. Wie viel, ist "
        "mit diesen Daten nicht messbar. Im 19-Monats-Abschlusstest ist die Verzerrung klein.",
        "- **Dividenden fehlen** bei Strategie, Markt, IWM und SPY. Der Vergleich bleibt fair, die absoluten Renditen "
        "sind zu niedrig.",
        "- **Abdeckung der Bilanzdaten:** 79 % der handelbaren Aktien (2.500 von 2.831 Aktien sind der SEC zugeordnet; "
        "ausländische Firmen fehlen weitgehend). Die Bilanz-Varianten liefen nur auf dieser Teilmenge, die im "
        "Durchschnitt +6,9 % statt +6,3 % pro Jahr brachte.",
        "- **Kurzer Zeitraum.** Zehn Jahre Kurse, davon 7,4 Jahre Entwicklung. 15 Halbjahre sind wenig, um zu "
        "unterscheiden, ob ein Vorsprung echt ist.",
        "- **Datenfehler** wurden bereinigt (11 Kursausreißer, 14 Niveausprünge, Aktienzahlen mit Gegenprobe). Echte "
        "Kursstürze blieben drin.",
        "- **Mehrfachtest.** 14 Varianten wurden gerechnet; unter so vielen besteht eine auch per Zufall einmal. Im "
        "Selbsttest besteht reiner Zufall die Hürden in höchstens 0,8 % der Läufe, bei 14 Versuchen also gelegentlich.",
        "", "## Was daraus folgt", "",
        "- Diese Suche hat keine Strategie gefunden, mit der ich Geld riskieren würde.",
        "- Gelernt: Einfache Bilanzkennzahlen (günstig, profitabel, Wachstum, Rückkäufe) schlagen den Markt hier nicht. "
        "Reine Kursstärke über 12 Monate hatte zeitweise einen Vorsprung, der aber instabil ist.",
        "- Nicht tun: 1a nachbessern oder den Abschlusstest wiederholen. Die Daten ab Mai 2025 sind jetzt verbraucht; "
        "jede neue Hypothese braucht einen neuen, bisher ungesehenen Zeitraum (also abwarten, bis neue "
        "Monate vorliegen) oder andere Märkte.",
        "- Weiter sinnvoll: der wöchentliche Probelauf ohne Geld für A, A+ und Meiden läuft weiter und liefert "
        "echte Zukunftsdaten.", ""]
open(os.path.join(OUT, "strategie_suche.md"), "w").write("\n".join(out))
print(len(E), "Varianten im Bericht")
