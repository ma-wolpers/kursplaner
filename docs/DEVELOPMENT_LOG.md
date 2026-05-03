# Development Log (kursplaner)

Dieses Dokument trackt technische Aenderungen fuer Feature- und Architekturarbeit.

Regel:
- Keine Feature- oder Architekturaenderung ohne Update in diesem Log.
- Bugfix-Only-Changes koennen ohne Eintrag erfolgen.

## [Unreleased]

### Changed
- Zentrale UI-Governance gestartet: `kursplaner/adapters/gui/keybinding_registry.py` und `kursplaner/adapters/gui/popup_policy.py` als gemeinsame API-Basis fuer Shortcut- und Popup-Steuerung eingefuehrt.
- Guardrails erweitert: AGENTS/Copilot/PR-Template verlangen zentrale Shortcut-/Popup-Registrierung sowie Feature-Commit-Disziplin bei manuellem Push.
- `tools/ci/check_ai_guardrails.py` prueft die Existenz der neuen Zentralmodule und meldet Commit-/Push-Prozessdrift als non-blocking Warnung.
- Paste-Konfliktfall `delete` bereinigt jetzt auch UB-Artefakte der ersetzten Zieleinheit: verknuepfte UB-Datei wird entfernt und UB-Uebersicht im selben Writeflow aktualisiert; alle betroffenen Pfade sind fuer Undo/Redo im Ergebnismodell markiert.
- Guardrail-Absicherung durch dedizierte Tests erweitert: Negativfall (direkter `apply_value`-Deletepfad) und Positivfall (getrackter Writeflow) sind als Unit-Tests fuer die AST-Guardrail-Regel abgedeckt.
- Spaltenmodus `Strg+X` ist jetzt als echter Einheit-Cut verdrahtet: statt Zelltext-Cut wird eine verlinkte Einheit zum Verschieben vorgemerkt.
- Cut+Paste fuer Einheiten mit UB als Move-Flow umgesetzt: beim Einfuegen wird die Ziel-Einheit geschrieben, danach die Quell-Einheit samt alter UB-Datei aufgeraeumt; Ergebnis ist eine verschobene Einheit mit UB-Update statt Duplikat.
- Einheits-Loeschen fuer Unterricht mit UB auf transaktionalen Writeflow umgestellt: Einheit-Datei wird beim Loeschen entfernt, optional verknuepfte UB-Datei mitgeloescht, UB-Uebersicht im selben Zyklus synchronisiert.
- Delete-Shortcut im Grid (`Inhalt`) routed jetzt auf denselben Action-Writeflow wie Toolbar-Loeschen statt direktem Zell-Write, damit Undo/Redo alle beteiligten Dateien konsistent rueckspielen kann.
- Paste-Flow erweitert um Pflichtauswahl bei Quellen mit UB-Verknuepfung: vor Einfuegen muss entschieden werden `UB mitkopieren` / `ohne UB` / `abbrechen`; bei Mitkopieren wird eine neue UB-Datei fuer das Ziel erzeugt und die Uebersicht aktualisiert.
- AI-Guardrails um AST-Pruefungen fuer Undo-kritische Writeflows erweitert (Delete/Paste muessen getrackt laufen; UB-Kopierdialog im Paste-Flow verpflichtend).
- Strg+Enter fuer Spaltenmodus ausgebaut: im Spaltenauswahlmodus oeffnet jetzt ein typabhaengiger Bestaetigungsdialog (Unterricht, LZK, Ausfall, Hospitation) statt des reinen Edit-Commits.
- Unterricht-Dialog bei Strg+Enter nutzt denselben Builder wie bei neuer Planung, aber mit Voll-Prefill aus bestehender Stunde (YAML + Inhalte/Methodik-Abschnitte aus Markdown), sodass bestehende Spaltenwerte direkt bearbeitbar sind.
- Ausfall/Hospitation auf bestehendem Dialogmuster belassen und um Vorbelegung erweitert (Ausfallgrund aus Markertext, Beobachtungsschwerpunkt aus YAML).
- Neues separates LZK-MVP-Fenster fuer Strg+Enter hinzugefuegt; optionaler Titel-Override, anschliessend bestehender LZK-Write-Flow.
- Escape-Verhalten in Popup-Basisklasse verfeinert: Esc schliesst nur sofort bei Popup-Fokus; bei Fokus in editierbaren Eingabefeldern wird zunaechst auf Popup-Ebene fokussiert.
- Popup-Modalfokus gehaertet: `_activate_modal_focus` bricht jetzt ab, wenn das Fenster nicht das aktive Top-Popup ist, um Fokus-Rueckspruenge in verschachtelten Popup-Flows zu vermeiden.
- UI-Persistenz erweitert: neue Preferences `lesson_builder_fields.show_kompetenzen` und `lesson_builder_fields.show_stundenziel` steuern die Sichtbarkeit optionaler Builder-Felder.
- Settings-Dialog um Feldsichtbarkeit fuer `Einheit planen` erweitert; Speicherung erfolgt zentral ueber `ui_preferences_store`.
- Lesson-Builder flexibilisiert: `Kompetenzen`/`Stundenziel` koennen ausgeblendet werden; `Stundenziel` ist nicht mehr als Pflichtauswahl erzwungen.
- LZK-Erkennung im Kern entheuristisiert: Detail-Projection, Daily-Log, Plan-Overview und LZK-Nummerierung nutzen jetzt YAML-`Stundentyp` statt String-Treffer auf Titel/Inhalt.
- Lesson-Index-Metadaten fuer Overview erweitert um `Stundentyp`, damit indexbasierte Abfragen ohne Topic-Heuristik auskommen.
- UB-Fokus in der GUI ausgebaut: Kursuebersicht zeigt jetzt `Naechster UB` im Format `D.M. Initialen+` (leer ohne zukuenftigen UB), Einheiten mit UB erhalten eine theme-abhaengige Vollspalten-Umrandung.
- UB-Interaktion umgestellt: erneuter Klick auf UB oeffnet den UB-Dialog zur Bearbeitung (mit Vorbelegung) statt sofortigem Entfernen; Loeschen erfolgt jetzt explizit ueber eigene Dialogaktion.
- UB-Ansicht als Tab-UI neu strukturiert: `Achievements`, `UB-Plan` (kommende/absolvierte Listen mit Spalten `Datum`, `Faecher`, `+`, `Kurs`) und `Entwicklungsimpulse`; Tabwechsel per Maus und Pfeiltasten.
- HO/LZK-Erzeugung vereinheitlicht: neue Hospitationen speichern in der Kurstabelle nur noch den Markdown-Link, HO-Dateithemen werden ohne doppelte Lerngruppen-Nennung gesetzt, und LZK-Titel werden mit Fachkuerzel statt Vollfach erzeugt.
- Hospitations-Detailmodus erweitert: `Stundenthema` ist jetzt im Hospitationsmodus sichtbar, analog zur Themenanzeige bei Unterrichtseinheiten.
- Dokumentrollen formal getrennt: Architektur-Referenz (`docs/ARCHITEKTUR_KERN.md`) vs offene Arbeit (`docs/ARCHITEKTUR_UMSETZUNGSPLAN.md`) vs Verlauf (`docs/DEVELOPMENT_LOG.md`).
- Guardrail-Regeln erweitert um verpflichtendes Development-Log-Update fuer relevante Aenderungen.
- Repo-Path-Guardrails repariert: CI verwendet jetzt wieder ein vorhandenes Pruefskript (`tools/repo_ci/check_no_absolute_paths.py`) fuer absolute JSON-Pfade.
- AI-Guardrails erweitert, damit Workflow-/Script-Drift fuer Repo-Path-Checks frueh erkannt und lokal blockiert wird.
- ttk-Themekonfiguration erweitert: `TScrollbar`, `Horizontal.TScrollbar` und `Vertical.TScrollbar` werden zentral modern gestylt, damit Scrollbereiche in allen GUI-Teilen konsistent zur Theme-Sprache passen.

### Added
- `CHANGELOG.md` fuer oeffentliche, nutzerorientierte Kommunikation.
- `.github/pull_request_template.md` mit Pflichtfeldern fuer Doku- und Release-Kommunikation.

## [History]

### 2026-04-12
- Development-Log-Governance eingefuehrt und in Guardrails verankert.
