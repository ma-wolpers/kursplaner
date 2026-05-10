# Changelog

All notable user-facing changes to this project will be documented in this file.

The format is based on Keep a Changelog.

## [Unreleased]

### Fixed
- UB-Mark dialog now keeps at least one UB type selected: empty initial selections default to `Paedagogik`, and saving with no selected type is blocked with an error prompt.

### Changed
- Hover tooltips now appear with smoother delayed behavior, pick up the active app theme automatically, and stay fully visible on-screen.
- Shared settings and scrollbar theming received a visual polish via the updated `bw-gui` baseline styles.
- Shared main-menu overlays now close automatically when focus moves away (inside or outside the app window), so they no longer remain in front of other applications.
- Theme-Auswahl zeigt jetzt gemeinsam die Kursplaner- und Blattwerk-Themefamilien aus der zentralen Shared-GUI-Registry.
- Alt-Mnemonics im Hauptmenue sind auf dem Shared-CustomMenuBar-Pfad wieder sichtbar unterstrichen.
- Main menu rendering now uses the shared `bw_gui.menu.CustomMenuBar` with centralized menu definitions (including recent-undo and theme submenu handling), while keeping a native fallback path when shared menu modules are unavailable.
- Interactive startup path-check now creates its root window via shared `bw_gui.runtime.ui` aliases in `path_bootstrap.py` instead of importing `tkinter` directly.
- Window identity/icon helpers now use shared `bw_gui.runtime.ui` aliases in `window_identity.py` instead of importing `tkinter` directly.
- Column visibility popup wiring now uses shared `bw_gui.runtime` aliases (`ui`, `widgets`) in `column_visibility_dialog.py` instead of direct `tkinter`/`ttk` imports.
- Wrapped text field wiring now uses shared `bw_gui.runtime` aliases (`ui`, `widgets`) in `wrapped_text_field.py` instead of direct `tkinter`/`ttk` imports.
- Export selection and UB mark popups now use shared `bw_gui.runtime` aliases (`ui`, `widgets`) in `export_selection_dialog.py` and `ub_mark_dialog.py` instead of direct `tkinter`/`ttk` imports.
- LZK and shortcut overview popups now use shared `bw_gui.runtime` aliases (`ui`, `widgets`) in `lzk_column_dialog.py` and `shortcut_overview_dialog.py` instead of direct `tkinter`/`ttk` imports.
- Settings popup wiring now uses shared `bw_gui.runtime` aliases (`ui`, `widgets`) in `settings_window.py` instead of direct `tkinter`/`ttk` imports.
- New lesson popup wiring now uses shared `bw_gui.runtime` aliases (`ui`, `widgets`) in `new_lesson_window.py` instead of direct `tkinter`/`ttk` imports.
- Popup base window wiring now uses shared `bw_gui.runtime` aliases (`ui`, `widgets`) in `popup_window.py` instead of direct `tkinter`/`ttk` imports.
- Lesson builder popup wiring now uses shared `bw_gui.runtime` aliases (`ui`, `widgets`) in `lesson_builder_dialog.py` instead of direct `tkinter`/`ttk` imports.
- Overview loading dialog wiring now uses shared `bw_gui.runtime` aliases (`ui`, `widgets`) in `overview_controller.py` instead of direct `tkinter`/`ttk` imports.
- Selection overlay wiring now uses shared `bw_gui.runtime` aliases (`ui`, `widgets`) in `selection_overlay_controller.py` instead of direct `tkinter`/`ttk` imports.
- Toolbar icon loading/tinting now uses shared `bw_gui.runtime` alias (`ui`) in `toolbar_icon_styler.py` instead of direct `tkinter` imports.
- Hover tooltip wiring now uses the shared tooltip bridge in `hover_tooltip.py` without direct `tkinter` imports.
- UI intent routing now uses shared `bw_gui.runtime` aliases (`ui`, `widgets`) in `ui_intent_controller.py` instead of direct `tkinter`/`ttk` imports.
- Grid rendering now uses shared `bw_gui.runtime` alias (`ui`) in `grid_renderer.py` instead of direct `tkinter` imports.
- Theme styling helpers now use shared `bw_gui.runtime` aliases (`ui`, `widgets`) in `ui_theme.py` instead of direct `tkinter`/`ttk` imports.
- Main window state/setup now uses shared `bw_gui.runtime` alias (`ui`) in `main_window.py` instead of direct `tkinter` imports.
- Screen building/layout wiring now uses shared `bw_gui.runtime` aliases (`ui`, `widgets`) in `screen_builder.py` instead of direct `tkinter`/`ttk` imports.
- Action handling dialogs/overlays now use shared `bw_gui.runtime` aliases (`ui`, `widgets`) in `action_controller.py` instead of direct `tkinter`/`ttk` imports.
- Shared shell setup now uses `bw_gui.runtime.ui` in `bw_libs/app_shell.py` instead of direct `tkinter` imports.
- Dialog and file picker flows are now routed through shared `bw_gui.dialogs` services across controllers and key popup/startup/settings flows, reducing direct tkinter dialog coupling and aligning modal handling across apps.
- Pilot integration for the shared GUI core started: Kursplaner now resolves keybinding, popup, and HSM contracts through the shared `bw-gui` core (via submodule bridge), and routes hover tooltips through the shared tooltip widget.
- Theme configuration now applies a shared baseline from `bw-gui` before Kursplaner-specific style overlays.
- The `Zur Kursliste` button no longer embeds `(Esc)` in its label; the shortcut hint remains in the hover help.
- Workspace-root inference for UB/plan workflows is now decoupled from a hardcoded `7thCloud` folder name and resolved via a centralized generic path helper.
- App identity metadata is now centralized in `kursplaner/app_info.py` and injected through `AppDependencies` as the startup metadata source.
- Main window startup now uses injected `AppDependencies` with a centralized shell configuration, aligning GUI bootstrap and window lifecycle handling across apps.
- Additional repository persistence paths now use the centralized atomic writer APIs, including plan table/metadata, lesson files, UB files, and subject-source manifest writes.
- App-state and daily course log JSON persistence now use the centralized atomic writer from `bw_libs/app_paths.py`.
- Shared app path/atomic-write foundation introduced via `bw_libs/app_paths.py`; path and UI preferences config writes now use the centralized atomic JSON writer.
- Central UI contracts for keybindings, popup policy, and HSM semantics now live in shared `bw_libs/ui_contract` modules to avoid duplicate maintenance.
- Escape follows a centralized back-navigation priority in detail workflows: first close active popups, then leave child edit/navigation states, then return to the parent overview.
- UI intents are now validated against a central HSM contract before dispatch, improving shortcut and view-transition consistency.
- The shortcut runtime debug dialog now opens as a non-blocking parallel popup and no longer forces dialog-mode shortcut resolution for the main window.
- Popup-sensitive shortcut routing now uses a centralized popup-policy runtime source, improving consistency for dialog-priority behavior across global/detail interactions.
- Guardrail checks now validate runtime integration patterns in the UI flow (not only module existence) for centralized shortcut and popup governance.
- Governance checks now enforce changelog updates for user- or co-developer-relevant changes, and commit/push process hints are now local-only (not printed in CI logs).
- Wave-1 groundwork for unified shortcut runtime resolution: central keybinding registry now exposes a shared runtime context model and evaluate API for mode/offline/text-focus/dialog checks.
- Global shortcuts are now evaluated through a centralized runtime resolver before execution, so mode/dialog/text-focus/offline context is applied consistently.
- Beim Einfuegen mit Konfliktoption `Loeschen` wird die ersetzte Zieleinheit jetzt inklusive verknuepfter UB-Datei sauber aufgeraeumt; die UB-Uebersicht wird dabei direkt mit aktualisiert.
- `Strg+X` im Spaltenmodus schneidet jetzt die verlinkte Einheit fachlich aus (statt nur Zelltext) und markiert sie fuer Verschieben.
- Ausschneiden+Einfügen verschiebt eine Einheit mit UB jetzt als Move-Flow: alte Verknuepfung/Dateien werden aufgeraeumt, der UB wird auf das Ziel aktualisiert statt als zweiter UB stehen zu bleiben.
- Loeschen einer Einheit im Feld `Inhalt` entfernt jetzt die verknuepfte Einheiten-Datei statt nur den Tabelleninhalt; wenn ein Unterrichtsbesuch verknuepft ist, wird im Dialog zusaetzlich abgefragt, ob die UB-Datei mitgeloescht werden soll.
- Undo/Redo nach Einheits-Loeschen wurde auf Mehrdatei-Tracking gehaertet: Plan, Einheiten-Datei, optionale UB-Datei und UB-Uebersicht werden konsistent rueckgespielt.
- Beim Einfuegen einer kopierten Einheit mit verknuepftem UB erscheint jetzt immer eine Auswahl: `UB mitkopieren`, `ohne UB kopieren` oder `abbrechen`.
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
- New shortcut runtime debug dialog (`Ansicht -> Shortcut-Runtime-Debug`, `Strg+Shift+D`) with compact table output and offline simulation toggle (`Strg+Shift+O`).
- New runtime module tests for keybinding evaluation and popup policy stack behavior.
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
