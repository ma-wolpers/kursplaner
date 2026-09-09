# Geplante Implementationen: Kursplaner-Erweiterungen

Stand: 2026-03-09

Dieses Dokument ist das zentrale Sammeldokument fuer alle kuenftigen Erweiterungen des Kursplaners.
Es werden keine separaten Einzel-Dokumente pro Erweiterung angelegt.

## Zielbild

Die Unterrichtserstellung soll fachspezifische Kompetenzauswahl strukturiert und schichtensauber unterstuetzen:

- GUI sammelt nur Eingaben
- UseCase validiert und orchestriert
- Domain liefert Kompetenzkataloge und Regeln
- Repository persistiert Metadaten im Frontmatter

Keine direkte Fachlogik im Adapter, keine I/O-Logik im Domain-Layer.

## Bereits umgesetzt (Informatik)

- Kompetenzkataloge fuer Informatik hinterlegt:
  - Sek I (Stufe 5-10)
  - Sek II (Stufe 11-13)
- Bei neuer Informatik-Unterrichtseinheit:
  - Auswahl eines KC-Profils
  - Mehrfachauswahl prozessbezogener Kompetenzen
  - Einzelauswahl einer inhaltsbezogenen Kompetenz als Stundenziel
- Persistenz in Plan-Frontmatter:
  - KC-Profil
  - Kompetenzen (Liste)
  - Stundenziel
- Datenquelle:
  - JSON-Dateien unter `kursplaner/resources/kompetenzkataloge/`
  - Manifest `catalog_manifest.json` + gemeinsame Fachdatei `informatik.json` mit mehreren Profilen
  - Wenn eine benoetigte Datei fehlt/ungueltig ist: Rueckfrage (Ersatzpfad waehlen oder ohne Datei fortfahren)

## Bereits umgesetzt (Bedienhilfe Shortcuts)

- In der GUI gibt es eine Shortcut-Uebersicht (Ansicht-Menue und `Strg+H`).
- Die Uebersicht zeigt alle `Strg+...`-Kuerzel mit Funktion, Merkregel und didaktischem Zusatz.
- Datenquelle ist zentral als JSON gepflegt: `kursplaner/resources/shortcuts/shortcut_guide.json`.
- Shortcut-Wiring der Hauptansicht nutzt dieselbe Quelle, damit Anzeige und Bindings konsistent bleiben.

## Bereits umgesetzt (UB-Dialoge und Vergangenheitsregel)

- Im Dialog **Einheit planen** (Strg+U-Flow) werden unten die letzten UB-Punkte angezeigt:
  - Fach: Professionalisierungsschritte
  - Fach: Nutzbare Ressourcen
  - Pädagogik: Professionalisierungsschritte
  - Pädagogik: Nutzbare Ressourcen
- Auswahl der "letzten" UB-Einträge ist vergangenheitsbasiert und schließt zukünftige Besuche aus.
- Für das aktuelle Datum gilt eine konfigurierbare Cutoff-Uhrzeit (Standard `15:00`):
  - vor Cutoff zählt `heute` noch nicht als Vergangenheit,
  - ab Cutoff zählt `heute` als Vergangenheit.
- Die Cutoff-Uhrzeit ist in **Datei → Einstellungen…** editierbar und wird in `config/ui_preferences.json` als `ub_past_cutoff_time` gespeichert.
- Die gleiche Regel wird konsistent in beiden Stellen genutzt:
  - UB-Achievements-Ansicht,
  - Laden der letzten UB-Punkte für Dialoge.
- In der UB-Achievements-Ansicht zeigen die Kacheln wieder den numerischen Fortschritt (`current/target`, z. B. `1/4`); nicht erfüllte Symbole sind dunkler dargestellt.

## Geplant (Mathematik) — KC-Katalog für Einheiten-Erstellung

### Fachliche Erweiterung

- Domain-Modul um Mathematik-Katalog(e) erweitern
- Katalogzuordnung nach Jahrgangsstufe und ggf. Schulzweig
- Stabiler Katalog-Identifier analog zu Informatik

### UseCase-Erweiterung

- NewLessonFormUseCase um Mathematik-Optionen erweitern
- Validierung von:
  - Mehrfachauswahl (prozessbezogene Kompetenzen)
  - Einzelauswahl (Stundenziel)
- Einheitliche Rueckgabe in StartRequest (fachunabhaengig)

### GUI-Erweiterung

- Wiederverwendung derselben UI-Bausteine wie bei Informatik
- Dynamisches Umschalten je Fach
- Keine Duplizierung von Fachlogik im Fenstercode

### Persistenz

- Frontmatter-Struktur fachunabhaengig halten:
  - KC-Profil
  - Kompetenzen
  - Stundenziel
- Optional spaeter: fachspezifische Zusatzfelder (nur bei echtem Bedarf)

## Geplant (Kompetenznetz-Graph-Popup)

**Abgrenzung zum KC-Katalog (siehe oben):** komplett getrenntes Feature. Der KC-Katalog
ist eine flache, JSON-basierte Textliste für die Kompetenzauswahl beim Erstellen einer
Einheit (Informatik heute, Mathematik geplant). Das Kompetenznetz-Graph-Popup liest
stattdessen das bereits im Vault existierende, verlinkte Markdown-Kompetenznetz unter
`34 Fachinhalte\<Fach>\` (Ober-/Teilkompetenz- und Fort-/Voraussetzungs-Beziehungen als
Obsidian-Wikilinks im YAML-Frontmatter) und stellt es zum Nachschlagen/Zitieren als
interaktiven Graphen dar. Beide Systeme bleiben unabhängig, keine Vereinheitlichung.

**Architektur ist bewusst fachoffen, nicht Mathematik-spezifisch**: Mathematik ist
aktuell der einzige real vorhandene, nach diesem Schema strukturierte Datenbestand
(~480 Dateien) — Repository/Domain/Filter/Layout enthalten aber an keiner Stelle
Mathematik-spezifische Logik. Ein weiteres Fach wird automatisch erkannt, sobald sein
Ordner dieselbe Struktur erfüllt (mindestens eine Kompetenz-Datei nach dem
`<Kürzel>-<Nummer>`-Muster plus ein `Bereiche\`-Unterordner).

**Umsetzungsstand** (Meilensteine gemäß Implementierungsplan
`ich-m-chte-im-kursplaner-prancy-gray.md`):

- ✅ Meilenstein 1 — Domain-Modell, PyYAML-freies Mapping, Validierung, DAG-Diagnose,
  zentrale Sichtbarkeits-Pipeline (Filter → Matchingtiefe → Fokus). Siehe
  DEVELOPMENT_LOG-Eintrag vom 2026-09-09. Reine Domain-Schicht, noch ohne
  Dateisystem-Zugriff/GUI.
- ✅ Meilenstein 2 — Repository (PyYAML, einzige Importstelle), Port, app-lokaler Cache,
  Usecases, Wiring. Siehe DEVELOPMENT_LOG-Eintrag vom 2026-09-09. Noch kein Popup/GUI.
- ✅ Meilenstein 3 — Popup-Grundgerüst, Sidebar mit Filtern, Detailbereich (noch ohne
  Graph-Canvas). Siehe DEVELOPMENT_LOG-Eintrag vom 2026-09-09. Menüpunkt „Kompetenznetz
  anzeigen…" (Strg+Shift+K) bereits nutzbar (Filter, Liste, Detail, Zitat-Kopieren);
  rechte Spalte zeigt bis Meilenstein 4 eine einfache Liste statt des Graphen.
- ✅ Meilenstein 4 — tkinter-Canvas-Renderer, Sugiyama-artiges Layout mit
  Crossing-Minimierung, Zoom/Pan. Siehe DEVELOPMENT_LOG-Eintrag vom 2026-09-09.
  View-Mode-Umschaltung (Segmented-Control + Strg+Tab) bereits nutzbar.
- ⬜ Meilenstein 5 — Fokus-Modus, Pfeiltasten-Kegel-Navigation, Hover-Tooltip,
  Recentering, Unresolved-Link-Darstellung.

## Geplant (Nachpflege bestehender Einheiten)

- Nach der Einheitserstellung sollen `Kompetenzen`, `Stundenziel`, `Inhalte` und `Methodik` einzeln nachpflegbar sein.
- UI-Zielbild:
  - dieselben Overlay-gestuetzten Auswahlmechaniken wie im Erstell-Dialog,
  - Tastatursteuerung (Pfeile, Enter/Leertaste) und Mausauswahl,
  - Mehrfachauswahl mit verwaltbaren Chips fuer Inhalte/Methodik.
- UseCase-Zielbild:
  - feldgenaue Write-Operationen ohne Nebenwirkung auf andere Bereiche,
  - konsistente Validierung und Delta-faehiges Undo/Redo fuer jede Einzelnachpflege.

## Bereits umgesetzt (Jahrgangsstufen-Achievements)

- Die Jahrgangsstufe kommt ausschließlich aus der `Stufe` des Kurses, zu dem die UB-markierte
  Einheit gehört (Single Source of Truth) — UB-Dateien tragen kein eigenes Jahrgangsstufe-Feld
  mehr (`QueryUbAchievementsUseCase._build_course_stufe_map`, siehe DEVELOPMENT_LOG 2026-08-30).
- Alle Achievement-Vorgaben (bestehende Halbzeit/Voll/UBplus/BUB-Schwellenwerte **und**
  Jahrgangsstufen-Gruppen) liegen gemeinsam in `kursplaner/resources/achievements/requirements.json`
  (ein gemeinsames JSON statt Zahlen im Usecase + separater Jahrgangsstufen-Datei).
- **Paedagogik ist scharf konfiguriert**: je mind. 1 UB in 5./6., 7.-10., 11.-13. — sichtbar
  im Achievements-Tab.
- **Offen**: konkrete Grenzen/Mindestanzahlen fuer Mathematik/Informatik/Darstellendes Spiel
  mit dem Nutzer klaeren, dann `requirements.json` ergaenzen (nur Datenaenderung, kein Code).

## Architekturleitplanken

- Composition Root bleibt [kursplaner/adapters/bootstrap/wiring.py](kursplaner/adapters/bootstrap/wiring.py)
- Kein direkter Zugriff von GUI-Adaptern auf `infrastructure`
- Keine Fachentscheidungen in Widgets/Controllern
- Domain und UseCases testbar ohne GUI

## Offene Entscheidungen (fuers naechste Inkrement)

1. Mathematik-KC-Quelle und Granularitaet:
   - Einheitlicher Katalog oder mehrere Teilkataloge je Leitidee?
2. Pflichtgrad bei Auswahl:
   - Muessen immer Kompetenzen + Stundenziel gesetzt werden oder nur empfohlen?
3. Darstellung in bestehenden Planansichten:
   - Sichtbar direkt in Uebersicht oder nur in Detailansicht?
