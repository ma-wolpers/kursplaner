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

## Geplant (Mathematik)

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

## Geplant (Nachpflege bestehender Einheiten)

- Nach der Einheitserstellung sollen `Kompetenzen`, `Stundenziel`, `Inhalte` und `Methodik` einzeln nachpflegbar sein.
- UI-Zielbild:
  - dieselben Overlay-gestuetzten Auswahlmechaniken wie im Erstell-Dialog,
  - Tastatursteuerung (Pfeile, Enter/Leertaste) und Mausauswahl,
  - Mehrfachauswahl mit verwaltbaren Chips fuer Inhalte/Methodik.
- UseCase-Zielbild:
  - feldgenaue Write-Operationen ohne Nebenwirkung auf andere Bereiche,
  - konsistente Validierung und Delta-faehiges Undo/Redo fuer jede Einzelnachpflege.

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
