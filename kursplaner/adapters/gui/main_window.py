import pathlib

from bw_libs.shared_gui_core import ensure_bw_gui_on_path
from kursplaner.core.domain.day_column import DayColumn

ensure_bw_gui_on_path()
from bw_gui.runtime import BwBaseWindow, ui  # noqa: F401,E402
from bw_gui.dialogs import open_tabbed_settings_dialog as _open_tabbed_settings_dialog_contract_marker  # noqa: F401,E402
from bw_gui.menu import section_spec  # noqa: E402
from bw_gui.shortcuts import compose_hover_text as _compose_hover_text_contract_marker  # noqa: F401,E402
from bw_gui.widgets import HoverTooltip as _SharedHoverTooltipContractMarker  # noqa: F401,E402
from datetime import date

from bw_libs.ui_contract.laufkern import aggregate_completion, emit_tracking_artifact
from kursplaner.adapters.bootstrap.wiring import AppDependencies, build_gui_dependencies
from kursplaner.adapters.gui.action_controller import MainWindowActionController
from kursplaner.adapters.gui.column_reorder_controller import MainWindowColumnReorderController
from kursplaner.adapters.gui.editor_controller import MainWindowEditorController
from kursplaner.adapters.gui.grid_renderer import GridRenderer
from kursplaner.adapters.gui.grid_viewport_sync import GridViewportSync, HorizontalViewportSync
from kursplaner.adapters.gui.lesson_context_controller import MainWindowLessonContextController
from kursplaner.adapters.gui.lesson_conversion_controller import MainWindowLessonConversionController
from kursplaner.adapters.gui.overview_controller import MainWindowOverviewController
from kursplaner.adapters.gui.path_bootstrap import ensure_paths_interactive
from kursplaner.adapters.gui.path_settings_controller import MainWindowPathSettingsController
from kursplaner.adapters.gui.screen_builder import ScreenBuilder
from kursplaner.adapters.gui.search_controller import MainWindowSearchController
from kursplaner.adapters.gui.search_state import SearchOverlayState
from kursplaner.adapters.gui.selection_controller import MainWindowSelectionController
from kursplaner.adapters.gui.toolbar_icon_styler import ToolbarIconStyler
from kursplaner.adapters.gui.ui_intent_controller import MainWindowUiIntentController
from kursplaner.adapters.gui.ui_intents import UiIntent
from kursplaner.adapters.gui.ui_state import MainWindowUiState
from kursplaner.adapters.gui.ui_theme import DEFAULT_THEME, normalize_theme_key
from kursplaner.adapters.gui.window_identity import (
    apply_window_icon,
    bring_window_to_front,
    configure_windows_process_identity,
)
from kursplaner.core.config.ui_preferences_store import load_column_visibility_settings, load_course_overview_highlight_days, load_row_filter_settings, load_theme_key, save_theme_key
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.row_display_mode_usecase import RowFilterSettings
from kursplaner.core.usecases.sync_topic_sequence_plans_usecase import TopicSequencePlanView
from kursplaner.adapters.gui.main_window_plan_delegation import KursplanerPlanDelegationMixin  # noqa: E402
from kursplaner.adapters.gui.main_window_row_mode import KursplanerRowModeMixin  # noqa: E402


class KursplanerApp(KursplanerRowModeMixin, KursplanerPlanDelegationMixin, BwBaseWindow):
    """Hauptfenster-Adapter der Anwendung.

    Verantwortlich für UI-Zustand und Delegation an spezialisierte Controller;
    fachliche Entscheidungen liegen in den injizierten Use Cases/Flows.
    """

    def __init__(self, dependencies: AppDependencies | None = None):
        """Initialisiert Hauptfenster, Controller und UI-Grundzustand."""
        self.gui_dependencies = dependencies or build_gui_dependencies()
        persisted_theme = normalize_theme_key(load_theme_key(DEFAULT_THEME))
        self.screen_builder = ScreenBuilder(self)
        cfg = self.gui_dependencies.shell_config
        super().__init__(
            title=cfg.title,
            geometry=cfg.geometry,
            theme_key=persisted_theme,
            min_width=cfg.min_width,
            min_height=cfg.min_height,
        )

    def build_menu(self) -> list:
        """Liefert die Menüstruktur für BwBaseWindow."""
        return [
            section_spec("file", label="Datei", alt="d", items_provider=self.screen_builder._menu_items_file),
            section_spec("edit", label="Bearbeiten", alt="b", items_provider=self.screen_builder._menu_items_edit),
            section_spec("aktion", label="Aktion", alt="k", items_provider=self.screen_builder._menu_items_action),
            section_spec("view", label="Ansicht", alt="a", items_provider=self.screen_builder._menu_items_view),
        ]

    def build_content(self, frame) -> None:
        """Erzeugt alle UI-Komponenten nach Fenster-Setup durch BwBaseWindow."""
        apply_window_icon(self.tk_root)
        self.path_settings_usecase = self.gui_dependencies.path_settings_usecase
        self.new_lesson_form_usecase = self.gui_dependencies.new_lesson_form_usecase
        self.new_lesson_usecase = self.gui_dependencies.new_lesson_usecase

        self.path_values = self.path_settings_usecase.load_values()
        current_paths = self.path_settings_usecase.to_managed_paths(self.path_values)
        self.base_dir_var = ui.StringVar(value=str(current_paths.unterricht_dir))
        self.count_var = ui.StringVar(value="0 Kurspläne")
        self.theme_var = ui.StringVar(value=normalize_theme_key(load_theme_key(DEFAULT_THEME)))
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
        self.sequence_fields_visible_var = ui.BooleanVar(value=True)
        self.topic_sequence_plans: list[TopicSequencePlanView] = []
        # Seit der Viewport-Virtualisierung (Kursplaner Item 4) bedeutet ein
        # Eintrag hier "diese Spannzelle ist gerade materialisiert", NICHT
        # "dieser Sequenzlauf existiert" -- vor der Virtualisierung waren
        # beide Aussagen deckungsgleich (jeder Lauf hatte immer ein Widget),
        # seither nicht mehr. Domain-/Grid-Fragen (z.B. "ueberspannt dieser
        # Lauf Tag X") gehoeren auf `topic_sequence_plans`/Grid-Konfiguration,
        # nicht auf dieses Dict; nur echte Materialisierungs-/UI-Fragen
        # ("hat diese Zelle gerade ein Widget zum Stylen/Fokussieren") duerfen
        # es lesen. S. `GridRenderer._reconcile_sequence_field_mounts()`.
        self.sequence_field_widgets: dict[tuple[str, int], ui.Text] = {}

        self.current_table: PlanTableData | None = None
        self.day_columns: list[DayColumn] = []
        self.day_column_x_positions: dict[int, int] = {}
        self.day_grid_columns: dict[int, int] = {}
        self.lesson_load_errors: dict[str, str] = {}
        self._plan_overview_query = self.gui_dependencies.plan_overview_query
        self.row_display_mode_usecase = self.gui_dependencies.row_display_mode_usecase
        self.update_sequence_goal_field_usecase = self.gui_dependencies.update_sequence_goal_field_usecase
        self.active_row_mode = self.row_display_mode_usecase.MODE_UNTERRICHT
        self.row_mode_buttons: dict[str, ui.Widget] = {}
        self.row_mode_labels: dict[str, str] = {
            item.key: item.label for item in self.row_display_mode_usecase.available_modes()
        }
        self.column_visibility_settings = load_column_visibility_settings()
        self.row_filter_settings: RowFilterSettings = load_row_filter_settings()
        self.row_defs = self.row_display_mode_usecase.row_defs_for_mode(
            self.active_row_mode, self.row_filter_settings
        )
        self.course_overview_highlight_days = load_course_overview_highlight_days()
        self.show_former_courses = False
        self.raw_day_columns: list[DayColumn] = []

        # Seit der Viewport-Virtualisierung (Kursplaner Item 4) bedeutet ein
        # Eintrag hier "diese Zelle ist gerade materialisiert", NICHT "diese
        # logische Zelle existiert" -- vor der Virtualisierung waren beide
        # Aussagen deckungsgleich (jede domain-sichtbare Zelle hatte immer
        # ein Widget), seither nicht mehr. Domain-/Grid-Fragen ("ist dieses
        # Feld an diesem Tag relevant", "wo liegt Grid-Zeile X") gehoeren auf
        # Domain-Daten bzw. Grid-Konfiguration (`grid_rowconfigure`/
        # `day_column_x_positions`/`day_grid_columns`), NIE auf dieses Dict;
        # nur echte Materialisierungs-/UI-Fragen ("hat diese Zelle gerade ein
        # Widget zum Stylen/Fokussieren") duerfen es lesen. S.
        # `GridRenderer._reconcile_column_mounts()`,
        # `MainWindowSelectionController.ensure_row_visible()`.
        self.cell_widgets: dict[tuple[str, int], ui.Text] = {}
        # Ungespeicherter Zellentext, unabhaengig vom Widget gehalten (Kursplaner
        # Item 4, Stufe 4 -- COLD-Eviction via destroy()). Wird nur befuellt, wenn
        # eine Zelle mit vom Domain-Wert abweichendem Text destroy()t wird, und
        # ausschliesslich bei einem erfolgreichen echten Commit (save_cell()
        # durch Fokusverlust) wieder geleert -- niemals durch reines Scrollen.
        self.pending_cell_text: dict[tuple[str, int], str] = {}
        self.header_labels: dict[int, ui.Label] = {}
        self.row_labels: dict[str, ui.Label] = {}
        self.corner_label: ui.Label | None = None
        self.ui_state = MainWindowUiState()
        self.search_state = SearchOverlayState()
        self.selected_day_indices = set()
        self._is_rebuilding_grid = False
        self.is_detail_view = False
        self.viewport_sync = GridViewportSync(self)
        self.viewport_sync_h = HorizontalViewportSync(self)

        self.overview_controller = MainWindowOverviewController(self)
        self.selection_controller = MainWindowSelectionController(self)
        self.search_controller = MainWindowSearchController(self)
        self.editor_controller = MainWindowEditorController(self)
        self.lesson_context_controller = MainWindowLessonContextController(self)
        self.path_settings_controller = MainWindowPathSettingsController(self)
        self.lesson_conversion_controller = MainWindowLessonConversionController(self)
        self.column_reorder_controller = MainWindowColumnReorderController(self)
        self.ui_intent_controller = MainWindowUiIntentController(self)
        self._laufkern_tracking_run_id = "runtime-intents"
        self._laufkern_tracking_sequence = 0
        self._laufkern_tracking_step_ids: dict[str, str] = {}
        self._laufkern_tracking_artifacts = []
        self.toolbar_icon_styler = ToolbarIconStyler(self)

        self.grid_renderer = GridRenderer(self)
        self.action_controller = MainWindowActionController(self)

        self.screen_builder.build_ui(frame)
        self.screen_builder._bind_shortcuts()
        self.screen_builder._apply_theme()
        self.action_controller.refresh_overview()
        self.action_controller.update_action_controls()

    def open_settings(self) -> None:
        """Öffnet den Einstellungen-Dialog."""
        self._handle_ui_intent(UiIntent.OPEN_SETTINGS)

    def apply_theme(self, theme_key: str) -> None:
        """Wechselt Theme und synchronisiert alle programm-spezifischen Flächen."""
        super().apply_theme(theme_key)
        self.theme_var.set(normalize_theme_key(theme_key))
        save_theme_key(normalize_theme_key(theme_key))
        self.screen_builder._apply_theme()
        self._apply_grid_theme()

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
        record_dispatch = getattr(self, "_record_laufkern_intent_dispatch", None)
        if controller is None:
            controller = MainWindowUiIntentController(self)
        try:
            result = controller.handle_intent(intent, **payload)
        except Exception:
            if callable(record_dispatch):
                record_dispatch(intent, success=False)
            raise

        if callable(record_dispatch):
            record_dispatch(intent, success=True)
        return result

    def _laufkern_step_id_for_intent(self, intent: str) -> str:
        """Return stable runtime-tracking step id for one intent during this session."""

        existing = self._laufkern_tracking_step_ids.get(intent)
        if existing is not None:
            return existing

        next_index = len(self._laufkern_tracking_step_ids) + 1
        step_id = f"LK-D-RTC-{next_index:03d}"
        self._laufkern_tracking_step_ids[intent] = step_id
        return step_id

    def _record_laufkern_intent_dispatch(self, intent: str, *, success: bool) -> None:
        """Record runtime intent dispatch result as LaufKern tracking artifact."""

        self._laufkern_tracking_sequence += 1
        artifact = emit_tracking_artifact(
            run_id=self._laufkern_tracking_run_id,
            repo_name="kursplaner",
            step_id=self._laufkern_step_id_for_intent(intent),
            phase="D",
            state="done" if success else "failed",
            sequence=self._laufkern_tracking_sequence,
            mandatory=True,
            producer="laufkern-runtime",
            evidence_ref=intent,
        )
        self._laufkern_tracking_artifacts.append(artifact)

    def _summarize_laufkern_completion(self) -> str:
        """Return compact completion status summary from tracked runtime artifacts."""

        if not self._laufkern_tracking_artifacts:
            return "LK completion n/a"

        summary = aggregate_completion(
            self._laufkern_tracking_artifacts,
            trusted_producers={"laufkern-runtime"},
        )
        return f"LK completion {summary.status} {summary.completed_steps}/{summary.mandatory_steps}"

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

    @staticmethod
    def _widget_has_text_selection(widget) -> bool:
        """Prüft widget-agnostisch, ob aktuell eine Textauswahl aktiv ist."""
        return MainWindowUiIntentController.widget_has_text_selection(widget)

    def _on_theme_changed(self):
        """Reagiert auf Theme-Wechsel und aktualisiert Fenster plus Grid-Darstellung."""
        save_theme_key(normalize_theme_key(self.theme_var.get()))
        self._apply_theme()
        self._apply_grid_theme()

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

    def open_new_course_window(self):
        """Öffnet den Dialog zur Erstellung eines neuen Kurses."""
        self.action_controller.open_new_course_window()

def main():
    """Startet die GUI-Anwendung nach interaktivem Pfad-Bootstrap."""
    configure_windows_process_identity()
    dependencies: AppDependencies = build_gui_dependencies()
    if not ensure_paths_interactive(path_settings_usecase=dependencies.path_settings_usecase):
        return

    def _run_startup_relation_registry_rebuild() -> None:
        """Rebuild file relations once on startup to warm the persistent registry."""
        try:
            managed_paths = dependencies.path_settings_usecase.to_managed_paths(
                dependencies.path_settings_usecase.load_values()
            )
            dependencies.rebuild_file_relation_registry_usecase.execute(managed_paths.unterricht_dir)
        except Exception as exc:
            print(f"Startup relation registry rebuild failed: {exc}")

    def _run_startup_archive_past_lessons() -> None:
        """Verschiebt vergangene Einheitsdateien einmalig beim Start in Alteinheiten/."""
        try:
            managed_paths = dependencies.path_settings_usecase.to_managed_paths(
                dependencies.path_settings_usecase.load_values()
            )
            tables = dependencies.plan_repo.load_plan_tables(managed_paths.unterricht_dir)
            archiver = dependencies.archive_past_lesson_files_usecase
            for table in tables:
                archiver.execute(table)
        except Exception as exc:
            print(f"Startup lesson archival failed: {exc}")

    _run_startup_archive_past_lessons()
    _run_startup_relation_registry_rebuild()

    app = KursplanerApp(dependencies=dependencies)
    apply_window_icon(app.tk_root)
    app.after(60, lambda: bring_window_to_front(app.tk_root))
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
    app.run()

