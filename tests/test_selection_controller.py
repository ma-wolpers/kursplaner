from types import SimpleNamespace

from kursplaner.adapters.gui.selection_controller import MainWindowSelectionController
from kursplaner.adapters.gui.ui_state import MainWindowUiState


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

    def update_action_controls(self):
        self.update_calls += 1


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


class _CellWidgetStub:
    def __init__(self, *, y: int, height: int):
        self._y = y
        self._height = height

    def winfo_y(self):
        return self._y

    def winfo_height(self):
        return self._height


class _RowDisplayModeUseCaseStub:
    def __init__(self, editable_cells: set[tuple[str, int]]):
        self._editable_cells = set(editable_cells)

    def is_editable(self, field_key: str, day: dict[str, object]) -> bool:
        return (field_key, int(day.get("index", -1))) in self._editable_cells


class _SelectionAppStub(SimpleNamespace):
    def __init__(
        self,
        *,
        day_columns: list[dict[str, object]],
        row_defs: list[tuple[str, str]],
        editable_cells: set[tuple[str, int]],
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
            action_controller=_ActionControllerSpy(),
            grid_canvas=_GridCanvasStub(),
            grid_window=object(),
            cell_widgets={},
            overview_controller=SimpleNamespace(_next_lesson_column_index=lambda: 0),
        )
        self.viewport_sync = _ViewportSyncStub(self.grid_canvas)
        self.refresh_calls = 0

    def _update_row_mode_from_selection(self):
        return None

    def _refresh_grid_content(self):
        self.refresh_calls += 1

    def _is_holiday_column(self, _day: dict[str, object]) -> bool:
        return False


def test_select_first_editable_in_selected_column_skips_non_editable_fields():
    app = _SelectionAppStub(
        day_columns=[{"index": 0, "datum": "2026-03-27"}],
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
        day_columns=[{"index": 0, "datum": "2026-03-27"}],
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
            {"index": 0, "datum": "2026-03-27"},
            {"index": 1, "datum": "2026-03-28"},
            {"index": 2, "datum": "2026-03-29"},
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
        day_columns=[{"index": 0, "datum": "2026-03-27"}],
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
            {"index": 0, "datum": "2026-03-27"},
            {"index": 1, "datum": "2026-03-28"},
            {"index": 2, "datum": "2026-03-29"},
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
            {"index": 0, "datum": "2026-03-27", "inhalt": "[[Thema A]]", "is_cancel": False},
            {"index": 1, "datum": "2026-03-28", "inhalt": "Ferien", "stunden": "0", "is_cancel": False},
            {"index": 2, "datum": "2026-03-29", "inhalt": "[[Thema B]]", "is_cancel": False},
        ],
        row_defs=[("Stundenthema", "Thema")],
        editable_cells={("Stundenthema", 0), ("Stundenthema", 1), ("Stundenthema", 2)},
    )
    app.selected_day_indices = {0}
    controller = MainWindowSelectionController(app)

    moved = controller.move_selection_to_adjacent_occurring(1)

    assert moved is True
    assert app.selected_day_indices == {1}


def test_vertical_navigation_scrolls_selected_cell_into_view():
    app = _SelectionAppStub(
        day_columns=[{"index": 0, "datum": "2026-03-27"}],
        row_defs=[("Stundenthema", "Thema"), ("Kompetenzen", "Kompetenzen")],
        editable_cells={("Stundenthema", 0), ("Kompetenzen", 0)},
    )
    app.cell_widgets[("Stundenthema", 0)] = _CellWidgetStub(y=20, height=80)
    app.cell_widgets[("Kompetenzen", 0)] = _CellWidgetStub(y=740, height=80)
    controller = MainWindowSelectionController(app)
    controller.set_selected_cell("Stundenthema", 0)

    moved = controller.move_selected_cell_vertical(1)

    assert moved is True
    assert app.viewport_sync.last_yview_moveto is not None
    assert app.viewport_sync.last_yview_moveto > 0.0


def test_move_selected_cell_to_edge_scrolls_selected_cell_into_view():
    app = _SelectionAppStub(
        day_columns=[{"index": 0, "datum": "2026-03-27"}],
        row_defs=[("Stundenthema", "Thema"), ("Kompetenzen", "Kompetenzen")],
        editable_cells={("Stundenthema", 0), ("Kompetenzen", 0)},
    )
    app.cell_widgets[("Stundenthema", 0)] = _CellWidgetStub(y=20, height=80)
    app.cell_widgets[("Kompetenzen", 0)] = _CellWidgetStub(y=740, height=80)
    controller = MainWindowSelectionController(app)
    controller.set_selected_cell("Stundenthema", 0)

    moved = controller.move_selected_cell_to_edge(to_end=True)

    assert moved is True
    assert app.viewport_sync.last_yview_moveto is not None
    assert app.viewport_sync.last_yview_moveto > 0.0


def test_select_first_editable_in_selected_column_scrolls_into_view():
    app = _SelectionAppStub(
        day_columns=[{"index": 0, "datum": "2026-03-27"}],
        row_defs=[("inhalt", "Inhalt"), ("Stundenthema", "Thema")],
        editable_cells={("Stundenthema", 0)},
    )
    app.selected_day_indices = {0}
    app.cell_widgets[("Stundenthema", 0)] = _CellWidgetStub(y=760, height=80)
    controller = MainWindowSelectionController(app)

    moved = controller.select_first_editable_in_selected_column()

    assert moved is True
    assert app.viewport_sync.last_yview_moveto is not None
    assert app.viewport_sync.last_yview_moveto > 0.0


def test_set_selected_cell_does_not_scroll_when_cell_already_visible():
    app = _SelectionAppStub(
        day_columns=[{"index": 0, "datum": "2026-03-27"}],
        row_defs=[("Stundenthema", "Thema")],
        editable_cells={("Stundenthema", 0)},
    )
    app.cell_widgets[("Stundenthema", 0)] = _CellWidgetStub(y=60, height=80)
    controller = MainWindowSelectionController(app)

    moved = controller.set_selected_cell("Stundenthema", 0, ensure_visible=True)

    assert moved is True
    assert app.viewport_sync.last_yview_moveto == 0.0
