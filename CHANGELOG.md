# Changelog

All notable user-facing changes to this project will be documented in this file.

The format is based on Keep a Changelog.

## [Unreleased]

### Changed
- Strg+Enter im Spaltenmodus ist jetzt typabhaengig: Unterricht, LZK, Ausfall und Hospitation oeffnen jeweils einen passenden Bestaetigungsdialog.
- Unterricht per Strg+Enter oeffnet denselben Planungsdialog wie beim Neuanlegen, nun mit vorausgefuellten Werten aus der bestehenden Spalte/Stunden-Datei.
- Ausfall- und Hospitationsdialoge bleiben die bestehenden Dialoge und oeffnen jetzt mit Vorbelegung aus vorhandenen Spalten-/YAML-Werten.
- Neues separates LZK-MVP-Fenster fuer Strg+Enter eingefuehrt (zunaechst schlank, mit optionalem Titel-Override).
- Esc in Popups ist jetzt fokusabhaengig: bei Textfeldeingabe wird zuerst der Popup-Fokus hergestellt; erst danach schliesst Esc ohne Speichern.
- Das Einstellungsfenster steuert jetzt, ob im Dialog `Einheit planen` die Felder `Kompetenzen` und `Stundenziel` angezeigt werden.
- `Stundenziel` ist im Dialog `Einheit planen` nicht mehr verpflichtend, auch wenn KC-Vorschlaege verfuegbar sind.
- LZK-Erkennung fuer Uebersicht/Detail und Tages-Logs wurde von Text-Treffern (`lzk` im Inhalt/Titel) auf YAML-Metadaten (`Stundentyp`) umgestellt.
- UB-Popup-Fokus wurde stabilisiert: nur das aktive Popup darf den Modal-Fokus erzwingen.
- Kursuebersicht erweitert um die Spalte `Naechster UB`: zeigt den naechsten geplanten Unterrichtsbesuch je Kurs im Kurzformat `D.M. Initialen+` (bleibt leer, wenn kein zukuenftiger UB vorhanden ist).
- Einheitenansicht verbessert: komplette UB-Einheiten werden jetzt mit einer theme-abhaengigen Umrandung hervorgehoben.
- UB-Button-Verhalten angepasst: erneuter Klick auf eine bereits als UB markierte Einheit oeffnet den UB-Dialog zur Bearbeitung (statt sofortigem Entfernen); UB-Loeschen ist als explizite Dialogaktion verfuegbar.
- UB-Ansicht modernisiert: drei Tabs (`Achievements`, `UB-Plan`, `Entwicklungsimpulse`) mit einfachem Wechsel per Mausklick und Pfeiltasten.

### Added
- Neuer Tab `UB-Plan` mit getrennten Listen fuer kommende und absolvierte UBs inklusive Spalten `Datum`, `Faecher`, `+` (Langentwurf), `Kurs`.

## [0.1.2] - 2026-04-22

### Changed
- Neue Hospitationen erzeugen jetzt den Dateititel im Format `Lerngruppe MM-DD Hospitation` statt mit doppelter Lerngruppen-Nennung im Titel.
- Beim Erstellen von Hospitationen wird in der Kurstabelle nur noch der Markdown-Link gespeichert, ohne zusaetzlichen `HO ...`-Praefixtext.
- Neue LZK-Dateititel nutzen das Fachkuerzel im Format `Lerngruppe MM-DD LZK Fachkuerzel HJ NR`.
- Der Hospitationsmodus zeigt `Stundenthema` aus der YAML-Datei in der Detailansicht analog zu Unterrichtseinheiten.
- Documentation governance now separates stable architecture reference from development history.
- Repo Path Guardrails wurden repariert; der CI-Check fuer persistierte JSON-Pfade laeuft wieder stabil mit einem vorhandenen Pruefskript.
- Scrollbars wurden visuell modernisiert und folgen jetzt konsistent den aktiven Theme-Farben (inklusive horizontaler und vertikaler Varianten).

### Added
- Public communication workflow via changelog, PR template, and release-ready structure.
