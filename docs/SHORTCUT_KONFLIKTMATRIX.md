# Shortcut-Konfliktmatrix

Stand: 2026-03-31

Quelle der aktuellen Belegung:
- `kursplaner/adapters/gui/screen_builder.py` (`_bind_shortcuts`)
- `kursplaner/adapters/gui/help_catalog.py` (`MAIN_WINDOW_HELP`)

## Aktuelle Bewertung

| Aktion | Shortcut | Merkregel | Didaktischer Zusatz | Typische Belegung anderswo | Risiko | Bewertung |
|---|---|---|---|---|---|---|
| Neu | Strg+N | N = Neu | Standardanker aus vielen Programmen. | Neu | niedrig | gut |
| Refresh | Strg+R | R = Reload | R stuetzt Neu-laden als Auffrischung. | Reload/Run/Replace je nach App | mittel | ok, aber merkbar |
| Undo | Strg+Z | Z = Zurueck | Klare Rueckwaerts-Assoziation. | Undo | niedrig | Standard |
| Redo | Strg+Y | Y = Wiederherstellen | Standard-Ergaenzung zu Strg+Z. | Redo | niedrig | Standard |
| Unterricht markieren | Strg+U | U = Unterricht | Direkter Buchstabenbezug zur Funktion. | Unterstreichen (manche Editoren) | niedrig | gut |
| Bis Ferien erweitern | Strg+E | E = Erweitern | E markiert den Schritt in die Zukunft. | Suche/Explorer/Align je nach App | mittel | ok |
| Ausfall markieren | Strg+Q | Q = Querstrich im Ablauf | Q steht als Bruch im regulaeren Fluss. | App schließen (einige Programme) | mittel | akzeptabel |
| Hospitation markieren | Strg+O | O = hOspitation | Auffaelliger Buchstabe O als Anker. | Datei öffnen | mittel | akzeptabel |
| LZK markieren | Strg+K | K = LeistungsKontrolle | K referenziert den Kernbegriff Kontrolle. | Link/Command in Editoren | mittel | akzeptabel |
| Einheit kopieren | Strg+C | C = Copy | Vertrauter Workflow-Standard. | Kopieren | niedrig | Standard |
| Einheit einfügen | Strg+V | V = Einfuegen | Standardpaar zu Strg+C. | Einfügen | niedrig | Standard |
| Markdown verknüpfen | Strg+G | G = Gehe zu Datei | G erinnert an Go-to bzw. Verknuepfung. | Go to / Find next | mittel | ok |
| Einheit leeren | Strg+Entf | Entf = Entfernen | Symbolische Loeschaktion passt direkt. | Wort rechts löschen (Textfelder) | mittel | ok, kontextabhängig |
| Split | Strg+T | T = Teilen | T koppelt die Funktion an Teilen. | Neuer Tab / Transpose | mittel | ok |
| Merge | Strg+M | M = Merge | Eindeutiger Initialbuchstabe. | Marker/Mode je nach Editor | mittel | ok |
| Ausfall zurücknehmen | Strg+B | B = Back | Rueckkehr zur regulaeren Planung. | Fett | mittel | ok |
| Spalte links/rechts | Strg+Links/Rechts | Pfeil = Richtung | Bewegungsrichtung ist direkt codiert. | Wortweise Navigation | mittel | ok, aber lernrelevant |
| UB-Übersicht | Strg+Shift+U | U = Unterrichtsbesuch | Shift trennt Uebersicht von Markieren. | selten standardisiert | niedrig | gut |
| Shortcut-Übersicht | Strg+H | H = Hilfe | H liefert schnellen Zugang zur Lernhilfe selbst. | Verlauf/Replace je nach App | mittel | gut merkbar |

## Kurzfazit

- Kritische Klassiker bleiben frei: `Strg+S`, `Strg+F`, `Strg+A`, `Strg+X`.
- Verbleibende Belegungen sind überwiegend mittleres Risiko, durch Modus-Gating vertretbar.
- Größte Kandidaten für spätere Entschärfung: `Strg+O`, `Strg+Q`, `Strg+T`, `Strg+Links/Rechts`.
- Shortcut-Merkregeln werden zentral in `kursplaner/resources/shortcuts/shortcut_guide.json` gepflegt.
