import re
from types import SimpleNamespace

from bw_gui.runtime import ui

from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.adapters.gui.search_controller import MainWindowSearchController
from kursplaner.adapters.gui.search_state import SearchOverlayState
from kursplaner.adapters.gui.ui_intent_controller import MainWindowUiIntentController
from kursplaner.adapters.gui.ui_intents import UiIntent
from kursplaner.adapters.gui.ui_state import MainWindowUiState
from tests.day_column_factory import make_day_column


class _FakeCellWidget:
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


class _SelectionControllerSpy:
    def __init__(self, *, select_first_editable_result: bool = True):
        self.select_first_editable_result = select_first_editable_result
        self.clear_selected_cell_calls = 0
        self.single_column_selection_calls: list[tuple[int, bool]] = []

    def select_first_editable_in_selected_column(self) -> bool:
        return self.select_first_editable_result

    def clear_selected_cell(self):
        self.clear_selected_cell_calls += 1

    def set_single_column_selection(self, day_index: int, *, ensure_visible: bool = False):
        self.single_column_selection_calls.append((day_index, ensure_visible))


class _OverviewControllerSpy:
    def __init__(self):
        self.close_detail_view_calls = 0
        self.load_selected_table_calls: list[object] = []

    def close_detail_view(self):
        self.close_detail_view_calls += 1

    def load_selected_table(self, event=None):
        self.load_selected_table_calls.append(event)


class _GridCanvasSpy:
    def __init__(self):
        self.focus_set_calls = 0

    def focus_set(self):
        self.focus_set_calls += 1


class _SearchOverlayViewSpy:
    def __init__(self):
        self.show_calls = 0
        self.hide_calls = 0

    def show(self):
        self.show_calls += 1

    def hide(self):
        self.hide_calls += 1


def _make_app(*, is_detail_view: bool, selection_level: str, day_columns=None, focused=None):
    ui_state = MainWindowUiState()
    ui_state.selection_level = selection_level
    app = SimpleNamespace(
        is_detail_view=is_detail_view,
        ui_state=ui_state,
        search_state=SearchOverlayState(),
        selection_controller=_SelectionControllerSpy(),
        overview_controller=_OverviewControllerSpy(),
        grid_canvas=_GridCanvasSpy(),
        search_overlay_view=_SearchOverlayViewSpy(),
        cell_widgets={},
        day_columns=day_columns if day_columns is not None else [],
        focus_get=lambda: focused,
    )
    app.search_controller = MainWindowSearchController(app)
    return app


def _make_controller(app) -> MainWindowUiIntentController:
    return MainWindowUiIntentController(app)


def test_course_layer_enter_confirms_selection():
    app = _make_app(is_detail_view=False, selection_level=MainWindowUiState.SELECTION_LEVEL_COURSE)
    controller = _make_controller(app)

    result = controller.intent_grid_enter()

    assert result == "break"
    assert app.overview_controller.load_selected_table_calls == [None]


def test_course_layer_escape_is_noop_without_text_focus():
    app = _make_app(is_detail_view=False, selection_level=MainWindowUiState.SELECTION_LEVEL_COURSE, focused=None)
    controller = _make_controller(app)

    result = controller.intent_escape()

    assert result is None
    assert app.grid_canvas.focus_set_calls == 0


def test_course_layer_escape_refocuses_grid_when_focus_is_text_widget(tk_root):
    stray_text = ui.Text(tk_root)
    app = _make_app(is_detail_view=False, selection_level=MainWindowUiState.SELECTION_LEVEL_COURSE, focused=stray_text)
    controller = _make_controller(app)

    result = controller.intent_escape()

    assert result == "break"
    assert app.grid_canvas.focus_set_calls == 1


def test_column_layer_enter_focuses_first_editable_cell():
    app = _make_app(is_detail_view=True, selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN)
    controller = _make_controller(app)

    result = controller.intent_grid_enter()

    assert result == "break"


def test_column_layer_enter_is_noop_when_nothing_editable():
    app = _make_app(is_detail_view=True, selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN)
    app.selection_controller.select_first_editable_result = False
    controller = _make_controller(app)

    result = controller.intent_grid_enter()

    assert result is None


def test_column_layer_escape_closes_detail_view():
    app = _make_app(is_detail_view=True, selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN)
    controller = _make_controller(app)

    result = controller.intent_escape()

    assert result == "break"
    assert app.overview_controller.close_detail_view_calls == 1


def test_edge_case_detail_view_true_with_course_level_falls_back_to_column_escape():
    """Der inkonsistente Zustand `is_detail_view=True` + `selection_level=COURSE`
    landet über `top()`s "otherwise"-Zweig bei `_ColumnLayer`, exakt wie der
    frühere Fallback am Ende von `intent_escape()`."""
    app = _make_app(is_detail_view=True, selection_level=MainWindowUiState.SELECTION_LEVEL_COURSE)
    controller = _make_controller(app)

    result = controller.intent_escape()

    assert result == "break"
    assert app.overview_controller.close_detail_view_calls == 1


def test_cell_layer_enter_focuses_widget():
    app = _make_app(is_detail_view=True, selection_level=MainWindowUiState.SELECTION_LEVEL_CELL)
    app.ui_state.set_selected_cell("Stundenthema", 0)
    widget = _FakeCellWidget()
    app.cell_widgets[("Stundenthema", 0)] = widget
    controller = _make_controller(app)

    result = controller.intent_grid_enter()

    assert result == "break"
    assert widget.focus_set_calls == 1


def test_cell_layer_escape_clears_cell_and_returns_to_column():
    app = _make_app(is_detail_view=True, selection_level=MainWindowUiState.SELECTION_LEVEL_CELL)
    app.ui_state.set_selected_cell("Stundenthema", 0)
    controller = _make_controller(app)

    result = controller.intent_escape()

    assert result == "break"
    assert app.selection_controller.clear_selected_cell_calls == 1
    assert app.ui_state.selection_level == MainWindowUiState.SELECTION_LEVEL_COLUMN
    assert app.grid_canvas.focus_set_calls == 1


def test_edit_layer_enter_is_noop_falls_through_to_tk_default():
    app = _make_app(is_detail_view=True, selection_level=MainWindowUiState.SELECTION_LEVEL_EDIT)
    controller = _make_controller(app)

    result = controller.intent_grid_enter()

    assert result is None


def test_edit_layer_escape_leaves_edit_mode():
    app = _make_app(is_detail_view=True, selection_level=MainWindowUiState.SELECTION_LEVEL_EDIT)
    controller = _make_controller(app)
    calls: list[dict] = []
    controller._leave_edit_mode_to_cell = lambda **kwargs: calls.append(kwargs) or True

    result = controller.intent_escape()

    assert result == "break"
    assert calls == [{"set_grid_focus": True}]


def test_search_layer_enter_calls_find_next_and_wins_over_column_level():
    app = _make_app(
        is_detail_view=True,
        selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN,
        day_columns=[make_day_column(row_index=0, inhalt="Vektoren"), make_day_column(row_index=1, inhalt="Sonstiges")],
    )
    app.search_state.is_active = True
    app.search_controller.update_query("Vektor", re.compile("Vektor"))
    controller = _make_controller(app)

    result = controller.intent_grid_enter()

    assert result == "break"
    assert app.selection_controller.single_column_selection_calls == [(0, True)]


def test_search_layer_find_previous_dispatches_through_handle_intent():
    app = _make_app(
        is_detail_view=True,
        selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN,
        day_columns=[make_day_column(row_index=0, inhalt="Vektoren"), make_day_column(row_index=1, inhalt="Vektorfeld")],
    )
    app.search_state.is_active = True
    app.search_controller.update_query("Vektor", re.compile("Vektor"))
    controller = _make_controller(app)
    controller.intent_grid_enter()  # springt zu Treffer 0

    result = controller.handle_intent(UiIntent.SHORTCUT_FIND_PREVIOUS)

    assert result == "break"
    assert app.selection_controller.single_column_selection_calls[-1] == (1, True)


def test_search_layer_escape_closes_search_without_touching_selection():
    app = _make_app(is_detail_view=True, selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN)
    app.search_state.is_active = True
    controller = _make_controller(app)

    result = controller.intent_escape()

    assert result == "break"
    assert app.search_state.is_active is False
    assert app.search_overlay_view.hide_calls == 1
    assert app.selection_controller.clear_selected_cell_calls == 0
    assert app.overview_controller.close_detail_view_calls == 0
    assert app.ui_state.selection_level == MainWindowUiState.SELECTION_LEVEL_COLUMN


def test_escape_falls_back_to_column_after_search_closes():
    app = _make_app(is_detail_view=True, selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN)
    app.search_state.is_active = True
    controller = _make_controller(app)

    controller.intent_escape()  # 1. Escape: schliesst nur die Suche
    result = controller.intent_escape()  # 2. Escape: greift wieder die unveraenderte Basis-Hierarchie

    assert result == "break"
    assert app.overview_controller.close_detail_view_calls == 1


def test_non_search_layers_find_previous_is_a_noop():
    app = _make_app(is_detail_view=True, selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN)
    controller = _make_controller(app)

    result = controller.handle_intent(UiIntent.SHORTCUT_FIND_PREVIOUS)

    assert result is None
    assert app.selection_controller.single_column_selection_calls == []


def test_escape_popup_takes_priority_over_active_search(monkeypatch):
    app = _make_app(is_detail_view=True, selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN)
    app.search_state.is_active = True
    monkeypatch.setattr(ScrollablePopupWindow, "has_active_popup", classmethod(lambda cls: True))
    monkeypatch.setattr(ScrollablePopupWindow, "close_active_popup", classmethod(lambda cls: True))
    controller = _make_controller(app)

    result = controller.intent_escape()

    assert result == "break"
    assert app.search_state.is_active is True  # Suche wurde NICHT angefasst -- Popup gewann
