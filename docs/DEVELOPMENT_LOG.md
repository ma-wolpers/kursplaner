# Development Log (kursplaner)

Dieses Dokument trackt technische Aenderungen fuer Feature- und Architekturarbeit.

Regel:
- Keine Feature- oder Architekturaenderung ohne Update in diesem Log.
- Bugfix-Only-Changes koennen ohne Eintrag erfolgen.

## [Unreleased]

### Changed
- Tk-Runtime-Pilotmigration erweitert: `kursplaner/adapters/gui/window_identity.py` nutzt jetzt `bw_gui.runtime.ui`-Typen/Exceptions statt direktem `tkinter`-Import.
- Tk-Runtime-Pilotmigration erweitert: `kursplaner/adapters/gui/path_bootstrap.py` nutzt jetzt `bw_gui.runtime.ui` fuer den Root-Window-Start statt direktem `tkinter`-Import.
- Tk/ttk-Runtime-Pilotmigration erweitert: `kursplaner/adapters/gui/column_visibility_dialog.py` nutzt jetzt zentrale Runtime-Aliases aus `bw_gui.runtime` (`ui`/`widgets`) statt direkter `tkinter`-/`ttk`-Imports.
- Tk/ttk-Runtime-Pilotmigration erweitert: `kursplaner/adapters/gui/wrapped_text_field.py` nutzt jetzt zentrale Runtime-Aliases aus `bw_gui.runtime` (`ui`/`widgets`) statt direkter `tkinter`-/`ttk`-Imports.
- Tk/ttk-Runtime-Pilotmigration erweitert: `kursplaner/adapters/gui/export_selection_dialog.py` und `kursplaner/adapters/gui/ub_mark_dialog.py` nutzen jetzt zentrale Runtime-Aliases aus `bw_gui.runtime` (`ui`/`widgets`) statt direkter `tkinter`-/`ttk`-Imports.
- Tk/ttk-Runtime-Pilotmigration erweitert: `kursplaner/adapters/gui/lzk_column_dialog.py` und `kursplaner/adapters/gui/shortcut_overview_dialog.py` nutzen jetzt zentrale Runtime-Aliases aus `bw_gui.runtime` (`ui`/`widgets`) statt direkter `tkinter`-/`ttk`-Imports.
- Tk/ttk-Runtime-Pilotmigration erweitert: `kursplaner/adapters/gui/settings_window.py` nutzt jetzt zentrale Runtime-Aliases aus `bw_gui.runtime` (`ui`/`widgets`) statt direkter `tkinter`-/`ttk`-Imports.
- Tk/ttk-Runtime-Pilotmigration erweitert: `kursplaner/adapters/gui/new_lesson_window.py` nutzt jetzt zentrale Runtime-Aliases aus `bw_gui.runtime` (`ui`/`widgets`) statt direkter `tkinter`-/`ttk`-Imports.
- Tk/ttk-Runtime-Pilotmigration erweitert: `kursplaner/adapters/gui/popup_window.py` nutzt jetzt zentrale Runtime-Aliases aus `bw_gui.runtime` (`ui`/`widgets`) statt direkter `tkinter`-/`ttk`-Imports.
- Tk/ttk-Runtime-Pilotmigration erweitert: `kursplaner/adapters/gui/lesson_builder_dialog.py` nutzt jetzt zentrale Runtime-Aliases aus `bw_gui.runtime` (`ui`/`widgets`) statt direkter `tkinter`-/`ttk`-Imports.
- Tk/ttk-Runtime-Pilotmigration erweitert: `kursplaner/adapters/gui/overview_controller.py` nutzt jetzt zentrale Runtime-Aliases aus `bw_gui.runtime` (`ui`/`widgets`) statt direkter `tkinter`-/`ttk`-Imports.
- Tk/ttk-Runtime-Pilotmigration erweitert: `kursplaner/adapters/gui/selection_overlay_controller.py` nutzt jetzt zentrale Runtime-Aliases aus `bw_gui.runtime` (`ui`/`widgets`) statt direkter `tkinter`-/`ttk`-Imports.
- Tk-Runtime-Pilotmigration erweitert: `kursplaner/adapters/gui/toolbar_icon_styler.py` nutzt jetzt zentrale Runtime-Aliases aus `bw_gui.runtime` (`ui`) statt direktem `tkinter`-Import.
- Tk-Runtime-Pilotmigration erweitert: `kursplaner/adapters/gui/hover_tooltip.py` nutzt jetzt die Shared-Core-Bridge ohne direkten `tkinter`-Import.
- Shared-Dialogmigration gestartet: zentrale Bridge `kursplaner/adapters/gui/dialog_services.py` auf `bw_gui.dialogs` eingefuehrt und mehrere Controller (`action_controller.py`, `lesson_conversion_controller.py`, `overview_controller.py`, `path_settings_controller.py`, `editor_controller.py`, `selection_controller.py`, `column_reorder_controller.py`) von direkten `tkinter`-Dialogimports auf Shared-Services umgestellt.
- Shared-Dialogmigration erweitert: auch `new_lesson_window.py`, `lesson_builder_dialog.py`, `settings_window.py`, `ub_mark_dialog.py`, `popup_window.py` und `path_bootstrap.py` nutzen jetzt die zentrale Dialog-Bridge statt direkter `tkinter`-Dialogimports.
- Pilotmigration zum gemeinsamen GUI-Core gestartet: `bw-gui` als Git-Submodule eingebunden und `bw_libs/ui_contract/*` via Bridge auf `bw_gui.contracts.*` umgestellt, sodass Keybinding-/Popup-/HSM-Vertraege aus der gemeinsamen Quelle geladen werden.
- Erste UI-Flow-Uebernahme aktiv: `kursplaner/adapters/gui/hover_tooltip.py` nutzt jetzt die gemeinsame `bw_gui.widgets.HoverTooltip`-Implementierung, und `ui_theme.py` wendet eine gemeinsame Theme-Baseline vor kursplanerspezifischen Style-Overlays an.
- Shortcut-Hinweis aus dem Button-Label entfernt: `Zur Kursliste` zeigt kein `(Esc)` mehr; Shortcut-Hinweise bleiben im Hover-Overlay (`_add_help`).
- Runtime-Workspace-Root-Aufloesung fuer UB-/Plan-Use-Cases entkoppelt: statt festem Ordnernamen `7thCloud` nutzt die GUI-/Use-Case-Schicht jetzt eine zentrale, generische Root-Inferenz (`infer_workspace_root_from_path`) im Pfadmodul.
- G5 abgeschlossen: AppIdentity-Manifest `kursplaner/app_info.py` eingefuehrt und im Composition-Root als `app_info`/`shell_config`-Single-Source fuer Startup-Metadaten verdrahtet.
- G3/G4 gestartet: `build_gui_dependencies()` liefert jetzt auch eine zentrale Shell-Konfiguration; `KursplanerApp` verwendet injizierte `AppDependencies` und initialisiert das Hauptfenster ueber `bw_libs/app_shell.py`.
- G2.3 erweitert: weitere Repository-Write-Pfade nutzen jetzt zentrale Atomic-APIs (`plan_table_file_repository.py`, `plan_repository.py`, `ub_repository.py`, `lesson_file_repository.py`, `subject_source_repository.py`).
- G2.2 erweitert: `kursplaner/core/config/app_state_store.py` und `kursplaner/core/usecases/daily_course_log_usecase.py` nutzen jetzt die zentrale `atomic_write_json`-API.
- G2.1 gestartet: Shared-Modul `bw_libs/app_paths.py` eingefuehrt (AppPaths-Discovery sowie atomische JSON/Text-Write-Helfer).
- Persistenz-Pilot: `kursplaner/core/config/path_store.py` und `kursplaner/core/config/ui_preferences_store.py` nutzen jetzt die zentrale `atomic_write_json`-API.
- Guardrails beruecksichtigen `bw_libs/app_paths.py` als relevanten Shared-Pfad.
- UI-Contracts fuer Keybindings, Popup-Lifecycle und HSM wurden auf das Shared-Paket `bw_libs/ui_contract/` umgestellt; GUI und Tests importieren die Vertraege jetzt zentral statt aus lokalen Duplikatmodulen.
- Guardrails/Governance wurden auf `bw_libs/ui_contract`-Pfade umgestellt; `bw_libs/` wird bei Changelog-/Development-Log-Relevanz mitgeprueft.
- `kursplaner/adapters/gui/ui_intent_controller.py` validiert Intents jetzt gegen einen zentralen HSM-Contract vor der Intent-Delegation.
- Escape-Handling im Intent-Controller folgt jetzt zentraler Prioritaet: aktives Popup schliessen, dann Detail-Child-Zustaende abbauen, danach Rueckkehr in den Parent-State.
- Runtime-Debug-Popup wurde als nicht mode-blockierendes Parallel-Popup (`dialog.non_blocking`) verdrahtet; der Shortcut-Resolver behandelt nur noch mode-blockierende Popups als Dialog-Prioritaet.
- Wave-1-Hardening fuer Popup-Lifecycle: `kursplaner/adapters/gui/screen_builder.py` synchronisiert Laufzeit-Popups jetzt ueber `PopupPolicyRegistry` und nutzt die Registry im Runtime-Kontext als primaere Dialogquelle.
- Runtime-Dispatch konsolidiert: popup-sensitive Shortcut-Pfade pruefen zentral `_has_active_popup()` statt verteilter Einzelabfragen.
- Guardrails erweitert: `tools/ci/check_ai_guardrails.py` validiert jetzt zusaetzlich die tatsaechliche Runtime-Integration (`evaluate_runtime`, PopupPolicy-Nutzung) in `screen_builder.py`.
- Wave-1-Start fuer den Hybrid-Resolver: `kursplaner/adapters/gui/keybinding_registry.py` enthaelt jetzt einen zentralen Runtime-Kontextvertrag (`KeybindingRuntimeContext`) und eine einheitliche `evaluate_runtime`-API fuer mode-/offline-/textfokus-/dialogbasierte Aktivierungspruefung.
- Wave-1 konkret verdrahtet: globale Shortcuts in `kursplaner/adapters/gui/screen_builder.py` laufen jetzt ueber den zentralen Runtime-Resolver statt direkter Bind-Dispatches.

### Added
- HSM-Contract-Modul `kursplaner/adapters/gui/hsm_contract.py` eingefuehrt (Intent-/Payload-Validierung, Transition-Regeln, Escape-Resolver).
- Neue Tests `tests/test_hsm_contract.py` fuer Intent-Contract, Transition-Gates und Escape-Prioritaetskette.
- Tests fuer zentrale Runtime-Module: `tests/test_keybinding_runtime_registry.py` (Mode-/Reason-Matrix) und `tests/test_popup_policy_registry.py` (Stack-/Manifest-Lifecycle).
- Tabellarische Runtime-Debug-Ansicht fuer Shortcuts in der Hauptansicht (Menuepunkt `Ansicht -> Shortcut-Runtime-Debug`, Shortcut `Strg+Shift+D`) inkl. Offline-Simulation (`Strg+Shift+O`) und Aktiv/Disabled-Gruenden pro Modus.
- Guardrails praezisiert: `CHANGELOG.md` wird nun bei nutzer- oder coentwicklerrelevanten Aenderungen erzwungen; Prozesswarnungen (Commit-/Push-Guidance) werden nur noch lokal und nicht in CI ausgegeben.
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
