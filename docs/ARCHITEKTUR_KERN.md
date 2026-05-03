# kursplaner – Architektur-Kernregeln

## Ziel
Dieses Dokument definiert den **dauerhaft gültigen Architektur-Kern** des kursplaners.

Es gilt als verbindliche Leitlinie für jede Änderung am Code.

---

## 1) Programmkern

Der Programmkern beantwortet ausschließlich: **„Was ist fachlich richtig?“**

Zum Kern gehören:

- Kursplan-Tabelle (`Datum`, `Stunden`, `Inhalt`; dabei bedeutet `Stunden` die Dauer einer Einheit)
- Verlinkte Einheiten-Dateien (YAML + optionale Inhalte)
- Termin-/Ferienlogik
- Fachliche Planoperationen (Ausfall, LZK, Split/Merge, Verschieben, Zuordnen)
- Delta-basierte Änderungs- und Undo/Redo-Logik
- Daily-Reporting als fachlicher Snapshot-Use-Case (z. B. Tages-JSON über aktuelle/future Einheiten)

Verbindliche Kernregel Datenvalidierung:

- Zentrale Daten werden strikt validiert, nicht heuristisch "gerettet".
- Pflichtfelder mit festen Standards sind harte Invarianten (z. B. `Kursfach`, `Stufe`, `Stundentyp`, `Dauer`).
- Bei Verstoß wird der Ablauf mit klarer Fehlermeldung abgebrochen; es gibt keine stillen Alias-/Fallback-Umdeutungen.
- Validierung sitzt im Kern (Domain/Application/Infrastructure), nicht nur in der GUI.

Nicht zum Kern gehören:

- GUI/CLI-Widgets und Event-Handling
- Dialoge/Messageboxen/Dateiauswahl
- konkrete I/O-Details (Dateisystem, YAML-Parser, Markdown-Parsing, ICS-Dateien)

---

## 2) Schichtenmodell (verbindlich)

### Domain
Verantwortlich für:

- Invarianten und Fachregeln
- fachliche Zustandsänderungen
- fachliche Datentypen

Nicht verantwortlich für:

- I/O
- GUI/CLI

### Use Cases (Application Layer)
Verantwortlich für:

- Orchestrierung einer Nutzerabsicht
- Transaktionsgrenze (`laden -> ändern -> speichern`)
- Konfliktauflösung als fachliche Strategie
- Erzeugung von Delta-Änderungen
- fachliche Snapshot-/Export-Orchestrierung (inkl. Datumsfilter und Datenzuschnitt)

Nicht verantwortlich für:

- GUI-Details
- Dateiformat-Parsing-Details

### Ports
Verantwortlich für:

- abstrakte Verträge für Plan-, Stunden- und Kalenderzugriffe

### Infrastructure
Verantwortlich für:

- konkrete Repository-Implementierungen
- Dateisystem-/Markdown-/YAML-/ICS-Implementierungen

### Adapter (GUI/CLI)
Verantwortlich für:

- Input sammeln
- Bestätigungen einholen
- Use Cases aufrufen
- Ergebnisse anzeigen
- Kontext-Hilfen für komplexe UI-Elemente bereitstellen (z. B. prägnante Hover-Erklärungen), damit Bedienung ohne Interna-Wissen möglich ist

Verbindliche UX-Regel für Adapter:

- Bei jedem neuen oder geänderten, nicht-trivialen GUI-Element wird geprüft, ob eine kurze Hover-Erklärung nötig ist.
- Priorität dieser Prüfung ist gleichrangig zu Methoden-Docstrings: **immer mitdenken**.
- Formulierung: Laiensprache mit leichtem Programmkontext, keine internen Begriffe ohne Nutzen.
- Umfang: so kurz wie möglich, nur dort länger, wo die Funktion ohne Erklärung nicht intuitiv ist.

Verbindliche Ausführbarkeitsregel für Toolbar-Aktionen:

- Tastenkürzel für Toolbar-Aktionen dürfen nur dann ausführen, wenn die zugehörige Aktion im aktuellen Kontext `enabled` ist.
- Button-Status und Shortcut-Ausführbarkeit müssen aus derselben Aktivierbarkeitsquelle abgeleitet sein; divergierende Nebenpfade sind ein Architektur-Verstoß.

Verbindliche Shortcut-Regel für Toolbar-Buttons:

- Jeder Toolbar-Button besitzt mindestens ein Strg-basiertes Shortcut (`Strg+...`) und darf nicht ohne Shortcut eingeführt werden.
- Die Zuordnung wird zentral in `kursplaner/resources/shortcuts/shortcut_guide.json` gepflegt (Single Source of Truth).
- Wenn zwei Toolbar-Aktionen kontextuell strikt disjunkt aber intentional gleich sind, dürfen sie dasselbe Strg-Shortcut teilen.

Verbindliche Zentralisierungsregel fuer UI-Steuerung:

- KeyBindings werden zentral in `bw_libs/ui_contract/keybinding.py` verwaltet.
- Pop-up-Verhaltensgrundsaetze werden zentral in `bw_libs/ui_contract/popup.py` verwaltet.
- HSM-Vertragslogik fuer Intent-Katalog, Escape-Prioritaet und Transition-Validierung liegt zentral in `bw_libs/ui_contract/hsm.py`.
- Neue Shortcut-/Popup-Interaktionen werden zuerst dort registriert und danach in konkrete Views verdrahtet.

Verbindliche Sprachregel für sichtbare UI-Texte:

- Sichtbare deutschsprachige GUI-/CLI-Texte verwenden echte Umlaute (`ä`, `ö`, `ü`, `ß`) und keine Ersatzschreibweisen (`ae`, `oe`, `ue`, `ss`), sofern technisch möglich.
- Gilt für Labels, Buttons, Menüs, Messageboxen, Tooltips und andere Nutzerausgaben.
- Technische Schlüssel, IDs, Dateiformate und Persistenzwerte bleiben davon unberührt.

Zusatzregel Datenquellen:

- Fachliche Katalogdaten (z. B. Kompetenzlisten) liegen in externen, versionierbaren Datenquellen (JSON), nicht als versteckte Python-Konstanten.
- Existenzpruefung und Laden solcher Dateien erfolgt ueber Ports/Infrastructure; die GUI startet keine direkte Dateisystem-Logik.
- Bei fehlenden/ungueltigen Ressourcen liefert der Application-Layer den Konflikt und der Adapter holt nur die Nutzerentscheidung (Ersatzpfad oder Fortfahren ohne Datei).

Zusatzregel GUI-Hilfsdaten:

- Reine GUI-Hilfsmetadaten ohne Fachentscheidung (z. B. Shortcut-Merkregeln fuer die Bedienhilfe) duerfen als versionierte JSON-Ressource unter `kursplaner/resources/` gepflegt werden.
- Solche Daten sind Single Source of Truth fuer Anzeige und GUI-Shortcut-Wiring, enthalten aber keine Domain-Regeln.

---

## 3) Abhängigkeitsregeln

Erlaubt:

- `Adapter -> UseCases -> Domain`
- `UseCases -> Ports`
- `Infrastructure -> Ports`

Verboten:

- `Adapter -> Domain` direkt
- `Adapter -> konkrete I/O-Services` direkt
- `UseCases -> konkrete I/O-Implementierungen` direkt
- `Domain -> I/O oder GUI`

---

## 4) Write-Flow-Standard

Jede schreibende Aktion folgt exakt diesem Ablauf:

1. Adapter validiert UI-Kontext.
2. Adapter holt notwendige Bestätigungen.
3. Adapter ruft einen Use Case auf.
4. Use Case führt fachliche Änderung aus.
5. Repositories speichern die betroffenen Daten.
6. Command-Delta wird für Undo/Redo erfasst.
7. Adapter aktualisiert die Anzeige.
8. Betroffene Repository-Caches/Indizes werden zentral invalidiert.

**Keine** verteilten ad-hoc Schreibpfade je Handler.

---

## 5) Undo/Redo-Standard

Undo/Redo ist **delta-basiert**.

Pflicht:

- Jede Aktion erzeugt ein `CommandEntry` mit expliziten `FileDelta`-Einträgen.
- Deltas enthalten immer `before` und `after`.
- Neu erzeugte Dateien müssen im `before` als `None` repräsentiert sein.
- Binärdateien (z. B. PDF-Exporte) gelten als generierbare Artefakte: sie werden nicht textbasiert delta-erfasst und sind damit nicht Teil der vollständigen Undo-Wiederherstellung.
- Beim Erwartungshorizont-Markdown gilt overwrite-sicheres Zusammenführen: bereits eingetragene Bewertungswerte (`AFB | Aufg | Pkte`) dürfen durch erneuten Export nicht verloren gehen.
- Entfallene, zuvor bewertete Ziele werden nicht still gelöscht, sondern als entfernt markiert (z. B. `~~...~~`) sichtbar gehalten.

Verboten:

- Vollständige Snapshot-Backups als Standardmechanismus.

---

## 6) Konfliktauflösungsstandard

Konflikte (z. B. Überschreiben/Verschieben/Löschen/Schatten) werden im Use Case entschieden.

Use Cases geben strukturierte Ergebnisse zurück, z. B.:

- `proceed`
- `error_message`
- `shadow_link`
- `delete_link`

Der Adapter führt nur die daraus resultierenden UI-Schritte aus.

---

## 7) No-Brute-Force-Regeln

Verboten:

- Vollscan pro Nutzeraktion
- Wiederholtes Laden derselben Stunde im selben Ablauf
- GUI-Klebercode zum Reparieren inkonsistenter Zustände

Pflicht:

- gezielte Queries
- betroffene Dateien explizit tracken
- frühzeitige Invariantenprüfung

Ausnahme nur als expliziter Maintenance-Entry:

- Vollscan/Rebuild ist ausschließlich über dedizierte Use Cases erlaubt (z. B. `RebuildPlanIndexUseCase`, `RebuildSubjectSourceIndexUseCase`).
- Diese Entries dürfen nicht implizit in normalen interaktiven Read-/Write-Pfaden ausgeführt werden.

---

## 7.1) Präzisierte, prüfbare Regeln zur Vermeidung von Brute-Force

Die folgenden Regeln konkretisieren Abschnitt 7 und sind automatisierbar/prüfbar in Code-Reviews:

- **Nur Infrastructure darf Dateisystem-Scans durchführen.** Adapter und Use Cases fordern gezielte Abfragen über Ports an; sie verwenden niemals `Path.iterdir()` oder `open()` direkt.
- **Repositories bieten gezielte, batch-fähige APIs.** Erforderlich sind mindestens:
	- `load_lessons_for_rows(table, row_indices)` (batch, darf intern cache verwenden)
	- `load_plan_tables(base_dir)` und `list_plan_markdown_files(base_dir)` (mit optionaler Cache-Invalidierung)
	- `load_calendar_data(calendar_dir, years)` (liefert bereits aggregierte Tages-Events)
- **Caches sind Repository-Verantwortung.** Caches müssen mtime-/size-Signaturen liefern oder invalidierbar sein; Use Cases und Adapter rufen `invalidate_cache()` über Ports, sie manipulieren keinen Cache direkt.
- **Index- oder Metadaten-Repositories sind Pflicht für häufige Queries.** Wenn ein Use Case regelmäßig viele Stunden-Metadaten benötigt (z. B. Übersicht/Reporting), muss ein `LessonIndexRepository` (Port) existieren, das nur metadata (z. B. `Stundenthema`, `mtime`) liefert, damit UI/UseCase keine Voll-Loads durchführen.
- **Keine wiederholten I/O-Zugriffe im selben Request.** Use Cases müssen Batch-Aufrufe an Repositories planen; Adapter dürfen nicht in Schleifen über Zeilen einzelne Repository-Aufrufe initiieren.
- **Dedizierte Rebuild-UseCases für Vollscan.** Vollständige Index-/Rebuild-Operationen sind ausdrücklich eigene Use Cases, mit klarer Kostenkennzeichnung und UI-Trigger (kein stiller Nebeneffekt).

Diese konkreten Regeln machen Abschnitt 7 prüfbar: Code, der `iterdir()` oder `open()` außerhalb von Infrastructure-Dateien verwendet, ist ein Architektur-Verstoß.

## 8) Pflichtbausteine je neue Schreibaktion

Jede neue Schreibaktion braucht:

1. eigenen oder klar erweiterten Use Case
2. Port-basierte Datenzugriffe
3. Delta-fähigen Undo/Redo-Eintrag
4. dokumentierte Konfliktstrategie (falls relevant)
5. UI-unabhängig testbaren Kernablauf

Wenn ein Baustein fehlt, ist die Änderung nicht architekturstabil.

---

## 9) Anti-Pattern (Stop-Signale)

Sofort stoppen und neu schneiden, wenn:

- „Nur kurz im GUI-Handler entschieden…“
- „Wir lesen einfach alles, dann finden wir es schon…“
- „Undo macht sicherheitshalber Voll-Snapshot…“
- „Dieses Modul kennt jetzt mehrere Schichten direkt…“
- „Wir brauchen einen kleinen Kleber-Hack…“

---

## 10) Definition of Done (Architektur)

Eine Änderung ist nur dann done, wenn:

- keine neue Fachentscheidung in GUI/CLI liegt,
- keine neue Brute-Force-Suche eingeführt wurde,
- ein klarer Use Case entstanden/erweitert wurde,
- Abhängigkeiten nach innen zeigen,
- Delta-basiertes Undo/Redo für die Änderung abgedeckt ist,
- der Kernablauf ohne GUI testbar ist.

---

## Kurzregel

> **Kern stabil, Adapter dünn, I/O gekapselt, Änderungen als Commands mit Deltas, kein Klebercode.**

---

## 11) Präzisierung: Was ist der Programmkern?

Der Programmkern besteht aus **allen fachlichen Entscheidungen**, die ohne GUI und ohne Dateisystem testbar sein müssen.

Verbindlich zum Kern gehören:

- Fachobjekte (`Plan`, `PlanRow`, `LessonRef`, `ConflictResolution`, `CommandEntry`, `FileDelta` als Fachstruktur)
- Fachregeln für Tabellenzustand und Stundenbezüge
- Konfliktentscheidungen (`move`, `shadow`, `delete`, `cancel`) als fachliche Strategie
- Fachliche Planoperationen (Ausfall/LZK/Split/Merge/Verschieben/Zuordnen)
- Undo/Redo-Logik als **fachlicher Command-Flow** (nicht als GUI-Helfer)

Nicht zum Kern gehören:

- Markdown/YAML/ICS parsing/rendering
- `Path`, `read/write/unlink/rename/move`
- GUI-Zustände (Selektion, Widgets, Button-Status)

---

## 12) Verbindliche Verantwortungsmatrix je Ebene

### Domain

- Enthält nur fachliche Typen, Invarianten, Entscheidungslogik.
- Kennt keine Repositories, keine Dateiformate, keine GUI-Events.

### Use Cases

- Enthalten den vollständigen Ablauf einer Nutzerabsicht.
- Definieren Transaktionsgrenze und erzeugen `CommandEntry`.
- Verwenden ausschließlich Ports (kein direkter Zugriff auf konkrete Dateien/Parser).
- Geben strukturierte Resultate zurück; keine Messagebox-Texte und keine UI-Dialoglogik.

### Ports

- Trennen fachliche Absicht von technischen Zugriffen.
- Jeder Use Case nutzt nur Ports; direkte Service-/Dateifunktionen sind verboten.

### Infrastructure

- Implementiert Ports für Dateisystem/Markdown/YAML/ICS.
- Kapselt alle konkreten I/O-Details.

### Adapter (GUI/CLI)

- Sammeln Input, holen Bestätigungen, rufen genau einen Use Case-Entry auf.
- Zeigen Resultate/Fehler an, aber treffen keine Fachentscheidungen.
- Kein eigener Write-Flow, kein eigener Undo/Redo-Stack als Geschäftslogik.

---

## 13) Pfad-Contract (verbindlich)

Persistierte Pfadwerte werden **immer relativ zum Workspace-Stamm `7thCloud`** gespeichert.

Verbindliche Regeln:

- Nur `core/config/path_store.py` normalisiert, speichert und auflöst Pfade.
- Persistenz (`config/paths.json`) enthält ausschließlich relative Werte (z. B. `7thVault/...`, `Code/...`).
- Alle Adapter/Use-Cases arbeiten bei Dateisystemzugriffen mit dem zentralen Resolver (`resolve_path_value(...)`).
- Direkte `Path(path_value).expanduser().resolve()`-Auflösung von gespeicherten Config-Werten außerhalb des zentralen Pfadmoduls ist verboten.

---

## 14) Export-Orchestrierungsstandard

Für Export-Aktionen (z. B. Sequenzplan/Erwartungshorizont, PDF/Markdown) gilt verbindlich:

- **Adapter** sammelt ausschließlich die Nutzerentscheidung (`Was`, `Wie`, `Als was`, Zielpfad) und zeigt Erfolg/Fehler an.
- **Use Cases** treffen die fachliche Auswahl (z. B. Sequenz über Oberthema, erlaubte Einheitstypen, Datenzuschnitt je Exportart).
- **Infrastructure-Renderer** sind format- und layoutspezifisch (PDF, Markdown) und enthalten keine Fachregeln.
- Ein gemeinsames GUI-Intent darf mehrere Exportvarianten auslösen; der Adapter bleibt dünn und delegiert die Fachvarianten an dedizierte Use Cases/Renderer.
- Bei Exporten mit Binärziel (PDF) ist Undo/Redo auf fachliche Quellen und textbasierte Artefakte begrenzt; PDFs werden bei Bedarf neu erzeugt statt aus Delta-Historie rekonstruiert.

Diese Regel sichert klare Modulgrenzen bei wachsender Exportfunktionalität.

DoD-Ergänzung:

- Eine Pfadänderung ist nur dann done, wenn kein Consumer mehr relative Konfigurationswerte über CWD auflöst.

---

## 13) Modulzuschnitt ohne Klebercode (Soll-Zustand)

Verbindlicher Zuschnitt mit eindeutiger Zuständigkeit (eine Hauptverantwortung je Modul):

1. **`core/domain/`**
	- nur fachliche Typen, Invarianten, Entscheidungslogik.
	- keine Dateipfade, keine Parser, keine GUI-Zustände.
2. **`core/usecases/`**
	- pro Nutzerabsicht genau ein Entry-Point (`execute(...)`).
	- orchestriert ausschließlich über Ports.
	- keine GUI-Dialoglogik und keine direkten Dateioperationen.
3. **`core/ports/`**
	- nur Verträge; keine Implementierungslogik.
	- Pflicht-Ports: `PlanRepository`, `LessonRepository`, `CalendarRepository`, `CommandRepository`, `SubjectSourceRepository`.
	- optional: `LessonFileRepository` für technische Dateioperationen.
4. **`infrastructure/repositories/`**
	- implementiert alle Ports.
	- kapselt vollständig `Path/open/read/write/unlink/rename/move/shutil`.
	- enthält auch technische Query-/Table-Implementierungen (z. B. `plan_table_file_repository.py`).
5. **`adapters/gui|cli/`**
	- nur Input sammeln, Bestätigungen holen, Use Case aufrufen, Ergebnis darstellen.
	- keine verteilte Persistenz-Orchestrierung.
6. **`adapters/bootstrap/` (Composition Root)**
	- einzige Stelle für Verdrahtung konkreter Repositories + Use Cases.
	- GUI/CLI-Module erhalten fertig konfigurierte Use Cases injiziert.
	- liefert fuer die GUI einen einheitlichen `AppDependencies`-Container (inkl. `shell_config`) aus `build_gui_dependencies()`.

Hinweis zum aktuellen Zuschnitt:

- `core/services/` ist kein I/O-Träger mehr; neue technische Logik wird direkt in `infrastructure/repositories/` implementiert.

Import-Regel (verbindlich):

- erlaubt: `adapter -> usecases`, `usecases -> ports|domain`, `infrastructure -> ports|domain`.
- verboten: `adapter -> infrastructure` direkt, `adapter -> core/services` direkt, `usecases -> core/services` mit I/O.

Schnitt-Regel:

- Wenn ein Modul sowohl Fachentscheidung als auch konkrete Datei-/Parser-Details enthält, ist der Schnitt falsch und muss neu geschnitten werden.

---

## 14) No-Brute-Force konkret (verbindlich)

Verboten im interaktiven Standardpfad:

- Vollscan aller Unterrichtsordner bei jeder UI-Aktualisierung.
- rekursiver Vollscan (`rglob`) bei jeder Dialogöffnung.
- wiederholtes Laden derselben Stunden-Datei innerhalb derselben Nutzeraktion.

Pflicht:

- Query-Ports mit Zielabfragen statt Dateibaum-Vollscan.
- Index/Caches für häufige Listen (Pläne, Baukasten-Quellen, ggf. Lesson-Metadaten).
- pro Use Case eine **Load-Phase** (betroffene Daten genau einmal laden), danach In-Memory-Entscheidungen.
- explizite Index-Invalidierung bei strukturändernden Aktionen (Anlegen/Löschen/Verschieben/Umbenennen).

Port-Anforderungen für Brute-Force-freie Abläufe:

- `PlanRepository` bietet indexbasierte Listen- und Metadatenabfragen sowie Batch-Queries (`load_plan_tables`).
- `LessonRepository` bietet gezielte Auflösung/Ladevorgänge für genau die betroffenen Zeilen/Dateien sowie Batch-Queries (`load_lessons_for_rows`).
- `SubjectSourceRepository` bietet Cache + explizite Invalidation/Rebuild-Operation.

Index-Regel:

- Index-Rebuild nur über expliziten Use Case (`rebuild_*`, `validate_*`).
- Adapter delegieren Invalidierung über Use Cases, implementieren aber keinen Vollscan.
- ein normaler `refresh` darf niemals implizit einen vollständigen Rebuild auslösen.

Fallback-Regel:

- Vollscan ist nur als bewusster Repair-Pfad erlaubt, nie als Standard-Reaktion auf Klickaktionen.

---

## 15) Write-Flow 2.1 (verbindlicher Ablauf)

Jede schreibende Aktion läuft über **eine** Use-Case-Transaktion:

1. Adapter sammelt Input + Bestätigung.
2. Adapter ruft genau **einen** Use-Case-Entry auf (`execute(command)`).
3. Use Case lädt alle betroffenen Daten über Ports (einmalig).
4. Use Case entscheidet Konflikte fachlich.
5. Use Case bildet Deltas (`before/after`) und erzeugt `CommandEntry`.
6. Use Case persistiert über Repositories.
7. Use Case liefert strukturiertes Ergebnis (`result`, `command_entry`, `invalidations`).
8. Adapter aktualisiert nur UI + triggert deklarierte Invalidierungen.

Verboten:

- verteilte `save_*`-Aufrufe in Adapter-Handlern.
- Undo/Redo-Orchestrierung im Adapter.
- Teil-Use-Case plus direkter Repository-/Dateizugriff im selben Handler.
- Mehrfach-Bestätigungs-/Mehrfach-Speicherketten im Adapter für eine einzelne Fachaktion.

Regel für zusammengesetzte Aktionen:

- Wenn eine Nutzeraktion mehrere Dateien betrifft (Plan + Stunden + Rename/Delete), bleibt sie trotzdem **ein** Use Case mit einem `CommandEntry`.

---

## 16) Dokumentationsstandard für Kernlogik

Pflicht für alle Kernmethoden (Domain + Use Cases):

- klare fachliche Absicht in einem Satz.
- Invarianten (`muss gelten vor/nachher`).
- Konfliktstrategie (falls vorhanden).
- welche Ports gelesen/geschrieben werden.
- welche Deltas entstehen.
- welche Index-Invalidierung ausgelöst wird (falls strukturändernd).

Mindestqualität:

- keine Platzhaltertexte wie „Unterstützt interne Verarbeitungsschritte …“.
- Methode muss anhand der Docstring ohne GUI-Kontext verständlich sein.

Pflicht zusätzlich je Write-Use-Case (Klassenebene):

- fachlicher Trigger (Nutzerabsicht).
- Transaktionsgrenze.
- Rückgabeformat inkl. `CommandEntry`.

Unzureichend und zu vermeiden:

- generische Platzhaltertexte ohne fachlichen Inhalt.
- rein technische Beschreibung ohne Fachwirkung.

---

## 17) Architektur-Checks (Definition von „Ja“)

Alle Antworten auf folgende Prüffragen müssen „Ja“ sein:

1. GUI macht nur Input/Output und ruft Use Cases auf.
2. Jede Schreibaktion läuft über genau einen Use Case mit einer Transaktion.
3. Jeder technische Zugriff läuft über Ports/Infrastructure.
4. Kein Use Case kennt konkrete I/O-Implementierung.
5. Kein Domain-Modul kennt I/O oder GUI.
6. Undo/Redo ist delta-basiert (`CommandEntry` mit `FileDelta before/after`).
	Binärartefakte (z. B. PDF) sind davon bewusst ausgenommen und werden als regenerierbar behandelt.
7. Kein Vollscan im normalen Nutzerklick-Pfad.
8. Jede Kernmethode ist fachlich klar dokumentiert.
9. Es gibt keinen verteilten Klebercode im Adapter (keine Mischkette aus Use Cases + direkten Saves).
10. Jedes Modul hat eine eindeutige Hauptverantwortung; bei zwei Verantwortungen wird geschnitten.

Prüfbare Stop-Kriterien (harte Verstöße):

- Adapter importiert konkrete Infrastructure-Repositories oder I/O-nahe Service-Module.
- Use Cases importieren Module mit konkreten Dateioperationen.
- Eine einzelne Nutzeraktion erzeugt mehrere unkoordinierte Save-Pfade außerhalb eines Use Cases.
- ein Adapter ruft Repository-Invalidierung direkt auf statt über expliziten Invalidierungs-UseCase.

Wenn eine Antwort „Nein“ ist oder ein Stop-Kriterium zutrifft, gilt die Änderung als **nicht done**.

---

## 18) Entscheidungslandkarte (verbindlich, konkret)

Zur Beantwortung von „Wer entscheidet was?“ gilt verbindlich:

### Domain entscheidet nur fachlich

- Invarianten der Planungstabelle (gültige Zeilenstruktur, Stunden-/Inhaltsregeln)
- fachliche Konfliktregeln als Strategieobjekte/Enums (`cancel|move|shadow|delete`)
- fachliche Transformationslogik (Split/Merge/Ausfall/LZK/Restore)

### Use Cases entscheiden Ablauf + Transaktion

- komplette Nutzerabsicht von Load bis Persist in **einem** `execute(...)`
- Konfliktauflösung anwenden (nicht nur weiterreichen)
- `CommandEntry` + `FileDelta before/after` erzeugen und zurückgeben
- deklarieren, welche Caches/Indizes invalidiert werden

### Adapter entscheidet nur Interaktion

- Input sammeln/validieren, Bestätigungen einholen, Use Case aufrufen
- strukturiertes Ergebnis darstellen
- **keine** fachlichen If/Else-Ketten über Konfliktlogik
- **keine** Persistenz-Orchestrierung, **kein** eigenes Dateistate-Capturing für Business-Undo

Prüfregel:

- Wenn ein Adapter mehr als „Input -> UseCase -> Output“ macht, ist der Schnitt falsch.

---

## 19) Use-Case-Schnittregel gegen „hübsch verpackte Abkürzungen"

Ein Use Case ist nur gültig, wenn er eine **vollständige Nutzerabsicht** kapselt.

Ungültig (Abkürzung):

- Utility-Methoden mit nur Teilwirkung ohne Transaktionsgrenze
- mehrere Use Cases + direkte Saves im Adapter für eine einzige Aktion
- Use Case, der konkrete Repositories selbst instanziiert

Gültig:

- ein Entry-Point pro Nutzeraktion
- alle benötigten Ports im Konstruktor injiziert
- Rückgabe ist strukturiert (`result`, `command_entry`, `invalidations`)

Pflichtregel:

- „Anlegen/Planen/Einfügen/Verschieben/Löschen/Umbenennen“ sind jeweils End-to-End-Use-Cases,
  keine zusammengesetzte Adapter-Choreografie.

---

## 20) No-Brute-Force 2.0 (operativ)

### Interaktiver Standardpfad

Verboten:

- Vollscan bei `refresh`, Tabellen-Laden, Dialog-Öffnen, Zell-Klick
- rekursives Dateisystem-Scannen zur Laufzeitentscheidung ohne Index

Pflicht:

- Plan-Übersicht aus Plan-Index (Metadaten + Next-Infos) statt vollständigem Tabellen-Reload
- Lesson-Infos über Batch-Queries (`load_lessons_for_rows`) statt Einzeldatei-Schleifen
- Subject-Quellen über persistenten Index/Manifest statt `rglob` im Interaktionspfad

### Expliziter Repair-/Rebuild-Pfad

- Vollscan nur in dediziertem Use Case (`rebuild_*`)
- UI darf Rebuild nur explizit triggern (nie implizit durch normalen Refresh)

---

## 20a) Governance fuer Einheiten-Schema/Naming

Fuer YAML-Schema und Dateinamensregeln von Einheitendateien gilt zusaetzlich verbindlich:

- Die fachliche Referenz liegt in `docs/EINHEITENDATEIEN_SCHEMA_GOVERNANCE.md`.
- Eine Aenderung ist nur done, wenn Rule-Code, Enforcement, Tests und Doku synchronisiert sind.
- Pull-Requests/Selbstreviews muessen die dortige Checkliste explizit abhaken.
- Rebuild-Ergebnis muss als strukturiertes Resultat zurückkommen

Unterrichts-YAML fuehrt `Teilziele` als Listenfeld direkt nach `Stundenziel`.
Die didaktischen Halbsatz-Rahmen fuer `Stundenziel` ("... insbesondere ...") und `Teilziele` ("... auch ...")
werden in der GUI als Hover-Hinweise angezeigt und nicht als persistierter Feldtext gespeichert.

### Technische Mindestbausteine

Pflichtports:

- `PlanIndexRepository` (listen, metadata, invalidate, rebuild)
- `LessonQueryRepository` (batch-read für betroffene Zeilen)
- `SubjectSourceIndexRepository` (resolve + invalidate + rebuild)

Hinweis:

- Dateibasierte Repositories bleiben erlaubt, aber nur hinter diesen Query-/Index-Ports.

---

## 21) Anti-Klebercode-Regeln (hart)

Klebercode liegt vor, wenn ein Modul gleichzeitig fachliche Entscheidung **und** technische Orchestrierung über mehrere Schichten macht.

Harte Verbote:

1. Adapter hält konkrete Repositories als Arbeitsobjekte für Fachabläufe.
2. Adapter baut Undo/Redo-Deltas über Dateicaptures für Business-Aktionen selbst.
3. Use Case importiert Infrastructure-Implementierungen direkt.
4. Core-Module (`core/storage`, `core/services`) enthalten konkrete Dateioperationen.

Zwingende Konsequenz bei Verstoß:

- Modul wird entlang Verantwortungen geschnitten, nicht „geflickt“.
- fehlende Portgrenze wird eingeführt, danach Use Case neu zuschneiden.

---

## 22) Verbindliche Zielantworten auf die Leitfragen

Die Architektur gilt nur dann als korrekt, wenn alle Antworten „Ja“ sind:

1. **Programmkern klar:** Fachregeln + fachliche Commands sind ohne GUI/Dateisystem testbar.
2. **Verantwortlichkeiten klar:** Adapter=I/O, UseCase=Ablauf, Domain=Regel, Infrastructure=Technik.
3. **GUI macht nur I/O:** keine fachliche Konfliktentscheidung, kein Save-/Undo-Glue.
4. **Speichermodule konsistent:** jede Dateioperation läuft ausschließlich über Ports/Repositories.
5. **Wissensminimierung:** jedes Modul kennt nur die eigene Ebene.
6. **Use Cases echt modularisiert:** pro Nutzerabsicht ein End-to-End-Use-Case.
7. **Kein Brute Force im Normalpfad:** nur index-/query-basiert; Vollscan nur via explizitem Rebuild.

---

## 23) Sanierungsreihenfolge ohne Architekturbruch

Die Umstellung erfolgt in dieser Reihenfolge:

1. **Use Cases entkoppeln:** direkte Infrastructure-Imports aus `core/usecases/` entfernen; nur Ports injizieren.
2. **Core-I/O bereinigen:** konkrete Dateifunktionen aus `core/storage` nach `infrastructure/repositories` verschieben.
3. **Adapter ausdünnen:** GUI hält nur Use Cases (keine Repositories für Fachpfade).
4. **Write-Use-Cases vervollständigen:** jeder Schreibpfad liefert `CommandEntry` und Invalidierungen.
5. **Index-Ports einziehen:** Plan-/Subject-/Lesson-Queries auf index-/batch-basierte Ports umstellen.
6. **Refresh entkoppeln:** Standard-Refresh rein query-basiert; Rebuild bleibt explizit.

Done-Kriterium pro Schritt:

- keine neuen Verstöße gegen Abschnitt 18–22,
- bestehende Verstöße werden reduziert, nicht nur verschoben.

---

## 24) Externe Änderungen außerhalb des Programms (verbindlich)

Da Markdown-/YAML-Dateien auch außerhalb der Anwendung geändert werden können, gilt:

1. Repository-Caches müssen **Staleness prüfen** (Datei-/Ordner-Signaturen wie `mtime`/`size` oder gleichwertig).
2. Ein Cache-Treffer ohne Frischeprüfung ist unzulässig.
3. Normale Lese-Use-Cases müssen externe Änderungen automatisch erkennen und aktuelle Daten liefern.
4. Explizite Rebuild-Use-Cases bleiben vorhanden, sind aber **Fallback/Repair**, nicht Normalbetrieb.
5. Bei erkannten externen Strukturänderungen (`create/delete/rename`) müssen betroffene Indizes gezielt invalidiert oder neu aufgebaut werden.

Verboten:

- blindes Vertrauen in langlebige In-Memory-Caches ohne Dateisystem-Validierung,
- implizite Annahme „nur das Programm schreibt Dateien".

Done-Kriterium:

- Änderungen an relevanten Dateien/Ordnern werden ohne Neustart sichtbar,
- ohne rekursiven Vollscan bei jedem UI-Klick.

---

## 25) REINE-GUI-Hard-Rule (bindend)

Für `adapters/gui/**` gilt strikt:

- erlaubt: Widget-Aufbau, Event-Binding, Selektion/Focus, Dialoganzeige, Formatierung für Anzeige.
- erlaubt: UseCase-Aufrufe + Anzeige strukturierter UseCase-Ergebnisse.
- verboten: fachliche If/Else-Entscheidungen über Konfliktstrategien (`move|shadow|delete|cancel`).
- verboten: fachliche Ableitungen aus Fachdaten (`row_index`, `default_hours`, `rename_target`, `target_path`), sofern diese nicht reine Anzeige sind.
- verboten: direkte Pfad-/Settings-Validierung oder Persistenzlogik außerhalb von UseCases.

### Verbotene Import-/Nutzungsmuster in GUI

In `adapters/gui/**` sind direkt verboten:

- `from ...core.config.path_store import load_path_values|save_path_values|validate_paths|get_managed_paths`
- direkte Nutzung konkreter Repositories oder Infrastructure-Module
- direkte Dateioperationen (`Path.write_text`, `open`, `unlink`, `rename`, `shutil.*`)

Zulässig ist ausschließlich:

- `adapter -> injected usecase -> ports/infrastructure`

### Prüfbarkeit (CI-/Review-Check)

Jede PR muss die folgenden Aussagen mit „0 Treffer“ erfüllen:

1. GUI enthält keine direkten Path-Store-Operationen (`load_path_values|save_path_values|validate_paths|get_managed_paths`).
2. GUI enthält keine direkten Datei-Operationen (`open\(|write_text\(|unlink\(|rename\(|shutil\.`).
3. GUI importiert keine Infrastructure-Repositories.

Wenn ein Check fehlschlägt, ist die Änderung **nicht done**.

### 25a) Verbindliche Verantwortungsmatrix (GUI-Schnitt)

Damit die Leitfragen aus Abschnitt 22 eindeutig mit "Ja" beantwortbar sind,
gilt fuer die GUI-Schicht folgende feste Matrix:

1. View (`screen_builder`, Widgets, Menues, Dialograhmen)
	- darf: Input erfassen, Output anzeigen, visuelle Zustandsdarstellung.
	- darf nicht: Fachentscheidungen, Persistenz, Konfliktregeln, Dateipfade ableiten.

2. UI-Orchestrierung (MainWindow-Adapter + dedizierte Controller)
	- darf: Intents entgegennehmen, UseCases aufrufen, View-State aktualisieren.
	- darf nicht: fachliche If/Else-Strategien oder Dateisystementscheidungen.

3. UseCases/Flows (`core/usecases`, `core/flows`)
	- darf: komplette fachliche Ablaufentscheidung inkl. Konfliktstrategie.
	- darf nicht: GUI-Widgets kennen oder auf Tk-Ereignisse reagieren.

4. Domain (`core/domain`)
	- darf: Regeln, Normalisierung, fachliche Ableitungen.
	- darf nicht: I/O, GUI, konkrete Repositories.

5. Infrastructure (`infrastructure/repositories`)
	- darf: konkrete Dateisystem-/JSON-/Indexzugriffe.
	- darf nicht: GUI- oder fachliche Entscheidungslogik.

Pruefregel:
- Wenn ein Modul zwei Ebenen der Matrix aktiv mischt, ist es Klebercode.

### 25b) Verbotene Wissensausweitung (Need-to-know)

Jedes Modul darf nur Daten kennen, die fuer seinen direkten Auftrag noetig sind.

Verboten:
- View kennt `row_index`, `target_path`, `decision`, `command_entry`.
- Controller kennt konkrete Repository-Typen oder Dateiablagen.
- UseCase kennt Widget-/Eventtypen.

Pflicht:
- Datenuebergabe nur ueber kleine Request/Result-Objekte (DTOs).
- Keine Weitergabe des gesamten App-Objekts als "Service-Bag".

### 25c) No-Brute-Force in der GUI (bindend)

Neben Abschnitt 20 gilt fuer Render-/Eventpfade zusaetzlich:

1. Vollstaendiges Grid-Rebuild ist nur zulaessig bei Strukturwechsel
	(z. B. Spaltenanzahl/Zeilenmodell geaendert).
2. Bei Zellwert-/Selektions-/Style-Aenderung muessen partielle Updates verwendet werden
	(`update_cell`, `update_header`, `update_row`).
3. Globale Event-Hooks (`bind_all`) duerfen keine linearen Vollsuchen ueber Widget-Sammlungen ausfuehren.
4. Fokus-/Edit-Zustand ist explizit als UI-State zu modellieren (kein implizites Durchsuchen).

Done-Kriterium:
- Interaktionspfade sind O(1) oder lokal begrenzt; kein O(n)-Scan ueber alle Grid-Zellen pro Klick.

### 25d) Ablaufstandard ohne Klebercode (verbindlich)

Jeder GUI-Ablauf folgt zwingend diesem Muster:

1. View-Ereignis erzeugt Intent (ohne Fachentscheidung).
2. Orchestrierung ruft genau einen fachlich passenden UseCase/Flow auf.
3. UseCase liefert Result mit fachlicher Entscheidung und UI-relevanten Auswirkungen.
4. Orchestrierung ueberfuehrt Result in View-State.
5. View rendert den geaenderten State (moeglichst partiell).

Verboten:
- View -> UseCase -> View -> UseCase Ping-Pong fuer einen einzelnen Nutzerintent.
- verstreute Seiteneffekte in mehreren Modulen ohne klaren Ablaufbesitz.

### 25e) KI-Umsetzungsprotokoll fuer Architektursanierungen (bindend)

Wenn Architekturarbeit mit KI umgesetzt wird, gilt:

1. Vor jedem Coding-Zyklus muss ein Mini-ADR vorliegen:
	- betroffenes Modul,
	- Regelbezug aus diesem Dokument,
	- geplanter Schnitt (vorher/nachher),
	- explizites Nicht-Ziel.

2. Ein Zyklus ist maximal ein Architekturschritt:
	- z. B. "Selection-Flow entkoppeln" oder "Grid-Patch-Update einfuehren".

3. Nach jedem Zyklus sind Pflichtartefakte:
	- Code,
	- Tests/Checks,
	- Doku-Delta in `ARCHITEKTUR_UMSETZUNGSPLAN.md`.

4. KI darf keine verdeckten Sammelrefactorings machen.
	- Jede zusaetzliche Strukturveraenderung muss vorab benannt werden.

5. Review-Checkliste pro KI-PR:
	- Hat sich Wissen pro Modul verringert?
	- Wurde Brute-Force reduziert statt verlagert?
	- Ist der Ablaufbesitz eindeutig?
	- Sind Importgrenzen weiterhin sauber?

Wenn eine Antwort "Nein" ist, wird der Zyklus nicht gemerged.

### 25f) GUI-Infrastruktur-Orientierung (dauerhaft)

Diese Orientierung dient dem Wiedereinstieg in die GUI-Architektur und beschreibt nur stabile Leitplanken.

Modulzuschnitt (wer ist wofuer zustaendig):

1. `adapters/gui/screen_builder.py`
	- baut Widgets, Menues, Bindings.
	- meldet UI-Ereignisse als Intents.
	- trifft keine fachlichen Ablaufentscheidungen.

2. `adapters/gui/grid_renderer.py`
	- rendert Grid-Struktur und Grid-Widgets.
	- meldet Grid-Interaktionen als Intents.
	- stellt Patch-Rendering bereit (`update_cell`, `update_header`, `update_row_style`, `update_column`, `refresh_grid_content`).
	- fuehrt Full-Rebuild nur bei Strukturwechseln aus (z. B. Zeilenmodell/Expand-Layout, Detailansicht-Neuaufbau, Spaltenbreite).
	- enthaelt keine fachliche Entscheidungslogik.

3. `adapters/gui/main_window.py`
	- ist zentraler UI-Orchestrator.
	- nimmt Intents an und delegiert an spezialisierte Controller/UseCases.
	- haelt den UI-Zustand zusammen, aber ohne fachliche Regeln auszuweiten.
	- enthaelt keine redundanten Alt-Forwarder fuer Aktionen, die bereits direkt ueber Intents delegiert werden.
	- initialisiert das Fensterlayout ueber die zentrale Shell-Konfiguration aus `AppDependencies` (`bw_libs/app_shell.py`).

4. `adapters/gui/action_controller.py`
	- kapselt allgemeine GUI-Aktionen (Toolbar-/Dialog-Aktionen ohne Fachumwandlung).
	- enthaelt keine Umwandlungslogik fuer Unterrichtstypen und keine Spalten-Reorder-Strategie.

5. `adapters/gui/lesson_conversion_controller.py`
	- kapselt Umwandlungen zwischen Unterricht/Ausfall/Hospitation/LZK.
	- delegiert fachliche Entscheidungen an UseCases/Flows.

6. `adapters/gui/column_reorder_controller.py`
	- kapselt Spaltenverschiebung inkl. Write-Tracking/Refresh-Pfad.
	- delegiert die Partnerwahl an `MoveSelectedColumnsUseCase.build_move_plan(...)`.
	- enthaelt keine fachliche Umwandlungslogik und keinen direkten Zeilentausch mehr.

10. `core/usecases/move_selected_columns_usecase.py`
	- ist die fachliche Orchestrierung fuer Einheiten-Verschiebung.
	- Invariante: nur `Inhalt` wird zwischen zwei Zeilen getauscht; `Datum` und `Stunden` bleiben zeilengebunden.
	- Ausfall-/Ferien-/Feiertags-Zeilen werden bei der Partnerwahl uebersprungen.
	- fuehrt nach dem Inhaltstausch fuer jede aufloesbare verlinkte Markdown-Datei eine Umbenennung aus (0, 1 oder 2 Dateien; Datumsteil wechselt zur Zielzeile, Titel bleibt bei der Einheit).
	- bei Namenskollisionen im Rename-Pfad wird atomar abgebrochen und in diesem Fall nichts persistiert.

7. `adapters/gui/ui_intents.py`
	- definiert den stabilen Intent-Vertrag zwischen View und Orchestrierung.

8. `adapters/gui/ui_state.py`
	- haelt den expliziten UI-Zustand (`selected_day_indices`, `is_detail_view`, `active_editor`, `visible_toolbar_actions`).
	- enthaelt nur UI-Zustand, keine fachlichen Regeln.

9. `adapters/gui/toolbar_viewmodel.py`
	- definiert die deklarative Toolbar-Struktur (feste Slot-Reihenfolge, Separator-Slots, Action-Definitionen).
	- kapselt die regelbasierte Ableitung von Sichtbarkeit/Aktivierung (`build_toolbar_view_model`).
	- enthaelt keine Tk-Widget-Manipulation und keine Fachentscheidungen.
	- bei schmalen Fensterbreiten werden Toolbar-Slots responsiv auf 2/3+ Reihen umgebrochen (normal: 1 Reihe), mit semantischer Gruppierung statt zufaelliger Reihenfolge.

Zentraler Eventfluss:

- `View-Event -> UiIntent -> MainWindow-Orchestrierung -> Controller/UseCase -> UI-Update`
- Editor-Fokusfluss: `FocusIn -> GRID_EDITOR_FOCUS_IN -> ui_state.active_editor`.
- Commit bei globalem Klick: `GLOBAL_CLICK_COMMIT_CELL` nutzt `ui_state.active_editor` direkt (kein Widget-Scan ueber alle Zellen).
- Renderfluss nach Interaktionen: `Controller-Write -> day_columns refresh -> grid_renderer.patch_update` (kein Full-Rebuild im Normalpfad).

Einstiegspunkte fuer typische Aenderungen:

1. Neuer Button/Shortcut/Menu-Aktion:
	- Intent in `ui_intents.py` ergaenzen,
	- Toolbar-Action und Slot in `toolbar_viewmodel.py` ergaenzen,
	- Event im `screen_builder.py` (oder `grid_renderer.py`) auf Intent binden,
	- Intent-Handling in `main_window.py` orchestrieren.

2. Neue Grid-Interaktion:
	- Binding im `grid_renderer.py`,
	- Intent-Verarbeitung in `main_window.py`,
	- fachliche Wirkung im passenden Controller/UseCase.

3. Fachliche Regelanpassung:
	- nicht im View/Renderer,
	- sondern in UseCase/Domain und dann nur orchestral anbinden.

Harte No-Gos fuer GUI-Infrastruktur:

- keine Fachentscheidungen in `screen_builder.py`/`grid_renderer.py`.
- keine direkten Datei- oder Infrastructure-Zugriffe in GUI-Adaptern.
- kein Bypass am Intent-Vertrag fuer neue Interaktionspfade.
- keine dynamische Pack-Reihenfolge-Rekonstruktion (`before`/Order-Hacks) im Toolbar-Normalpfad.
- kein Mischen von Tk-Geometry-Managern im selben Toolbar-Container (`toolbar_frame`): Toolbar-Slots sind strikt `grid`-basiert.
- kein Sammelmodul fuer fachfremde GUI-Restlogik (kein dauerhafter "legacy"-Controller-Eimer).

Verbindliche lokale Gates bei GUI-Aenderungen:

- `pre-commit` ist fuer lokale GUI-Entwicklung verpflichtend (`ruff`, `ruff-format`, `mypy`; `pytest` als `pre-push`).

---

## 26) Doku-Pflicht bei Architekturänderungen (bindend)

Für jede Architektur-relevante Änderung gilt:

1. Codeänderung und Dokuänderung sind ein gemeinsames Deliverable.
2. Bei Änderungen am Zuschnitt/Flow/Schichtverhalten muss im selben Arbeitszyklus mindestens aktualisiert werden:
	- `docs/DEVELOPMENT_LOG.md` (durchgeführte Änderung, Datum, Scope),
	- `docs/ARCHITEKTUR_KERN.md` (nur wenn Regeln/Leitplanken geändert oder präzisiert wurden).
3. Ein PR/Arbeitsstand ohne passenden Doku-Stand gilt architektonisch als nicht done.
4. Doku-Änderungen müssen den Zustand prüfbar machen (Datum, betroffener Baustein, kurzer Status).
5. **Immer-Update-Regel:** Änderungen am Architekturzuschnitt werden nie gesammelt „später" dokumentiert, sondern sofort im gleichen Arbeitszyklus.

Dokumentrollen (verbindlich):

- `docs/ARCHITEKTUR_KERN.md`: stabiler Ist-Zustand und dauerhafte Architekturregeln.
- `docs/ARCHITEKTUR_UMSETZUNGSPLAN.md`: nur offene Arbeit, keine Historie.
- `docs/DEVELOPMENT_LOG.md`: Verlauf und abgeschlossene Feature-/Architektur-Aenderungen.

## 27) Standard für Format-/Serialisierungslogik (bindend)

Wiederverwendete Formatierungen mit Fachbedeutung (z. B. Wiki-Link-Syntax `[[...]]`) werden nicht ad hoc in mehreren UseCases/Adaptern als String-Verkettung umgesetzt.

Pflicht:

1. Ein zentraler Domain-Baustein kapselt die Erzeugung/Normalisierung (z. B. `build_*`, `strip_*`).
2. Schreibpfade in UseCases/Infrastructure verwenden diesen Baustein, statt eigene f-Strings für dasselbe Format zu bauen.
3. Für den zentralen Baustein existieren gezielte Regressionstests für fehleranfällige Randfälle (z. B. unbalancierte Klammern, Alias-Varianten).

Verboten:

- Gleichartige Format-Logik in mehreren Dateien duplizieren.
- Format-Parsing/-Reparatur als GUI-Helfer zu implementieren, wenn es fachlich wiederverwendbar ist.

