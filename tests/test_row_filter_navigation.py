from types import SimpleNamespace

from kursplaner.adapters.gui.selection_controller import MainWindowSelectionController
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
    def get(self):
        return "default"


class _ActionControllerSpy:
    def update_action_controls(self):
        pass


class _GridCanvasStub:
    def __init__(self):
        self.full_width = 1200
        self.full_height = 1200
        self.viewport_width = 600
        self.viewport_height = 600
        self._x_start_fraction = 0.0
        self._y_start_fraction = 0.0

    def update_idletasks(self):
        pass

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
        self._x_start_fraction = fraction

    def yview(self):
        span = self.viewport_height / float(self.full_height)
        return (self._y_start_fraction, min(1.0, self._y_start_fraction + span))

    def yview_moveto(self, fraction):
        self._y_start_fraction = fraction


class _ViewportSyncStub:
    def __init__(self, grid_canvas: _GridCanvasStub):
        self._grid_canvas = grid_canvas

    def yview_range(self):
        return self._grid_canvas.yview()

    def yview_moveto(self, fraction):
        self._grid_canvas.yview_moveto(fraction)


class _HorizontalViewportSyncStub:
    def __init__(self, grid_canvas: _GridCanvasStub):
        self._grid_canvas = grid_canvas

    def xview_range(self):
        return self._grid_canvas.xview()

    def xview_moveto(self, fraction):
        self._grid_canvas.xview_moveto(fraction)


class _RowDisplayModeUseCaseStub:
    def __init__(self, editable_cells: set[tuple[str, int]]):
        self._editable_cells = editable_cells

    def is_editable(self, field_key: str, day: DayColumn, settings: RowFilterSettings | None = None) -> bool:
        if (field_key, day.row_index) not in self._editable_cells:
            return False
        if settings is not None and field_key in settings.field_mode_overrides:
            return bool(settings.field_mode_overrides[field_key])
        return True


def _make_app(
    *,
    day_columns: list[DayColumn],
    row_defs: list[tuple[str, str]],
    editable_cells: set[tuple[str, int]],
    row_filter_settings: RowFilterSettings | None = None,
) -> SimpleNamespace:
    ui_state = MainWindowUiState()
    grid_canvas = _GridCanvasStub()
    app = SimpleNamespace(
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
        grid_canvas=grid_canvas,
        grid_window=object(),
        cell_widgets={},
        overview_controller=SimpleNamespace(_next_lesson_column_index=lambda: 0),
    )
    app.viewport_sync = _ViewportSyncStub(grid_canvas)
    app.viewport_sync_h = _HorizontalViewportSyncStub(grid_canvas)
    app._update_row_mode_from_selection = lambda: None
    app._refresh_grid_content = lambda: None
    app._is_holiday_column = lambda _day: False
    return app


def test_vertical_navigation_skips_filter_hidden_fields():
    app = _make_app(
        day_columns=[make_day_column(row_index=0)],
        row_defs=[("Stundenthema", "Thema"), ("Oberthema", "Oberthema"), ("Stundenziel", "Ziel")],
        editable_cells={("Stundenthema", 0), ("Oberthema", 0), ("Stundenziel", 0)},
        row_filter_settings=RowFilterSettings(field_mode_overrides={"Oberthema": frozenset()}),
    )
    controller = MainWindowSelectionController(app)
    controller.set_selected_cell("Stundenthema", 0)

    moved = controller.move_selected_cell_vertical(1)

    assert moved is True
    assert app.ui_state.selected_cell is not None
    assert app.ui_state.selected_cell.field_key == "Stundenziel"


def test_select_first_editable_skips_filter_hidden_fields():
    app = _make_app(
        day_columns=[make_day_column(row_index=0)],
        row_defs=[("Stundenthema", "Thema"), ("Oberthema", "Oberthema"), ("Stundenziel", "Ziel")],
        editable_cells={("Stundenthema", 0), ("Oberthema", 0), ("Stundenziel", 0)},
        row_filter_settings=RowFilterSettings(field_mode_overrides={"Stundenthema": frozenset()}),
    )
    app.selected_day_indices = {0}
    controller = MainWindowSelectionController(app)

    moved = controller.select_first_editable_in_selected_column()

    assert moved is True
    assert app.ui_state.selected_cell is not None
    assert app.ui_state.selected_cell.field_key == "Oberthema"


def test_select_first_editable_returns_false_when_all_editable_fields_are_hidden():
    app = _make_app(
        day_columns=[make_day_column(row_index=0)],
        row_defs=[("Stundenthema", "Thema"), ("Oberthema", "Oberthema")],
        editable_cells={("Stundenthema", 0), ("Oberthema", 0)},
        row_filter_settings=RowFilterSettings(
            field_mode_overrides={"Stundenthema": frozenset(), "Oberthema": frozenset()}
        ),
    )
    app.selected_day_indices = {0}
    controller = MainWindowSelectionController(app)

    moved = controller.select_first_editable_in_selected_column()

    assert moved is False


def test_vertical_navigation_returns_false_when_all_remaining_fields_are_hidden():
    app = _make_app(
        day_columns=[make_day_column(row_index=0)],
        row_defs=[("Stundenthema", "Thema"), ("Oberthema", "Oberthema")],
        editable_cells={("Stundenthema", 0), ("Oberthema", 0)},
        row_filter_settings=RowFilterSettings(field_mode_overrides={"Oberthema": frozenset()}),
    )
    controller = MainWindowSelectionController(app)
    controller.set_selected_cell("Stundenthema", 0)

    moved = controller.move_selected_cell_vertical(1)

    assert moved is False


def test_enter_does_nothing_when_all_editable_fields_hidden():
    """select_first_editable_in_selected_column liefert False → Enter tut nichts."""
    app = _make_app(
        day_columns=[make_day_column(row_index=0)],
        row_defs=[("Stundenthema", "Thema")],
        editable_cells={("Stundenthema", 0)},
        row_filter_settings=RowFilterSettings(field_mode_overrides={"Stundenthema": frozenset()}),
    )
    app.selected_day_indices = {0}
    controller = MainWindowSelectionController(app)

    result = controller.select_first_editable_in_selected_column()

    assert result is False
    assert app.ui_state.selected_cell is None
