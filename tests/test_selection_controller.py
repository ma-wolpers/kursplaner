from types import SimpleNamespace

from kursplaner.adapters.gui.selection_controller import MainWindowSelectionController
from kursplaner.adapters.gui.ui_intent_controller import MainWindowUiIntentController
from kursplaner.adapters.gui.ui_state import MainWindowUiState
from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.usecases.row_display_mode_usecase import RowFilterSettings
from tests.day_column_factory import make_day_column


class _Var:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = str(value)


class _ThemeVar:
    def __init__(self, value: str = "default"):
        self._value = value

    def get(self):
        return self._value


class _ActionControllerSpy:
    def __init__(self):
        self.update_calls = 0
        self.schedule_calls = 0

    def update_action_controls(self):
        self.update_calls += 1

    def schedule_action_controls_update(self):
        self.schedule_calls += 1


class _GridRendererStub:
    def __init__(self):
        self.style_calls: list[tuple[str, int]] = []
        self.row_index_by_field: dict[str, int] = {}

    def _apply_cell_selection_style(self, _widget, *, field_key: str, day_index: int):
        self.style_calls.append((field_key, day_index))

    def _row_index_for_field(self, field_key: str) -> int | None:
        return self.row_index_by_field.get(field_key)


class _GridInnerStub:
    """Stub für `grid_inner`: `grid_bbox(column, row)` liefert Zeilen-Geometrie

    rein aus Konfiguration -- unabhängig davon, ob für diese Zeile gerade ein
    Zellen-Widget existiert (s. `ensure_row_visible()`, das genau das nicht
    mehr voraussetzt)."""

    def __init__(self):
        self.bbox_by_row: dict[int, tuple[int, int, int, int]] = {}

    def grid_bbox(self, _column, row_idx):
        return self.bbox_by_row.get(row_idx)


class _GridCanvasStub:
    def __init__(self):
        self.full_width = 1200
        self.full_height = 1200
        self.viewport_width = 600
        self.viewport_height = 300
        self._x_start_fraction = 0.0
        self._y_start_fraction = 0.0
        self.last_xview_moveto = None
        self.last_yview_moveto = None

    def update_idletasks(self):
        return None

    def bbox(self, _window):
        return (0, 0, self.full_width, self.full_height)

    def winfo_width(self):
        return self.viewport_width

    def winfo_height(self):
        return self.viewport_height

    def xview(self):
        span = self.viewport_width / float(self.full_width)
        return (self._x_start_fraction, min(1.0, self._x_start_fraction + span))

    def xview_moveto(self, fraction):
        self.last_xview_moveto = fraction
        self._x_start_fraction = fraction
        return None

    def yview(self):
        span = self.viewport_height / float(self.full_height)
        return (self._y_start_fraction, min(1.0, self._y_start_fraction + span))

    def yview_moveto(self, fraction):
        self.last_yview_moveto = fraction
        self._y_start_fraction = fraction
        return None


class _ViewportSyncStub:
    def __init__(self, grid_canvas: _GridCanvasStub):
        self._grid_canvas = grid_canvas
        self.last_yview_moveto = None

    def yview_range(self):
        return self._grid_canvas.yview()

    def yview_moveto(self, fraction):
        self.last_yview_moveto = fraction
        self._grid_canvas.yview_moveto(fraction)


class _FakeCellWidget:
    """Steht für ein echtes, gerade materialisiertes Zellen-Widget -- trackt

    nur, was `intent_grid_enter()` darauf aufruft (`focus_set`/`mark_set`/`see`)."""

    def __init__(self):
        self.focus_set_calls = 0
        self.mark_set_calls: list[tuple] = []
        self.see_calls: list[tuple] = []

    def focus_set(self):
        self.focus_set_calls += 1

    def mark_set(self, *args):
        self.mark_set_calls.append(args)

    def see(self, *args):
        self.see_calls.append(args)


class _HorizontalViewportSyncStub:
    def __init__(self, grid_canvas: _GridCanvasStub, app=None):
        self._grid_canvas = grid_canvas
        self.last_xview_moveto = None
        self.flush_calls = 0
        self._app = app

    def xview_range(self):
        return self._grid_canvas.xview()

    def xview_moveto(self, fraction):
        self.last_xview_moveto = fraction
        self._grid_canvas.xview_moveto(fraction)

    def flush_pending_reconciliation(self):
        """Stub der realen synchronen Reconciliation: materialisiert die

        aktuell selektierte Zelle in `cell_widgets` -- exakt die Garantie,
        auf die `set_selected_cell(..., ensure_visible=True)` sich verlässt
        (s. Kommentar dort)."""
        self.flush_calls += 1
        if self._app is None:
            return
        selected = self._app.ui_state.selected_cell
        if selected is None:
            return
        key = (selected.field_key, selected.day_index)
        if key not in self._app.cell_widgets:
            self._app.cell_widgets[key] = _FakeCellWidget()


class _RowDisplayModeUseCaseStub:
    def __init__(self, editable_cells: set[tuple[str, int]]):
        self._editable_cells = set(editable_cells)

    def is_editable(self, field_key: str, day: DayColumn, _settings: RowFilterSettings | None = None) -> bool:
        return (field_key, day.row_index) in self._editable_cells


class _SelectionAppStub(SimpleNamespace):
    def __init__(
        self,
        *,
        day_columns: list[DayColumn],
        row_defs: list[tuple[str, str]],
        editable_cells: set[tuple[str, int]],
        row_filter_settings: RowFilterSettings | None = None,
    ):
        ui_state = MainWindowUiState()
        super().__init__(
            ui_state=ui_state,
            day_columns=day_columns,
            row_defs=row_defs,
            day_column_width=260,
            selected_column_var=_Var(),
            theme_var=_ThemeVar(),
            header_labels={},
            selected_day_indices=set(),
            row_display_mode_usecase=_RowDisplayModeUseCaseStub(editable_cells),
            row_filter_settings=row_filter_settings if row_filter_settings is not None else RowFilterSettings(),
            action_controller=_ActionControllerSpy(),
            grid_canvas=_GridCanvasStub(),
            grid_window=object(),
            grid_renderer=_GridRendererStub(),
            grid_inner=_GridInnerStub(),
            cell_widgets={},
            _is_rebuilding_grid=False,
            overview_controller=SimpleNamespace(_next_lesson_column_index=lambda: 0),
        )
        self.viewport_sync = _ViewportSyncStub(self.grid_canvas)
        self.viewport_sync_h = _HorizontalViewportSyncStub(self.grid_canvas, app=self)
        self.refresh_calls = 0

    def _update_row_mode_from_selection(self):
        return None

    def _refresh_grid_content(self):
        self.refresh_calls += 1

    def _is_holiday_column(self, _day: DayColumn) -> bool:
        return False


def test_select_first_editable_in_selected_column_skips_non_editable_fields():
    app = _SelectionAppStub(
        day_columns=[make_day_column(row_index=0, datum="2026-03-27")],
        row_defs=[("inhalt", "Inhalt"), ("stunden", "Wie lange"), ("Stundenthema", "Thema")],
        editable_cells={("Stundenthema", 0)},
    )
    app.selected_day_indices = {0}
    controller = MainWindowSelectionController(app)

    moved = controller.select_first_editable_in_selected_column()

    assert moved is True
    assert app.ui_state.selected_cell is not None
    assert app.ui_state.selected_cell.field_key == "Stundenthema"
    assert app.ui_state.selected_cell.day_index == 0
    assert app.ui_state.selection_level == app.ui_state.SELECTION_LEVEL_CELL


def test_vertical_cell_navigation_skips_non_editable_rows():
    app = _SelectionAppStub(
        day_columns=[make_day_column(row_index=0, datum="2026-03-27")],
        row_defs=[("inhalt", "Inhalt"), ("Stundenthema", "Thema"), ("Kompetenzen", "Kompetenzen")],
        editable_cells={("Stundenthema", 0), ("Kompetenzen", 0)},
    )
    controller = MainWindowSelectionController(app)
    controller.set_selected_cell("Stundenthema", 0)

    moved = controller.move_selected_cell_vertical(1)

    assert moved is True
    assert app.ui_state.selected_cell is not None
    assert app.ui_state.selected_cell.field_key == "Kompetenzen"


def test_horizontal_cell_navigation_skips_non_matching_columns():
    app = _SelectionAppStub(
        day_columns=[
            make_day_column(row_index=0, datum="2026-03-27"),
            make_day_column(row_index=1, datum="2026-03-28"),
            make_day_column(row_index=2, datum="2026-03-29"),
        ],
        row_defs=[("Stundenthema", "Thema")],
        editable_cells={("Stundenthema", 0), ("Stundenthema", 2)},
    )
    controller = MainWindowSelectionController(app)
    controller.set_selected_cell("Stundenthema", 0)

    moved = controller.move_selected_cell_horizontal(1)

    assert moved is True
    assert app.ui_state.selected_cell is not None
    assert app.ui_state.selected_cell.day_index == 2


def test_move_selected_cell_to_edge_selects_first_and_last_editable_field():
    app = _SelectionAppStub(
        day_columns=[make_day_column(row_index=0, datum="2026-03-27")],
        row_defs=[("inhalt", "Inhalt"), ("Stundenthema", "Thema"), ("Kompetenzen", "Kompetenzen")],
        editable_cells={("Stundenthema", 0), ("Kompetenzen", 0)},
    )
    controller = MainWindowSelectionController(app)
    controller.set_selected_cell("Kompetenzen", 0)

    moved_top = controller.move_selected_cell_to_edge(to_end=False)
    top_field = app.ui_state.selected_cell.field_key if app.ui_state.selected_cell is not None else ""
    moved_bottom = controller.move_selected_cell_to_edge(to_end=True)
    bottom_field = app.ui_state.selected_cell.field_key if app.ui_state.selected_cell is not None else ""

    assert moved_top is True
    assert top_field == "Stundenthema"
    assert moved_bottom is True
    assert bottom_field == "Kompetenzen"


def test_set_edge_column_selection_selects_first_and_last_column():
    app = _SelectionAppStub(
        day_columns=[
            make_day_column(row_index=0, datum="2026-03-27"),
            make_day_column(row_index=1, datum="2026-03-28"),
            make_day_column(row_index=2, datum="2026-03-29"),
        ],
        row_defs=[("Stundenthema", "Thema")],
        editable_cells={("Stundenthema", 0), ("Stundenthema", 1), ("Stundenthema", 2)},
    )
    controller = MainWindowSelectionController(app)

    first = controller.set_edge_column_selection(to_end=False)
    last = controller.set_edge_column_selection(to_end=True)

    assert first is True
    assert last is True
    assert app.selected_day_indices == {2}


def test_move_selection_to_adjacent_occurring_does_not_skip_non_cancel_holiday_column():
    app = _SelectionAppStub(
        day_columns=[
            make_day_column(row_index=0, datum="2026-03-27", inhalt="[[Thema A]]"),
            make_day_column(row_index=1, datum="2026-03-28", inhalt="Ferien"),
            make_day_column(row_index=2, datum="2026-03-29", inhalt="[[Thema B]]"),
        ],
        row_defs=[("Stundenthema", "Thema")],
        editable_cells={("Stundenthema", 0), ("Stundenthema", 1), ("Stundenthema", 2)},
    )
    app.selected_day_indices = {0}
    controller = MainWindowSelectionController(app)

    moved = controller.move_selection_to_adjacent_occurring(1)

    assert moved is True
    assert app.selected_day_indices == {1}


def test_select_unit_at_offset_from_next_zero_selects_the_anchor_itself():
    app = _SelectionAppStub(
        day_columns=[
            make_day_column(row_index=0, datum="2026-03-27"),
            make_day_column(row_index=1, datum="2026-03-28"),
            make_day_column(row_index=2, datum="2026-03-29"),
        ],
        row_defs=[("Stundenthema", "Thema")],
        editable_cells={("Stundenthema", 0), ("Stundenthema", 1), ("Stundenthema", 2)},
    )
    app.overview_controller = SimpleNamespace(_next_lesson_column_index=lambda: 1)
    controller = MainWindowSelectionController(app)

    selected = controller.select_unit_at_offset_from_next(0)

    assert selected is True
    assert app.selected_day_indices == {1}


def test_select_unit_at_offset_from_next_skips_cancelled_columns():
    app = _SelectionAppStub(
        day_columns=[
            make_day_column(row_index=0, datum="2026-03-27"),  # Anker (offset 0)
            make_day_column(row_index=1, datum="2026-03-28", thema_ausfall="X Grund"),  # uebersprungen
            make_day_column(row_index=2, datum="2026-03-29"),  # offset 1
            make_day_column(row_index=3, datum="2026-03-30"),  # offset 2
        ],
        row_defs=[("Stundenthema", "Thema")],
        editable_cells={("Stundenthema", idx) for idx in range(4)},
    )
    app.overview_controller = SimpleNamespace(_next_lesson_column_index=lambda: 0)
    controller = MainWindowSelectionController(app)

    selected = controller.select_unit_at_offset_from_next(2)

    assert selected is True
    assert app.selected_day_indices == {3}


def test_select_unit_at_offset_from_next_is_noop_when_offset_exceeds_available_columns():
    app = _SelectionAppStub(
        day_columns=[
            make_day_column(row_index=0, datum="2026-03-27"),
            make_day_column(row_index=1, datum="2026-03-28"),
        ],
        row_defs=[("Stundenthema", "Thema")],
        editable_cells={("Stundenthema", 0), ("Stundenthema", 1)},
    )
    app.overview_controller = SimpleNamespace(_next_lesson_column_index=lambda: 0)
    app.selected_day_indices = {1}
    controller = MainWindowSelectionController(app)

    selected = controller.select_unit_at_offset_from_next(5)

    assert selected is False
    assert app.selected_day_indices == {1}  # unveraendert, kein Wrap-around


def test_select_unit_at_offset_from_next_is_noop_when_no_next_unit_exists():
    app = _SelectionAppStub(
        day_columns=[make_day_column(row_index=0, datum="2026-03-27")],
        row_defs=[("Stundenthema", "Thema")],
        editable_cells={("Stundenthema", 0)},
    )
    app.overview_controller = SimpleNamespace(_next_lesson_column_index=lambda: None)
    controller = MainWindowSelectionController(app)

    selected = controller.select_unit_at_offset_from_next(0)

    assert selected is False


def test_vertical_navigation_scrolls_selected_cell_into_view():
    app = _SelectionAppStub(
        day_columns=[make_day_column(row_index=0, datum="2026-03-27")],
        row_defs=[("Stundenthema", "Thema"), ("Kompetenzen", "Kompetenzen")],
        editable_cells={("Stundenthema", 0), ("Kompetenzen", 0)},
    )
    app.grid_renderer.row_index_by_field.update({"Stundenthema": 0, "Kompetenzen": 1})
    app.grid_inner.bbox_by_row.update({0: (0, 20, 100, 80), 1: (0, 740, 100, 80)})
    controller = MainWindowSelectionController(app)
    controller.set_selected_cell("Stundenthema", 0)

    moved = controller.move_selected_cell_vertical(1)

    assert moved is True
    assert app.viewport_sync.last_yview_moveto is not None
    assert app.viewport_sync.last_yview_moveto > 0.0


def test_move_selected_cell_to_edge_scrolls_selected_cell_into_view():
    app = _SelectionAppStub(
        day_columns=[make_day_column(row_index=0, datum="2026-03-27")],
        row_defs=[("Stundenthema", "Thema"), ("Kompetenzen", "Kompetenzen")],
        editable_cells={("Stundenthema", 0), ("Kompetenzen", 0)},
    )
    app.grid_renderer.row_index_by_field.update({"Stundenthema": 0, "Kompetenzen": 1})
    app.grid_inner.bbox_by_row.update({0: (0, 20, 100, 80), 1: (0, 740, 100, 80)})
    controller = MainWindowSelectionController(app)
    controller.set_selected_cell("Stundenthema", 0)

    moved = controller.move_selected_cell_to_edge(to_end=True)

    assert moved is True
    assert app.viewport_sync.last_yview_moveto is not None
    assert app.viewport_sync.last_yview_moveto > 0.0


def test_select_first_editable_in_selected_column_scrolls_into_view():
    app = _SelectionAppStub(
        day_columns=[make_day_column(row_index=0, datum="2026-03-27")],
        row_defs=[("inhalt", "Inhalt"), ("Stundenthema", "Thema")],
        editable_cells={("Stundenthema", 0)},
    )
    app.selected_day_indices = {0}
    app.grid_renderer.row_index_by_field["Stundenthema"] = 0
    app.grid_inner.bbox_by_row[0] = (0, 760, 100, 80)
    controller = MainWindowSelectionController(app)

    moved = controller.select_first_editable_in_selected_column()

    assert moved is True
    assert app.viewport_sync.last_yview_moveto is not None
    assert app.viewport_sync.last_yview_moveto > 0.0


def test_set_selected_cell_does_not_scroll_when_cell_already_visible():
    app = _SelectionAppStub(
        day_columns=[make_day_column(row_index=0, datum="2026-03-27")],
        row_defs=[("Stundenthema", "Thema")],
        editable_cells={("Stundenthema", 0)},
    )
    app.grid_renderer.row_index_by_field["Stundenthema"] = 0
    app.grid_inner.bbox_by_row[0] = (0, 60, 100, 80)
    controller = MainWindowSelectionController(app)

    moved = controller.set_selected_cell("Stundenthema", 0, ensure_visible=True)

    assert moved is True
    assert app.viewport_sync.last_yview_moveto == 0.0


def test_ensure_row_visible_computes_target_from_grid_bbox_without_materialized_widget():
    """`ensure_row_visible()` beantwortet "wo liegt Zeile X" rein aus dem

    Grid (`grid_bbox()`), nie aus einem Zellen-Widget: die Zielzelle bleibt
    hier bewusst COLD (kein Eintrag in `cell_widgets`) und `ensure_row_
    visible()` materialisiert selbst auch nichts -- diese Verantwortung
    liegt bei `set_selected_cell()` (Fix B), nicht hier (Fix A)."""
    app = _SelectionAppStub(
        day_columns=[make_day_column(row_index=0, datum="2026-03-27")],
        row_defs=[("Stundenthema", "Thema"), ("Kompetenzen", "Kompetenzen")],
        editable_cells={("Stundenthema", 0), ("Kompetenzen", 0)},
    )
    app.grid_renderer.row_index_by_field.update({"Stundenthema": 0, "Kompetenzen": 1})
    app.grid_inner.bbox_by_row.update({0: (0, 20, 100, 80), 1: (0, 740, 100, 80)})
    controller = MainWindowSelectionController(app)
    assert ("Kompetenzen", 0) not in app.cell_widgets

    controller.ensure_row_visible("Kompetenzen", 0)

    assert ("Kompetenzen", 0) not in app.cell_widgets
    assert app.viewport_sync.last_yview_moveto is not None
    assert app.viewport_sync.last_yview_moveto > 0.0


def test_set_selected_cell_ensure_visible_materializes_previously_cold_cell():
    """Invariante: kehrt `set_selected_cell(..., ensure_visible=True)`

    zurueck, ist die Zielzelle synchron materialisiert -- geprueft am
    tatsaechlichen Zustand (`cell_widgets`-Eintrag), nicht nur behauptet."""
    app = _SelectionAppStub(
        day_columns=[make_day_column(row_index=0, datum="2026-03-27")],
        row_defs=[("Stundenthema", "Thema")],
        editable_cells={("Stundenthema", 0)},
    )
    assert ("Stundenthema", 0) not in app.cell_widgets
    controller = MainWindowSelectionController(app)

    moved = controller.set_selected_cell("Stundenthema", 0, ensure_visible=True)

    assert moved is True
    assert app.viewport_sync_h.flush_calls == 1
    assert ("Stundenthema", 0) in app.cell_widgets


def test_set_selected_cell_ensure_visible_false_does_not_flush_reconciliation():
    """Normales Scrollen (kein ensure_visible) bleibt gedebouncet --

    `flush_pending_reconciliation()` ist ausschliesslich fuer die diskrete
    ensure_visible=True-Aktion reserviert, kein genereller Hotpath-Aufruf."""
    app = _SelectionAppStub(
        day_columns=[make_day_column(row_index=0, datum="2026-03-27")],
        row_defs=[("Stundenthema", "Thema")],
        editable_cells={("Stundenthema", 0)},
    )
    controller = MainWindowSelectionController(app)

    moved = controller.set_selected_cell("Stundenthema", 0, ensure_visible=False)

    assert moved is True
    assert app.viewport_sync_h.flush_calls == 0


def test_intent_grid_enter_focuses_freshly_materialized_cell_after_navigation():
    """End-zu-Ende-Nachweis der Kette #1 -> #2 -> #5 aus dem Nachaudit: eine

    per Tastatursprung frisch selektierte, zuvor COLD-e Zelle ist nach
    `set_selected_cell(..., ensure_visible=True)` materialisiert, sodass ein
    direkt anschliessendes Enter sie sofort fokussiert statt No-op zu sein.
    `intent_grid_enter()` selbst bleibt dabei frei von Virtualisierungswissen
    -- es liest nur `cell_widgets`, materialisiert nichts selbst."""
    app = _SelectionAppStub(
        day_columns=[make_day_column(row_index=0, datum="2026-03-27")],
        row_defs=[("Stundenthema", "Thema")],
        editable_cells={("Stundenthema", 0)},
    )
    app.is_detail_view = True
    app.focus_get = lambda: None
    controller = MainWindowSelectionController(app)
    app.selection_controller = controller
    assert ("Stundenthema", 0) not in app.cell_widgets

    moved = controller.set_selected_cell("Stundenthema", 0, ensure_visible=True)
    assert moved is True
    assert ("Stundenthema", 0) in app.cell_widgets

    intent_controller = MainWindowUiIntentController(app)
    result = intent_controller.intent_grid_enter()

    widget = app.cell_widgets[("Stundenthema", 0)]
    assert result == "break"
    assert widget.focus_set_calls == 1


def test_ensure_visible_selection_sequence_never_touches_persistence():
    """Strukturell erzwungen (wie die bestehenden COLD-Eviction-Tests): der

    App-Stub hat kein `editor_controller`, `save_cell` oder
    `save_sequence_field` -- jede Beruehrung wuerde sofort mit
    AttributeError crashen. Scrollen/Sichtbarkeitswechsel (inkl. des
    synchronen Flushs) darf nie einen Save ausloesen."""
    app = _SelectionAppStub(
        day_columns=[make_day_column(row_index=0, datum="2026-03-27")],
        row_defs=[("Stundenthema", "Thema"), ("Kompetenzen", "Kompetenzen")],
        editable_cells={("Stundenthema", 0), ("Kompetenzen", 0)},
    )
    assert not hasattr(app, "editor_controller")
    assert not hasattr(app, "save_cell")
    assert not hasattr(app, "save_sequence_field")
    app.grid_renderer.row_index_by_field.update({"Stundenthema": 0, "Kompetenzen": 1})
    app.grid_inner.bbox_by_row.update({0: (0, 20, 100, 80), 1: (0, 740, 100, 80)})
    controller = MainWindowSelectionController(app)

    controller.set_selected_cell("Stundenthema", 0, ensure_visible=True)
    controller.move_selected_cell_vertical(1)
    controller.ensure_row_visible("Kompetenzen", 0)

    assert app.viewport_sync_h.flush_calls >= 1
    assert app.ui_state.selected_cell is not None
    assert app.ui_state.selected_cell.field_key == "Kompetenzen"
