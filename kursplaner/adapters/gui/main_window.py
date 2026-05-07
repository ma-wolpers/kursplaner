import pathlib
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui
from datetime import date

from bw_libs.app_shell import TkinterAppShell
from kursplaner.adapters.bootstrap.wiring import AppDependencies, build_gui_dependencies
from kursplaner.adapters.gui.action_controller import MainWindowActionController
from kursplaner.adapters.gui.column_reorder_controller import MainWindowColumnReorderController
from kursplaner.adapters.gui.editor_controller import MainWindowEditorController
from kursplaner.adapters.gui.grid_renderer import GridRenderer
from kursplaner.adapters.gui.grid_viewport_sync import GridViewportSync
from kursplaner.adapters.gui.lesson_context_controller import MainWindowLessonContextController
from kursplaner.adapters.gui.lesson_conversion_controller import MainWindowLessonConversionController
from kursplaner.adapters.gui.overview_controller import MainWindowOverviewController
from kursplaner.adapters.gui.path_bootstrap import ensure_paths_interactive
from kursplaner.adapters.gui.path_settings_controller import MainWindowPathSettingsController
from kursplaner.adapters.gui.screen_builder import ScreenBuilder
from kursplaner.adapters.gui.selection_controller import MainWindowSelectionController
from kursplaner.adapters.gui.toolbar_icon_styler import ToolbarIconStyler
from kursplaner.adapters.gui.ui_intent_controller import MainWindowUiIntentController
from kursplaner.adapters.gui.ui_state import MainWindowUiState
from kursplaner.adapters.gui.ui_theme import DEFAULT_THEME, normalize_theme_key
from kursplaner.adapters.gui.window_identity import (
    apply_window_icon,
    bring_window_to_front,
    configure_windows_process_identity,
)
from kursplaner.core.config.ui_preferences_store import (
    load_column_visibility_settings,
    load_theme_key,
    save_column_visibility_settings,
    save_theme_key,
)
from kursplaner.core.domain.plan_table import PlanTableData


class KursplanerApp(ui.Tk):
    """Hauptfenster-Adapter der Anwendung.

    Verantwortlich für UI-Zustand und Delegation an spezialisierte Controller;
    fachliche Entscheidungen liegen in den injizierten Use Cases/Flows.
    """

    def __init__(self, dependencies: AppDependencies | None = None):
        """Initialisiert Hauptfenster, Controller und UI-Grundzustand."""
        super().__init__()
        apply_window_icon(self)
        self.gui_dependencies = dependencies or build_gui_dependencies()
        self.app_shell = TkinterAppShell(self, self.gui_dependencies.shell_config)

        self.path_settings_usecase = self.gui_dependencies.path_settings_usecase
        self.new_lesson_form_usecase = self.gui_dependencies.new_lesson_form_usecase
        self.new_lesson_usecase = self.gui_dependencies.new_lesson_usecase

        self.path_values = self.path_settings_usecase.load_values()
        current_paths = self.path_settings_usecase.to_managed_paths(self.path_values)
        self.base_dir_var = ui.StringVar(value=str(current_paths.unterricht_dir))
        self.count_var = ui.StringVar(value="0 Kurspläne")
        persisted_theme = normalize_theme_key(load_theme_key(DEFAULT_THEME))
        self.theme_var = ui.StringVar(value=persisted_theme)
        self.preview_title_var = ui.StringVar(value="Kursplan")
        self.selected_column_var = ui.StringVar(value="Ausgewählte Spalte: keine")
        self.auto_row_mode_var = ui.BooleanVar(value=True)
        self.auto_scroll_next_unit_var = ui.BooleanVar(value=True)

        self.preview_font_size = 10
        self.preview_font = ("Consolas", self.preview_font_size)
        self.day_column_width = 260
        self.min_day_column_width = 140
        self.max_day_column_width = 1200
        self.collapsed_row_lines = 1
        self.expanded_row_max_lines = 20
        self.expand_long_rows_var = ui.BooleanVar(value=True)
        self.row_expanded: dict[str, bool] = {}
        self.clipboard_lesson_path: pathlib.Path | None = None

        self.current_table: PlanTableData | None = None
        self.day_columns: list[dict[str, object]] = []
        self.day_column_x_positions: dict[int, int] = {}
        self.lesson_load_errors: dict[str, str] = {}
        self._plan_overview_query = self.gui_dependencies.plan_overview_query
        self.row_display_mode_usecase = self.gui_dependencies.row_display_mode_usecase
        self.active_row_mode = self.row_display_mode_usecase.MODE_UNTERRICHT
        self.row_mode_buttons: dict[str, ui.Widget] = {}
        self.row_mode_labels: dict[str, str] = {
            item.key: item.label for item in self.row_display_mode_usecase.available_modes()
        }
        self.row_defs = self.row_display_mode_usecase.row_defs_for_mode(self.active_row_mode)
        self.column_visibility_settings = load_column_visibility_settings()
        self.raw_day_columns: list[dict[str, object]] = []

        self.cell_widgets: dict[tuple[str, int], ui.Text] = {}
        self.header_labels: dict[int, ui.Label] = {}
        self.row_labels: dict[str, ui.Label] = {}
        self.corner_label: ui.Label | None = None
        self.ui_state = MainWindowUiState()
        self.selected_day_indices = set()
        self._is_rebuilding_grid = False
        self.is_detail_view = False
        self.viewport_sync = GridViewportSync(self)

        self.overview_controller = MainWindowOverviewController(self)
        self.selection_controller = MainWindowSelectionController(self)
        self.editor_controller = MainWindowEditorController(self)
        self.lesson_context_controller = MainWindowLessonContextController(self)
        self.path_settings_controller = MainWindowPathSettingsController(self)
        self.lesson_conversion_controller = MainWindowLessonConversionController(self)
        self.column_reorder_controller = MainWindowColumnReorderController(self)
        self.ui_intent_controller = MainWindowUiIntentController(self)
        self.toolbar_icon_styler = ToolbarIconStyler(self)

        # extracted UI/component helpers
        self.screen_builder = ScreenBuilder(self)
        self.grid_renderer = GridRenderer(self)
        self.action_controller = MainWindowActionController(self)

        self.screen_builder.build_ui()
        self.screen_builder._bind_shortcuts()
        self.screen_builder._apply_theme()
        self.action_controller.refresh_overview()
        self.action_controller.update_action_controls()

    @property
    def selected_day_indices(self) -> set[int]:
        """Liefert den kanonischen Selektionszustand der Grid-Spalten."""
        return self.ui_state.selected_day_indices

    @selected_day_indices.setter
    def selected_day_indices(self, value: set[int]):
        """Setzt den kanonischen Selektionszustand der Grid-Spalten."""
        self.ui_state.selected_day_indices = set(value)

    @property
    def is_detail_view(self) -> bool:
        """Liefert den aktuellen Ansichtszustand (Overview vs. Detail)."""
        return self.ui_state.is_detail_view

    @is_detail_view.setter
    def is_detail_view(self, value: bool):
        """Setzt den aktuellen Ansichtszustand (Overview vs. Detail)."""
        self.ui_state.is_detail_view = bool(value)

    @staticmethod
    def _to_int(value: object, default: int = 0) -> int:
        """Konvertiert heterogene UI-Werte robust in `int` mit Fallback."""
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            text = value.strip()
            if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
                return int(text)
        return default

    def _handle_ui_intent(self, intent: str, **payload):
        """Delegiert die zentrale Intent-Verarbeitung an den dedizierten Intent-Controller."""
        controller = getattr(self, "ui_intent_controller", None)
        if controller is None:
            controller = MainWindowUiIntentController(self)
        return controller.handle_intent(intent, **payload)

    def _intent_course_confirm_selection(self, event):
        """Bestätigt die Kursauswahl aus der Übersicht über den Intent-Controller."""
        return self.ui_intent_controller.intent_course_confirm_selection(event)

    def _intent_course_hover_select(self, event):
        """Aktualisiert die Kursselektion bei Hover-Navigation in der Übersicht."""
        return self.ui_intent_controller.intent_course_hover_select(event)

    def _intent_toggle_row_expand(self, field_key: str):
        """Schaltet die Expandierung einer Detailzeile um."""
        return self.ui_intent_controller.intent_toggle_row_expand(field_key)

    def _intent_detail_left(self):
        """Navigiert in der Detailansicht zur vorherigen Spalte."""
        return self.ui_intent_controller.intent_detail_left()

    def _intent_detail_right(self):
        """Navigiert in der Detailansicht zur nächsten Spalte."""
        return self.ui_intent_controller.intent_detail_right()

    def _intent_escape(self):
        """Verarbeitet Escape gemäß aktivem UI-Kontext."""
        return self.ui_intent_controller.intent_escape()

    def _intent_clipboard_shortcut(self, event, *, operation: str):
        """Delegiert globale Zwischenablage-Shortcuts mit gewünschter Operation."""
        return self.ui_intent_controller.intent_clipboard_shortcut(event, operation=operation)

    def _intent_global_click_commit_cell(self, event):
        """Commitet aktive Zellbearbeitung bei globalem Klick außerhalb des Editors."""
        return self.ui_intent_controller.intent_global_click_commit_cell(event)

    def _should_handle_global_clipboard_shortcut(self, event, operation: str) -> bool:
        """Prüft, ob ein globaler Zwischenablage-Shortcut vom Grid behandelt werden soll."""
        return self.ui_intent_controller.should_handle_global_clipboard_shortcut(event, operation)

    @staticmethod
    def _widget_has_text_selection(widget) -> bool:
        """Prüft widget-agnostisch, ob aktuell eine Textauswahl aktiv ist."""
        return MainWindowUiIntentController.widget_has_text_selection(widget)

    def _on_theme_changed(self):
        """Reagiert auf Theme-Wechsel und aktualisiert Fenster plus Grid-Darstellung."""
        save_theme_key(normalize_theme_key(self.theme_var.get()))
        self._apply_theme()
        self._apply_grid_theme()

    def _open_column_visibility_settings(self):
        """Öffnet den Dialog zum Ein-/Ausblenden von Spaltenarten."""
        self.action_controller.open_column_visibility_settings()

    def _refresh_row_mode_button_styles(self):
        """Aktualisiert die Beschriftung der Modusbuttons gemäß aktivem Modus."""
        for mode_key, button in self.row_mode_buttons.items():
            base_label = self.row_mode_labels.get(mode_key, mode_key.title())
            label = f"● {base_label}" if mode_key == self.active_row_mode else base_label
            button.configure(text=label)

    def _set_row_mode(self, mode_key: str, *, manual: bool = True):
        """Setzt den aktiven Zeilen-Anzeigemodus und rendert bei Änderung neu."""
        normalized = self.row_display_mode_usecase.normalize_mode(mode_key)
        if manual:
            self.auto_row_mode_var.set(False)

        changed = normalized != self.active_row_mode
        self.active_row_mode = normalized
        self.row_defs = self.row_display_mode_usecase.row_defs_for_mode(self.active_row_mode)
        self._refresh_row_mode_button_styles()
        if changed:
            self._rebuild_grid()

    def _on_toggle_auto_row_mode(self):
        """Reagiert auf Umschalten des Auto-Modus für Zeilenansichten."""
        if bool(self.auto_row_mode_var.get()):
            self._update_row_mode_from_selection()

    def _set_column_visibility_settings(self, settings):
        """Setzt globale Sichtbarkeits-/Marker-Einstellungen und rendert neu."""
        self.column_visibility_settings = settings
        save_column_visibility_settings(settings)
        self._collect_day_columns()
        self._update_row_mode_from_selection()
        self._rebuild_grid()

    def _update_row_mode_from_selection(self):
        """Leitet den Zeilenmodus automatisch aus der selektierten Spaltenart ab."""
        if not bool(self.auto_row_mode_var.get()):
            return
        mode = self.row_display_mode_usecase.mode_for_selection(
            selected_day_indices=set(self.selected_day_indices),
            day_columns=list(self.day_columns),
            fallback_mode=self.active_row_mode,
        )
        self._set_row_mode(mode, manual=False)

    def _apply_theme(self):
        """Wendet das aktuelle Theme auf das Hauptfenster an."""
        return self.screen_builder._apply_theme()

    def _pick_base_dir(self):
        """Startet den Dialog zur Auswahl des Unterrichtsbasisordners."""
        return self.action_controller.pick_base_dir()

    def _apply_saved_paths(self, values: dict[str, str]):
        """Übernimmt gespeicherte Pfadwerte in den App-Zustand."""
        return self.action_controller.apply_saved_paths(values)

    def _archive_dir(self) -> pathlib.Path:
        """Liefert den aktuell verwendeten Archivordnerpfad."""
        return self.action_controller.archive_dir()

    def _auto_archive_enabled(self) -> bool:
        """Gibt zurück, ob automatisches Archivieren aktiv ist."""
        return self.action_controller.auto_archive_enabled()

    def _on_paths_saved(self, values: dict[str, str]):
        """Verarbeitet gespeicherte Pfadänderungen aus dem Settings-Dialog."""
        self.action_controller.on_paths_saved(values)

    def refresh_overview(self):
        """High-level Entry: lädt die linke Unterrichtsübersicht neu."""
        self.action_controller.refresh_overview()

    def open_new_lesson_window(self):
        """Öffnet den Dialog zur Erstellung einer neuen Unterrichtseinheit."""
        self.action_controller.open_new_lesson_window()

    def _clear_plan_table(self, title: str):
        """Setzt die rechte Planansicht auf einen leeren Ausgangszustand."""
        self.action_controller.clear_plan_table(title)

    def _undo_history(self):
        """Delegiert Undo an den Action-Controller."""
        self.action_controller.undo_history()

    def _redo_history(self):
        """Delegiert Redo an den Action-Controller."""
        self.action_controller.redo_history()

    def _on_grid_inner_configure(self, _event=None):
        """Synchronisiert Scrollregion/Layout nach Änderungen im Grid-Container."""
        return self.grid_renderer._on_grid_inner_configure(_event)

    def _on_canvas_configure(self, event):
        """Reagiert auf Größenänderungen des Canvas für responsive Grid-Breite."""
        return self.grid_renderer._on_canvas_configure(event)

    def _on_vertical_scroll(self, *args):
        """Delegiert vertikales Scrollen an beide Grid-Bereiche synchron."""
        return self.viewport_sync.yview(*args)

    def _on_horizontal_scroll(self, *args):
        """Delegiert horizontales Scrollen an Header- und Body-Canvas synchron."""
        return self.grid_renderer._on_horizontal_scroll(*args)

    def _load_selected_table(self, _event=None):
        """High-level Entry: lädt die aktuell selektierte Planung in die Detailansicht."""
        self.overview_controller.load_selected_table(_event)

    def _close_detail_view(self):
        """Schließt die Einheitenansicht und zeigt wieder nur die Kursliste."""
        self.overview_controller.close_detail_view()

    def _show_course_overview(self):
        """Zeigt die Kursliste als alleinige Hauptansicht."""
        self.screen_builder.show_course_overview()

    def _show_course_detail(self):
        """Zeigt die Einheitenansicht als alleinige Hauptansicht."""
        self.screen_builder.show_course_detail()

    def _collect_day_columns(self):
        """Aktualisiert die Grid-Projektion (`day_columns`) aus der geladenen Tabelle."""
        self.overview_controller.collect_day_columns()

    def _field_value(self, day: dict[str, object], field_key: str) -> str:
        """Liefert den darzustellenden Zellwert für ein Feld aus `day_columns`."""
        return self.lesson_context_controller.field_value(day, field_key)

    def _estimate_visual_lines(self, text: str) -> int:
        """Schätzt benötigte Anzeigezeilen für Text anhand UI-Regeln."""
        return self.lesson_context_controller.estimate_visual_lines(text)

    @staticmethod
    def _format_list_entries(entries: list[str]) -> str:
        """Formatiert Listeninhalte für die Darstellung in Grid-Zellen."""
        return MainWindowLessonContextController.format_list_entries(entries)

    @staticmethod
    def _parse_list_entries(text: str) -> list[str]:
        """Parst mehrzeilige Zelltexte in bereinigte Listeneinträge."""
        return MainWindowLessonContextController.parse_list_entries(text)

    @staticmethod
    def _keyword_match(text: str, keywords: list[str]) -> bool:
        """Prüft case-insensitiv, ob eines der Keywords im Text enthalten ist."""
        return MainWindowLessonContextController.keyword_match(text, keywords)

    @staticmethod
    def _contains_markdown_link(text: str) -> bool:
        """Erkennt Obsidian-Linksyntax `[[...]]` in einem Text."""
        return MainWindowLessonContextController.contains_markdown_link(text)

    def _parse_halfyear_token(self) -> str:
        """Liest Halbjahres-Token aus aktueller Planmetadatenlage."""
        return self.lesson_context_controller.parse_halfyear_token()

    def _parse_group_token(self) -> str:
        """Liest Lerngruppen-Token aus aktueller Planmetadatenlage."""
        return self.lesson_context_controller.parse_group_token()

    def _parse_subject_token(self) -> str:
        """Liest Fach-Token aus aktueller Planmetadatenlage."""
        return self.lesson_context_controller.parse_subject_token()

    def _parse_grade_token(self) -> str:
        """Liest Stufen-Token aus aktueller Planmetadatenlage."""
        return self.lesson_context_controller.parse_grade_token()

    def _build_regular_stem(self, topic: str, date_label: str = "") -> str:
        """Erzeugt einen normalisierten Dateistamm für regulären Unterricht."""
        return self.lesson_context_controller.build_regular_stem(topic, date_label)

    def _is_lzk_row(self, row_index: int) -> bool:
        """Prüft, ob die gegebene Tabellenzeile als LZK klassifiziert ist."""
        return self.lesson_context_controller.is_lzk_row(row_index)

    def _next_lzk_number(self) -> int:
        """Bestimmt die nächste freie LZK-Nummer im aktuellen Plan."""
        return self.lesson_context_controller.next_lzk_number()

    def _replace_plan_link(self, row_index: int, new_stem: str):
        """Ersetzt den Linktext in einer Planzeile durch einen neuen Dateistamm."""
        self.lesson_context_controller.replace_plan_link(row_index, new_stem)

    def _rename_linked_file_for_row(self, row_index: int, desired_stem: str) -> pathlib.Path | None:
        """Benennt die verlinkte Stunden-Datei einer Zeile auf den Zielstamm um."""
        return self.lesson_context_controller.rename_linked_file_for_row(row_index, desired_stem)

    def _toggle_column_selection(self, day_index: int):
        """Schaltet die Selektion einer Spalte und stößt Header-Update an."""
        self.selection_controller.toggle_column_selection(day_index)

    def _update_selected_column_label(self):
        """Aktualisiert das UI-Label für aktuell selektierte Grid-Spalten."""
        self.selection_controller.update_selected_column_label()

    def _refresh_header_styles(self):
        """Aktualisiert Header-Styling anhand Selektion und Theme-Zustand."""
        self.selection_controller.refresh_header_styles()

    def _selected_indices_sorted(self) -> list[int]:
        """Liefert selektierte Spaltenindizes in stabil sortierter Reihenfolge."""
        return self.selection_controller.selected_indices_sorted()

    def _collect_selected_or_warn(self) -> list[int]:
        """Liefert selektierte Spalten oder zeigt Hinweis bei leerer Auswahl."""
        return self.selection_controller.collect_selected_or_warn()

    def _get_single_selected_or_warn(self) -> int | None:
        """Liefert genau eine ausgewählte Spalte oder zeigt Warnhinweis."""
        return self.selection_controller.get_single_selected_or_warn()

    def _set_single_column_selection(self, day_index: int, *, ensure_visible: bool = False):
        """Setzt genau eine selektierte Spalte und optional den horizontalen Fokus darauf."""
        self.selection_controller.set_single_column_selection(day_index, ensure_visible=ensure_visible)

    def _move_selected_column_focus(self, direction: int) -> bool:
        """Verschiebt die Spaltenselektion per Tastatur zur nächsten stattfindenden Einheit."""
        return self.selection_controller.move_selection_to_adjacent_occurring(direction)

    def _create_text_cell(
        self,
        parent: ui.Widget,
        text: str,
        editable: bool,
        canceled: bool,
        unresolved_link: bool,
        height_lines: int,
        *,
        is_lzk: bool = False,
        lzk_masked: bool = False,
    ) -> ui.Text:
        """Erzeugt ein Text-Widget für eine Grid-Zelle mit passendem Rendering."""
        return self.grid_renderer._create_text_cell(
            parent,
            text,
            editable,
            canceled,
            unresolved_link,
            height_lines,
            is_lzk=is_lzk,
            lzk_masked=lzk_masked,
        )

    def _rebuild_grid(self):
        """High-frequency Entry: rendert das komplette Plan-Grid neu."""
        return self.grid_renderer._rebuild_grid()

    def _refresh_grid_content(self):
        """Aktualisiert Header/Zellen ohne kompletten Widget-Neuaufbau."""
        return self.grid_renderer.refresh_grid_content()

    def _update_grid_column(self, day_index: int):
        """Aktualisiert Header und alle Zellen einer bestehenden Spalte."""
        return self.grid_renderer.update_column(day_index)

    def _update_grid_cell(self, field_key: str, day_index: int):
        """Aktualisiert den Inhalt/Stil einer einzelnen existierenden Zelle."""
        return self.grid_renderer.update_cell(field_key, day_index)

    def _update_grid_header(self, day_index: int):
        """Aktualisiert nur den Header einer bestehenden Spalte."""
        return self.grid_renderer.update_header(day_index)

    def _update_grid_row_style(self, field_key: str):
        """Aktualisiert Label und Stil einer bestehenden Feldzeile."""
        return self.grid_renderer.update_row_style(field_key)

    def _apply_grid_theme(self):
        """Wendet Themefarben/-stile auf alle Grid-Komponenten an."""
        return self.grid_renderer._apply_grid_theme()

    def _ensure_link_for_day(self, day_index: int, preferred_topic: str = "") -> pathlib.Path | None:
        """Stellt sicher, dass für eine Spalte eine Stunden-Datei verlinkt ist."""
        return self.editor_controller.ensure_link_for_day(day_index, preferred_topic=preferred_topic)

    def _save_cell(self, field_key: str, day_index: int):
        """High-frequency Entry: persistiert Änderungen einer einzelnen Grid-Zelle."""
        self.editor_controller.save_cell(field_key, day_index)

    def _apply_value(self, field_key: str, day_index: int, value: str):
        """Übernimmt einen Zellenwert fachkonform in Tabelle/YAML und Persistenz."""
        self.editor_controller.apply_value(field_key, day_index, value)

    def _update_selected_lesson_metrics(self):
        """Aktualisiert die Übersichtsmetriken der aktuell selektierten Unterrichtszeile."""
        selected = self.lesson_tree.focus()
        if not selected or self.current_table is None:
            return

        values = list(self.lesson_tree.item(selected, "values"))
        if len(values) < 4:
            return

        next_theme, remaining_hours, next_lzk = self._plan_overview_query.summarize_plan(self.current_table)
        values[1] = next_theme
        values[2] = str(remaining_hours)
        values[3] = next_lzk
        self.lesson_tree.item(selected, values=tuple(values))

    def _on_grid_mousewheel(self, event):
        """Delegiert Scroll-/Zoom-Interaktion des Grids an den Renderer."""
        return self.grid_renderer._on_grid_mousewheel(event)


def main():
    """Startet die GUI-Anwendung nach interaktivem Pfad-Bootstrap."""
    configure_windows_process_identity()
    dependencies: AppDependencies = build_gui_dependencies()
    if not ensure_paths_interactive(path_settings_usecase=dependencies.path_settings_usecase):
        return

    app = KursplanerApp(dependencies=dependencies)
    apply_window_icon(app)
    app.after(60, lambda: bring_window_to_front(app))
    app.after(240, lambda: app.overview_controller.ensure_course_selected(prefer_first=True))
    app.after(260, app.lesson_tree.focus_set)

    def _run_daily_course_log_export() -> None:
        """Exportiert einmal täglich einen JSON-Snapshot aller aktuellen Kurse."""
        today = date.today()
        if not dependencies.daily_log_state_usecase.should_log_for_day(today):
            return
        try:
            managed_paths = dependencies.path_settings_usecase.to_managed_paths(
                dependencies.path_settings_usecase.load_values()
            )
            result = dependencies.daily_course_log_usecase.export_for_day(
                unterricht_dir=managed_paths.unterricht_dir,
                export_day=today,
            )
            if result.created:
                dependencies.daily_log_state_usecase.mark_logged(today)
        except Exception as exc:
            print(f"Daily course log export failed: {exc}")

    app.after(320, _run_daily_course_log_export)
    app.mainloop()

