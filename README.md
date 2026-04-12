# Kurs-Manager (Code/kursplaner)

## Überblick

Der Kurs-Manager hat zwei Hauptbereiche:

1. **Manager-Hauptfenster**: Übersicht aller Kurspläne
2. **Neu-Fenster**: Neuen Kurs direkt anlegen

Zusätzlich gibt es den **Terminplaner-CLI-Einstiegspunkt**.

---

## Begriffe

- **Kurs**: ein Fach in einer Lerngruppe für ein Halbjahr
- **Einheit**: eine Spalte im Kursplan

Hinweis zur Kompatibilität: interne YAML-/Tabellenschlüssel wie `Lerngruppe`, `Fach`, `Stunden`, `Stundenthema` bleiben aktuell technisch unverändert.

---

## Neu an der Struktur

### Architektur (Code)

Die Python-Pakete sind jetzt tiefer verschachtelt für mehr Übersicht:

- `kursplaner/adapters/gui` (GUI)
- `kursplaner/adapters/cli` (CLI)
- `kursplaner/core/services` (Anwendungslogik)
- `kursplaner/core/domain` (Fachlogik)
- `kursplaner/core/storage` (Dateioperationen)
- `kursplaner/core/config` (Defaults + persistente Pfad-Settings)

### Plan-Datei (pro Kurs)

Neu erstellte Plan-Dateien erhalten am Anfang YAML-Metadaten:

- `Lerngruppe`
- `Fach`
- `Stufe`

### Plan-Tabelle in der Kursdatei

Die Planungstabelle hat nur noch diese 3 Spalten:

- `Datum`
- `Stunden` (Dauer der Einheit in Stunden)
- `Inhalt`

`Inhalt` ist entweder:

- ein Ausfallgrund (kein Link),
- ein Link auf eine Einheit im Ordner `Einheiten` (z. B. `[[Einheiten/Inf8 Thema]]`),
- oder leer.

### Einheiten-Dateien (Ordner `Einheiten`)

Die verlinkten Einheiten-Dateien tragen die inhaltlichen Daten in YAML, z. B.:

- `Oberthema`
- `Stundenthema`
- `Stundenziel`
- `Kompetenzen` (Liste)
- `Material` (Liste)

---

## Manager-Hauptfenster

### Funktionsübersicht (grundsätzlich verfügbar)

Die Aktionen sind immer über das Menü erreichbar; in der Toolbar werden sie je nach Auswahlkontext ein-/ausgeblendet.

- **Datei**
	- Neu
	- Lesson-Index neu aufbauen
	- Einstellungen
- **Bearbeiten**
	- Undo
	- Redo
- **Aktion**
	- Einheit kopieren
	- Einheit einfügen
	- Markdown finden
	- Einheit leeren
	- Einheit aufsplitten
	- Einheiten zusammenführen
	- Ausfall zurücknehmen
- **Toolbar-Kontextaktionen**
	- Als Unterricht
	- Als Ausfall
	- Als Hospitation
	- Als LZK
	- ← / → (Spalten verschieben)
- **Shortcuts**
	- `Strg+N`, `Strg+C`, `Strg+V`, `Strg+Z`, `Strg+Y`

### Start-Prüfung für Pfade

Beim Programmstart werden alle konfigurierten Pfade geprüft (Unterrichtsordner, Kalenderordner).

Wenn ein Pfad fehlt/ungültig ist:

- wird der Benutzer informiert,
- danach wird direkt ein System-Ordnerdialog geöffnet,
- erst mit gültigen Pfaden startet das Hauptfenster.

Die Pfade werden persistent gespeichert.

Speicherort der Konfiguration:

- `Code/kursplaner/config/paths.json`

Es wird **nichts** mehr in AppData oder anderen systemweiten Nutzerverzeichnissen gespeichert.

### Strikte YAML-Prüfung

Der Manager prüft beim Laden **alle in den Planungstabellen verlinkten Stunden-Markdowns** sofort auf gültige YAML-Daten.

- fehlendes YAML-Frontmatter wird sofort als Fehler gemeldet,
- fehlende Pflichtfelder werden sofort als Fehler gemeldet,
- es wird nichts „stillschweigend“ mit leeren Defaults weitergeführt.

Wenn bei einer Einheit das YAML-Frontmatter fehlt, fragt die GUI beim Laden,
ob das YAML ergänzt werden soll. Dabei kann die Art gewählt werden:

- Unterricht
- LZK
- Hospitation

### Linke Übersichtstabelle

Zeigt pro Unterricht:

- `Unterricht`
- `Nächstes Thema`
- `Reststunden`
- `Nächste LZK`

`LZK` wird aus dem Inhalt (insb. Stundenthema/Kommentar mit „LZK") erkannt.

Wenn beim initialen Laden/Aktualisieren einzelne Unterrichte nicht vollständig
berechnet werden können, bleiben sie trotzdem in der Übersicht sichtbar und
werden mit `⚠` markiert (statt aus der Liste zu verschwinden).

### Rechte Detailtabelle (dynamisch)

Die rechte Tabelle basiert auf der Plan-Tabelle plus den verlinkten Stunden-YAML-Daten und zeigt:

- Datum / Stunden / Inhalt
- Oberthema / Stundenthema / Stundenziel / Kompetenzen / Material

Zusätzlich gibt es fachbezogene Anzeigemodi mit automatischer Umschaltung je Spaltentyp:

- **Unterricht**: Stundenthema, Oberthema, Stundenziel, Kompetenzen, Material
- **LZK**: zu schreibende LZK (Stundenthema), Erwartungshorizont, Inhaltsübersicht
- **Ausfall**: Vertretungsmaterial
- **Hospitation**: Beobachtungsschwerpunkte, Ressourcen, Baustellen

Die Moduswahl ist manuell per Buttons möglich; mit **Auto je Spalte** wird bei Auswahl einer Spalte automatisch auf deren Art umgeschaltet.

#### Bearbeitung

- Doppelklick auf Zelle: editieren
- Speichern beim Verlassen der Zelle (nur wenn eine gültige verlinkte Stunden-Markdown vorhanden ist)
- Bei Ausfall-Zeilen (Inhalt vorhanden, aber kein Link) wird die Zeile ausgegraut
- Spalten ohne bekannte Stunden-Markdown sind schreibgeschützt
- Für fehlende/verlorene Links steht die Aktion **Markdown finden** zur Verfügung (Datei wählen, zurück an passenden Ort verschieben, Link aktualisieren)

Beim Erstellen einer neuen Stunde über **Stunde erstellen** öffnet sich ein Bau-Dialog:

- Stundenthema
- Oberthema (aus vorherigen Stunden vorbefüllt, aber editierbar)
- Inhalte (Mehrfachauswahl aus `30 Baukasten/34 Fachinhalte/<Fach>`)
- Methodik (Mehrfachauswahl aus `30 Baukasten/33 Fachdidaktik/<Fach>`)

Ausgewählte Inhalte/Methodiken werden als Wiki-Links unter `## Inhalte` und `## Methodik` in die neue Stunden-Datei geschrieben.

Dateiname für neue Stunde: **Lerngruppe + `mm-dd` + Stundenthema** (z. B. `grün-6 03-14 Rechnerlogik`).

Pflichtfeld im Stunden-YAML: `Stundentyp` mit einem der Werte `Unterricht`, `LZK`, `Ausfall`, `Hospitation`.

### Governance fuer Schema/Naming

Verbindliche Dokumentation und Aenderungs-Checkliste:

- `docs/EINHEITENDATEIEN_SCHEMA_GOVERNANCE.md`

Single Source of Truth im Code:

- YAML pro `Stundentyp`: `kursplaner/core/domain/lesson_yaml_policy.py`
- Dateiname (`Lerngruppe mm-dd Titel`): `kursplaner/core/domain/lesson_naming.py`
- Mindestvalidierung: `kursplaner/core/domain/yaml_registry.py`

Empfohlener Pre-Commit-Check:

- `powershell -ExecutionPolicy Bypass -File .\\tools\\ci\\check_einheiten_schema_consistency.ps1`

### Maussteuerung in der Detailtabelle

- Mausrad: vertikal scrollen
- `Shift` + Mausrad: horizontal scrollen
- `Strg` + Mausrad: Zoom

### Themes

Unter **Ansicht → Theme** sind die gleichen Theme-Optionen verfügbar wie in Blattwerk/NamenFit.

### Einstellungen

Unter **Datei → Einstellungen…** können die zentral verwalteten Pfade jederzeit geändert werden.

- Unterrichtsordner
- Kalenderordner

Zusätzlich ist dort die **UB-Vergangenheitsregel** konfigurierbar:

- Uhrzeit im Format `HH:MM` (24h), ab der UBs am aktuellen Datum als Vergangenheit zählen
- Standard ist `15:00`
- Die Einstellung wirkt sowohl auf die UB-Achievements als auch auf die "letzten UB-Punkte" im Dialog **Einheit planen**

Persistenz:

- `config/ui_preferences.json` unter dem Schlüssel `ub_past_cutoff_time`

---

## Neu-Fenster

Eingaben:

- Fach
- Lerngruppe
- Stufe (1–13)
- Halbjahr **oder** Startdatum
- Unterrichtstage Mo–Fr inkl. Stunden (1–4)

Beim Anlegen:

- Unterrichtsordner wird angelegt
- Plan-Datei wird neu erstellt
- YAML-Metadaten werden vorangestellt
- Terminplan wird angehängt
- Feiertage/Ferien setzen `Stunden` automatisch auf `0`

---

## UB-Ansicht

Die UB-Ansicht zeigt Fortschrittskacheln mit Ringdarstellung je Ziel.

- Jede Kachel zeigt den numerischen Stand direkt im Symbol (`current/target`, z. B. `1/4`)
- Nicht erfüllte Kacheln verwenden ein abgedunkeltes Symbol, um den offenen Zustand klarer erkennbar zu machen
- Die Datumsfilterung nutzt die konfigurierbare UB-Vergangenheitsregel aus den Einstellungen

---

## Start

### GUI

- `start-kursplaner.bat`
- oder `py -3 app.py`

### Terminplaner CLI

- `start-terminplaner.bat`
- oder `py -3 planer_cli.py`

---

## Lokale Quality-Gates (pre-commit)

Einmalig einrichten:

```powershell
py -3 -m pip install -r requirements-dev.txt
py -3 -m pre_commit install
py -3 -m pre_commit install -t pre-push
```

Manueller Lauf:

```powershell
py -3 -m pre_commit run --all-files
```

