# Changelog

All notable user-facing changes to this project will be documented in this file.

The format is based on Keep a Changelog.

## [Unreleased]

### Added
- **Schulweite Ausfälle**: Neues Popup „Schulweite Ausfälle…" (Button in der Kursübersicht, neben „Neuer Kurs"), um einen Ausfall (z. B. Wandertag, pädagogischer Tag) für mehrere Kurse gleichzeitig einzutragen — Grund, Zeitraum und betroffene Jahrgangsstufen (Grundschule/Sek I/Sek II, aufklappbar bis auf einzelne Stufen). Eine Live-Vorschau zeigt bei jeder Eingabe sofort, welche konkreten Kurse/Einheiten betroffen wären; bereits durch einen anderen Ausfall beanspruchte Tage werden markiert. Beim Speichern werden die betroffenen Einheiten automatisch als Ausfall markiert und ihr Inhalt in die nächste freie Lücke verschoben — findet sich keine, wird eine neue Einheit ohne Datum angehängt (im Grid rot umrandet dargestellt, Header + Zelle). Bestehende Einträge lassen sich im selben Fenster bearbeiten oder löschen (nimmt alle Verschiebungen automatisch zurück). Tritt während des Speicherns/Löschens ein Fehler oder Konflikt auf (z. B. eine Zeile wurde inzwischen manuell verändert), fragt ein Dialog nach: Nochmal versuchen, Überspringen, gesamten Vorgang zurückrollen oder (bei bloßen Warnungen) trotzdem durchführen. Ein informativer Hinweis beim Öffnen des Popups zeigt an, falls gespeicherte Einträge nicht mehr zum tatsächlichen Kursplan-Zustand passen.
  - Auch die bestehende „Stundenplanänderung…" warnt jetzt nicht-blockierend, wenn der gewählte Zeitraum einen aktiven schulweiten Ausfall berührt.
  - Betroffen: `core/domain/{grade_groups,plan_row_placement,school_wide_cancellation,row_identity}.py`, `core/config/school_wide_cancellations_store.py`, `core/usecases/school_wide_cancellation_{preview,apply,revert,overlap_query,diagnostics}_usecase.py`, `core/usecases/bulk_cancellation_coordinator.py`, `core/flows/school_wide_cancellation_flow.py`, `adapters/gui/{grade_group_selector,school_wide_cancellation_dialog,conflict_decision_dialog}.py`.
- **Startzeit pro Wochentag**: Kurse haben jetzt einen echten Wochenrhythmus (Startzeit + Stundenzahl je Wochentag), editierbar sowohl beim Kurs-Anlegen ("Neuer Kurs") als auch bei einer späteren Stundenplanänderung. Eine neue, nicht editierbare Grid-Zeile "Wann" zeigt die Startzeit jedes Kurstags direkt über "Wie lange" an — auch bei noch leeren, nicht verlinkten Einheiten.
- **Automatische Kurs-Archivierung**: Ein Kurs wandert automatisch ins Archiv, sobald sein letztes Plandatum in der Vergangenheit liegt, und automatisch zurück, sobald eine Verlängerung das letzte Datum wieder in die Zukunft verschiebt. "Ehemalige anzeigen" (Strg+Shift+E) zeigt archivierte Kurse weiterhin wie gewohnt an.
- **Ausfallgrund als eigene Grid-Zeile**: Der Grund eines Ausfalls (bisher nur in der Kopfzeile der Spalte sichtbar) erscheint jetzt zusätzlich als eigene, nicht editierbare Zeile "Ausfallgrund" bei Ausfall-Einheiten.
- **"Zeilenfelder…" jetzt pro Anzeige-Modus konfigurierbar**: Statt einer einzigen Anzeigen-Checkbox pro Zeilenfeld gibt es jetzt vier Checkboxen (Unterricht/LZK/Ausfall/Hospitation) — ein Feld lässt sich dadurch für einzelne Modi ausblenden oder auch in Modi einblenden, in denen es standardmäßig nicht vorkommt (z. B. "Stundenziel" zusätzlich bei Ausfall anzeigen).
- **Stundenplanänderung**: Neues Popup (Aktion → Stundenplanänderung…) für die Umverteilung eines Kursplans auf einen geänderten Stundenrhythmus. Spalten der linken Seite zeigen den bisherigen Plan im gewählten Datumsbereich; die rechte Seite enthält den editierbaren Entwurf des neuen Plans. Aktionen: Ausfall/Stattfinden-Toggle, ↑/↓-Tausch, Entfernen, Strg+Z (dialog-intern). Klick auf Übernehmen erzeugt einen einzelnen Undo-Eintrag in der Hauptansicht.
  - `core/usecases/timetable_change_usecase.py`: `TimetableChangeUseCase.compute()`, `DraftSlot`-Dataclass, Prädikat-Wrapper `column_is_ferien`, `column_is_manual_ausfall`, `column_is_stattfindend`, Wochenvergleich für `was_recovered_week`.
  - `core/usecases/apply_timetable_change_usecase.py`: `ApplyTimetableChangeUseCase.execute()` spliced neuen Datumsblock in `table.rows` und speichert via `PlanRepository`.
  - `adapters/gui/timetable_change_dialog.py`: `TimetableChangeDialog(ScrollablePopupWindow)`, PanedWindow-Splitansicht mit zwei Treeviews, Header (Von/Bis-Eingabe, Wochentagsauswahl, Berechnen), Footer (Aktionsknöpfe, Übernehmen/Abbrechen), dialog-interner Undo-Stack.
  - `adapters/gui/ui_intents.py`: `OPEN_TIMETABLE_CHANGE = "detail.open_timetable_change"`.
  - `adapters/gui/screen_builder.py`: Menüpunkt „Stundenplanänderung…" im Aktion-Menü.
  - `adapters/gui/ui_intent_controller.py`: Dispatch für `OPEN_TIMETABLE_CHANGE`.
  - `adapters/gui/action_controller.py`: `open_timetable_change()`.
  - `adapters/bootstrap/wiring.py`: `TimetableChangeUseCase` und `ApplyTimetableChangeUseCase` verdrahtet.
  - Tests: `tests/test_timetable_change_usecase.py` (15 Tests), `tests/test_apply_timetable_change_usecase.py` (7 Tests).

### Changed
- **"Neuer Unterricht" heißt jetzt "Neuer Kurs"**: Der Dialog legt einen ganzen Kurs an, keine einzelne Stunde — der bisherige Name war irreführend.
- **Stunden-Spalte der Plantabelle entfällt**: Die Stundenzahl je Kurstag wird jetzt aus dem neuen Wochenrhythmus abgeleitet, statt in jeder Zeile einzeln gespeichert zu werden (dadurch war sie bisher redundant zum tatsächlichen Rhythmus). Bestehende Kurse wurden automatisch auf das neue Format gehoben.
- **Ferien jetzt am Markierungsformat erkennbar**: Ferien-/Feiertagszeilen tragen jetzt `X Grund X` (mit Schluss-X) in der Thema/Ausfall-Spalte, ein normaler Ausfall (z. B. Krankheit) bleibt beim einfachen `X Grund`. Dadurch sind Ferien direkt im Text erkennbar, statt sich nur aus der jetzt entfallenen Stundenzahl=0 zu ergeben.
- **UB-Dateinamen vereinfacht**: Unterrichtsbesuch-Dateien heißen jetzt ``ub yy-mm-dd.md`` statt ``UB yy-mm-dd Einheitstitel.md``. Der Titel wird nicht mehr im Dateinamen kodiert, um Link-Drift bei Titeländerungen zu verhindern. ``build_ub_stem`` nimmt nur noch das Datum als Argument. Alle ``Unterrichtsbesuch``-Links in Einheitendateien und die ``UB Übersicht`` wurden via ``tools/migrate_ub_filenames.py`` aktualisiert.
- **Feld "Titel (Dateiname)" im "Einheit planen"-Dialog entfernt**: Das Feld täuschte Kontrolle über den Dateinamen vor, die es tatsächlich hatte — aber auf eine Art, die der dokumentierten Namensregel widersprach: Neue Einheiten-Dateien bekamen zunächst den vorgesehenen 6-stelligen Zufallscode, wurden aber im selben Speichervorgang sofort wieder auf einen aus dem Titel abgeleiteten Namen umbenannt. Einheiten-Dateinamen bleiben jetzt durchgehend beim bei Anlage vergebenen Zufallscode (auch beim Verschieben von Spalten per ↑/↓).

### Removed
- **"Einheit aufsplitten"/"Einheiten zusammenführen" (Strg+T/Strg+M)**: Ein Kurstag hat im aktuellen Datenmodell genau eine Einheit; die Stundenzahl kommt vollständig aus dem Wochenrhythmus. Split/Merge stellte technisch weiterhin die Möglichkeit mehrerer Einheiten pro Kurstag her, obwohl das im neuen Modell nicht mehr vorgesehen ist, und wurde daher ersatzlos entfernt (Toolbar-Buttons, Kontextmenü-Einträge, Tastenkürzel).

### Fixed
- Ein bewusst als Obsidian-Link gespeichertes Oberthema (`[[Gruppe Thema]]`) wurde in der Kursübersicht, im Grid und in Exporten als roher Link statt als Klartext angezeigt. Zusätzlich konnte dieselbe Themenfolge fälschlich in zwei getrennte Sequenzen zerfallen, wenn eine Einheit den Klartext und die nächste den Link trug (Kompetenzhorizont-Export war ebenso betroffen). Klartext und Link-Schreibweise werden jetzt überall als dasselbe Thema erkannt und einheitlich als Klartext angezeigt; die YAML-Speicherung bleibt unverändert verlinkt.
- Beim Umwandeln einer leeren Planzeile in "Unterricht" wurde ein bereits direkt in diese Zeile eingetragenes Oberthema nicht in den Dialog übernommen — stattdessen wurde immer nach dem Oberthema der letzten Vorzeile mit verlinkter Stunden-Datei gesucht. Ein in der aktuellen Zeile bereits eingetragenes Oberthema hat jetzt Vorrang.
- Das automatische Verschieben vergangener Einheitsdateien nach `Alteinheiten/` beim Programmstart lief seit Einführung des Features nie tatsächlich — ein fehlendes `plan_repo`-Feld in der zentralen Dependency-Verdrahtung (`GuiDependencies`) ließ den Schritt bei jedem Start mit `'GuiDependencies' object has no attribute 'plan_repo'` fehlschlagen (stumm abgefangen, nur als Konsolenzeile sichtbar). `plan_repo` wird jetzt korrekt durchgereicht.
- Strg+Z (Rückgängig) wirkte nach dem Bearbeiten einer Grid-Zelle manchmal nicht mehr per Tastenkürzel, obwohl der Rückgängig-Button in der Toolbar weiterhin funktionierte — z. B. nach: Zelle editieren → auf einen Toolbar-Button klicken (statt Escape/Strg+Enter oder eine andere Zelle anzuklicken). Der Tastaturfokus blieb dabei auf der bereits gespeicherten Zelle hängen, wodurch nachfolgende Tastenkürzel fälschlich als "Textfeld wird gerade bearbeitet" erkannt wurden. Strg+Z funktioniert jetzt in diesem Fall wieder zuverlässig.
- Escape schloss den Unterrichtseinheitcreator sowie mehrere kleinere Auswahl-Popups nicht, solange der Fokus in einem Textfeld lag (also praktisch beim normalen Ausfüllen). Escape schließt Popups jetzt immer, unabhängig vom Fokus.
- Escape im Ausfallgrund-Eingabefeld (z. B. bei "Als Ausfall markieren") schloss zwar das Eingabefeld, wirkte aber zusätzlich auf das dahinterliegende Fenster (z. B. sprang die Grid-Auswahl ungewollt eine Stufe zurück, oder ein übergeordneter Dialog wie "Stundenplanänderung" konnte sich mitschließen). Escape wirkt jetzt nur noch auf das Eingabefeld selbst.
- Toolbar-Icons wurden manchmal gar nicht, nur kurz aufblitzend oder erst nach einem Themenwechsel korrekt angezeigt (Disabled-Icons sowie die Status-Wechsel-Icons für UB-Markierung und Ausfall). Ursache war ein fehlender Python-Verweis auf neu eingefärbte Icon-Bilder in `adapters/gui/toolbar_icon_styler.py::apply_state_overrides()`, wodurch Tkinter die Bilder sofort wieder freigab. Behoben über die neue Hilfsfunktion `bw_gui.theming.retain_icon_override()`.
- "Neuer Unterricht" zeigte eine unvollständige Kalenderdaten-Abdeckung (fehlende Ferien-/Feiertagsjahre) bisher nur als leicht zu übersehenden Zusatztext im Erfolgs-Popup an. Es erscheint jetzt eine eigene, prominente Warnung vor dem Erfolgs-Popup, inklusive Hinweis, wo aktuelle .ics-Kalenderdateien heruntergeladen werden können (ferienwiki.de).
- Der Kalenderordner hatte bisher einen im Code hinterlegten Rate-Pfad als Fallback, der auf einen nicht mehr existierenden Ordner zeigte. Fehlt der Kalenderordner jetzt in der lokalen Konfiguration, wird das beim Start als eigener Konfigurationshinweis erkannt und interaktiv abgefragt, statt auf einen möglicherweise falschen Pfad zurückzufallen.
- Stundenplanänderung (Aktion → Stundenplanänderung…) ließ das Oberthema noch nicht angelegter Einheiten beim Umverteilen auf einen neuen Stundenrhythmus verschwinden. Der Oberthema-Zellwert wird jetzt zusammen mit dem Inhalt übernommen (`DraftSlot.oberthema_cell`), im Entwurfs-Dialog angezeigt und beim Übernehmen mitgeschrieben.
- "Leer ausblenden" (Spaltenarten…) blendete Einheiten mit bereits gesetztem Oberthema, aber ohne verlinkte Stunden-Datei fälschlich als leer aus. `ColumnVisibilityProjectionUseCase._is_empty_day()` berücksichtigt jetzt auch das Oberthema.
- Text, der außerhalb von Kursplaner direkt vor oder nach der Einheitentabelle in die Kursplan-Datei geschrieben wurde, ging bisher verloren, sobald danach aus Kursplaner heraus irgendeine Zelle gespeichert wurde (z. B. Oberthema, Inhalt, Stunden) — die App überschrieb ihn mit dem Stand von vor der externen Änderung. Kursplaner erkennt jetzt, wenn sich die Datei seit dem Laden des Kurses extern geändert hat, und übernimmt den aktuellen Text vor/nach der Tabelle, bevor gespeichert wird.
- Ein Fehlschlagen beim Speichern des Fachquellen-Index (z. B. Festplatte voll oder Schreibrechte fehlen) wird jetzt als Fehlermeldung angezeigt statt unbemerkt zu verschwinden.
- Einheiten werden nach dem Löschen oder Ändern ihres Oberthemas jetzt automatisch aus der zugehörigen Sequenz-Datei entfernt (vorher blieben sie in deren Export-Tabelle stehen, egal welche Aktion die Änderung ausgelöst hat). Wird eine Sequenz-Datei dadurch komplett inhaltsleer (keine Einheiten, kein Sequenzziel/Leitkompetenz, kein Brainstorming-Text), wird sie gelöscht statt als leere Hülle liegen zu bleiben.
- Strg+Enter verlässt jetzt zuverlässig den Bearbeitungsmodus einer Grid-Zelle (Inhalt wird gespeichert, Auswahl springt zurück auf einfache Zellselektion) — vorher hatte der Shortcut während des Tippens keine Wirkung.
- Escape wird während des Ladens eines Kursplans nicht mehr verschluckt: vorher konnte ein Escape-Tastendruck, während der Lade-Hinweis sichtbar war, spurlos verpuffen, ohne die Auswahl (Zelle → Spalte → Kurs) eine Stufe zurückzusetzen.
- Sequenzziel-/Leitkompetenz-Zeile wird durch ausgeblendete Spaltenarten ("Spaltenarten…") nicht mehr unterbrochen: die spannende Zelle zieht sich jetzt über die schmale Marker-Spalte hinweg statt in zwei getrennte Zellen zu zerfallen.
- Ein im "Einheit planen"-Dialog eingegebenes Oberthema wurde bisher nur in die YAML der Einheiten-Datei geschrieben, aber nicht in die "Thema/Ausfall"-Spalte der Plantabelle übernommen — die Spalte blieb leer bzw. veraltet, obwohl der Wert im Plan sichtbar sein sollte. Wird jetzt beim Speichern korrekt synchronisiert.
- "Zeilenfelder…" blendet "Inhalt" jetzt auch bei Einheiten ohne verlinkte Stunden-Datei zuverlässig aus (vorher wurde der Zeilenfilter für "Inhalt"/"Stunden" bei solchen Tagen ignoriert).
- Oberthema lässt sich bei leeren, noch nicht angelegten Einheiten jetzt direkt im Grid anzeigen und eingeben — der Wert wird in die `Thema/Ausfall`-Zelle der Kurstabelle geschrieben, ohne dass zuerst eine Stunden-Datei angelegt werden muss.
- Kursübersicht zeigt bei "Nächste Einheit" jetzt zuverlässig die tatsächlich nächste stattfindende Einheit statt gelegentlich ein Ferien-/Ausfalldatum: Ausfall-/Ferienerkennung liest wieder die richtige `Thema/Ausfall`-Spalte statt der seit der 4-Spalten-Migration nur noch Links tragenden `Inhalt`-Spalte. Betroffen war auch die "Als Ausfall markieren"-Aktion selbst (schrieb den Ausfallgrund in die falsche Spalte, sichtbar wurde das nur bei Einheiten ohne bereits verlinkte Stunden-Datei) sowie das Verschieben bestehender Einheiten (`shift_existing_lessons_forward` konnte eine Einheit versehentlich in eine Ferien-/Ausfallzeile schieben).
- Sequenz-Markdown-Dateien tracken ihre zugehörigen Einheiten jetzt automatisch am Ende (`## Export`-Abschnitt) bei jedem Neuladen des Kursplans, nicht mehr nur nach manuellem "Exportieren als...".
- Leere, noch nicht angelegte Einheiten zeigen jetzt ein Oberthema, wenn die Kurstabelle ihnen bereits eines zugeordnet hat, und zählen entsprechend zu ihrer Sequenz.
- Rauszoomen im Kursplaner (Strg+Mausrad) baut das Grid nicht mehr bei jedem einzelnen Scroll-Tick sofort komplett neu auf; mehrfaches schnelles Scrollen sammelt sich jetzt zu einem einzigen Rebuild, sobald das Scrollen pausiert.
- UB-Mark dialog now keeps at least one UB type selected: empty initial selections default to `Paedagogik`, and saving with no selected type is blocked with an error prompt.
- Course selection no longer opens an empty mini popout: parent/transient dialog calls now resolve to the real Tk root path when the app runs through `TkRootHost`, so opening a course reliably switches to detail view.
- Stundenziel/Kompetenzen popup dialogs are interactive again: popup-owner parent/transient resolution now points to a valid Tk window path, restoring typing, apply/save actions, and popup-local shortcut handling.
- **Kritisch**: Übernehmen einer Stundenplanänderung konnte die Kursdatei ab dem `Rhythmus`-Block abschneiden — schließendes Frontmatter-`---`, komplette Plantabelle und alles danach gingen verloren, wenn `Rhythmus` das letzte Feld der Frontmatter war (nach der Migration der Normalfall). Betroffene Dateien lassen sich am fehlenden schließenden `---` bzw. der fehlenden Tabelle nach dem `Rhythmus:`-Block erkennen. Zusätzlich: ein neuer Stundenplan-Rhythmus wurde immer als zusätzliches, datiertes Segment neben dem alten gespeichert, auch wenn der neue Rhythmus faktisch seit Kursbeginn gilt (keine frühere Planzeile vorhanden) — der Rhythmus wird in diesem Fall jetzt korrekt komplett ersetzt statt sinnlos ergänzt.

### Changed
- Kursübersicht zeigt jetzt eine zusätzliche Spalte `Nächste Einheit`; die Datumsbewertung nutzt dieselbe konfigurierbare Tages-Cutoff-Regel wie die UB-Auswertungen (heutige Einheiten zählen ab Cutoff als vergangen).
- Kursübersicht und Einheitenansicht sind grafisch entkoppelt: die Detail-Toolbar ist in der Kursübersicht nicht mehr sichtbar, und die Kursübersicht besitzt eine eigene Toolbar.
- Ehemalige Kurse (ohne kommende Einheiten) sind in der Kursübersicht standardmäßig ausgeblendet und lassen sich per Button oder `Strg+Shift+E` ein-/ausblenden.
- Kursübersicht markiert nahe Termine fett; das Zeitfenster ist in den Einstellungen konfigurierbar (Default: 5 Tage).
- AI guardrails now emit non-blocking local warnings when configured core keyboard intents (for example new/export/undo/redo/copy/cut/paste/escape/settings) are present but matching shortcut binding markers are missing in the configured runtime/shortcut sources.
- UI contract bridges are now fully decommissioned to thin shared re-export shims (`bw_libs/ui_contract/keybinding.py`, `bw_libs/ui_contract/popup.py`, `bw_libs/ui_contract/hsm.py`, `bw_libs/ui_contract/laufkern.py`); dead local duplicate implementations were removed.
- AI guardrails now enforce a Phase-I decommission gate for UI contract bridges: each bridge must keep `ensure_bw_gui_on_path` plus shared `bw_gui` imports and may not reintroduce local contract class/function implementations.
- AI guardrails now enforce LaufKern fallback sunset Wave-3: local `ModuleNotFoundError` fallback branches were removed from the central contract bridges (`bw_libs/ui_contract/keybinding.py`, `bw_libs/ui_contract/popup.py`, `bw_libs/ui_contract/hsm.py`, `bw_libs/ui_contract/laufkern.py`), and fallback handlers are now forbidden repo-wide in guardrail scan scopes.
- Kursplaner bindet jetzt eine zentrale LaufKern-Bridge (`bw_libs.ui_contract.laufkern`) fuer Manifest-, Reachability- und Tracking-Vertraege ein und bereitet damit die Trennung "Programm = Was" und "LaufKern = Wie" technisch vor.
- Die Shortcut-Runtime-Debug-Ansicht zeigt jetzt zusaetzlich eine LaufKern-Zusammenfassung zur aktuellen Intent-Erreichbarkeit (erreichbare Intents pro Runtime-Kontext und Manifest-Validierungsstatus).
- Der LaufKern-Manifestaufbau wurde in einen dedizierten Provider (`kursplaner/adapters/gui/laufkern_manifest_provider.py`) ausgelagert, damit Runtime-Integration (Wie) und app-spezifische Deklaration (Was) klar getrennt bleiben.
- Der produktive UI-Intent-Dispatch protokolliert jetzt LaufKern-Tracking-Artefakte; das Runtime-Debug zeigt dazu einen Completion-Status aus der Artefaktaggregation.
- AI guardrails now enforce LaufKern fallback sunset Wave-2: `except ModuleNotFoundError` is only allowed in the central contract bridges (`bw_libs/ui_contract/keybinding.py`, `bw_libs/ui_contract/popup.py`, `bw_libs/ui_contract/hsm.py`, `bw_libs/ui_contract/laufkern.py`); new local fallback branches are rejected.
- AI guardrails now also block local redefinitions of reserved shared primitives (`TkRootHost`, `ScrollablePopupWindow`, `WrappedTextField`) so these runtime/dialog/widget foundations must be consumed from `bw-gui`; the existing popup compatibility adapter remains explicitly allowlisted.
- Main-window hosting and popup/form helper wiring now use the new shared bw-gui primitives (`bw_gui.runtime.TkRootHost`, `bw_gui.dialogs.ScrollablePopupWindow`, `bw_gui.widgets.WrappedTextField`) instead of maintaining local host/widget implementations.
- AI guardrails now include `bw_libs/` in the repo-wide GUI contract scan scope, so direct `tkinter`/`ttk` imports and new local `ui`/`widgets`/`tui` baseclass patterns are also blocked in shared-library paths.
- AI guardrails no longer keep legacy class allowlist exemptions in `kursplaner/adapters/gui/main_window.py`, `kursplaner/adapters/gui/popup_window.py`, and `kursplaner/adapters/gui/wrapped_text_field.py`; these adapters now use composed shared runtime roots/widgets instead of local UI baseclass inheritance.
- AI guardrails no longer keep future-entrypoint baseline exemptions for `kursplaner/adapters/gui/main_window.py` and `kursplaner/adapters/gui/screen_builder.py`; both now run under strict shared-GUI contract checks.
- AI guardrails now require an explicit GUI migration backlog (`docs/GUI_MIGRATION_BACKLOG.md`) for active GUI baselines/exemptions, including time-bound `remove_by` tracking.
- Governance policy now explicitly requires strict bw-gui-only usage: no local tkinter/ttk widget implementations in repo modules, and reusable GUI building blocks must be implemented in bw-gui first.
- AI guardrails now enforce repo-wide strict bw-gui usage in `kursplaner/adapters/gui`: direct `tkinter`/`ttk` imports and new local `ui`/`widgets`/`tui` baseclass patterns are rejected via AST-based checks (with a legacy allowlist for existing classes).
- AI guardrails now also enforce shared-GUI bootstrap requirements for any newly added GUI entrypoint files and reject direct tkinter imports in those entrypoints.
- AI guardrails were hardened to enforce mandatory shared UI contracts in `kursplaner/adapters/gui/screen_builder.py` and `kursplaner/adapters/gui/hover_tooltip.py` and fail fast on legacy fallback branches.
- Shared UI fallback branches were removed from `kursplaner/adapters/gui/screen_builder.py` and `kursplaner/adapters/gui/hover_tooltip.py`: the shared menu bar, shared shortcut hover formatter, and shared tooltip widget are now mandatory runtime paths.
- Theme special paths were removed from `kursplaner/adapters/gui/ui_theme.py`: shared theme registry and baseline style wiring are now mandatory, and optional fallback branches for missing shared theming were deleted.
- Settings now open through the shared `bw_gui.dialogs.open_tabbed_settings_dialog` renderer with unified section navigation for path settings, UB cutoff, and lesson-builder field toggles.
- Toolbar and action hover overlays now resolve shortcut hints from the central runtime keybinding registry, keeping tooltip wording and active shortcut labels consistent.
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
- Technische Grundlage fuer Sequenzplanung hinzugefuegt: neue Sequenz-Dateiverwaltung (`Sequenzen`), persistente Datei-Relations-Registry und automatischer Registry-Rebuild beim Start sowie nach getrackten Schreibvorgaengen.

### Performance
- Grid-Zellnavigation (Pfeiltasten) erheblich beschleunigt: `set_selected_cell()` in `selection_controller.py` nutzt jetzt einen Fast Path, der nur die 2 betroffenen Zellen und max. 2 Spalten-Header aktualisiert statt das gesamte Grid neu zu zeichnen; alle anderen Zellen bleiben unberührt.
- `_row_layout()` in `grid_renderer.py` cacht berechnete Zeilenhöhen pro Feldschlüssel; Cache wird bei Datenschreibvorgängen (`collect_day_columns()` in `overview_controller.py`) und vollständigem Grid-Rebuild (`_rebuild_grid()`) invalidiert.
- `update_action_controls()` in `action_controller.py` wird bei Navigation mit 80 ms Debounce geplant (`schedule_action_controls_update()`), sodass gehaltene Pfeiltasten nur einen einzigen Toolbar-Update auslösen statt bei jedem Keypress synchron den System-Clipboard abzufragen.
- `parse_group_token()` in `lesson_context_controller.py` cacht das Ergebnis per `id(current_table)` und verhindert ~100 redundante Stringoperationen pro Grid-Refresh.

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
