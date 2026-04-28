from types import SimpleNamespace

import kursplaner.adapters.gui.ui_intent_controller as ui_intent_controller
from kursplaner.adapters.gui.main_window import KursplanerApp
from kursplaner.adapters.gui.ui_intents import UiIntent
from kursplaner.adapters.gui.ui_state import MainWindowUiState


class _ActionControllerSpy:
    def __init__(self):
        self.calls: list[str] = []

    def open_settings_window(self):
        self.calls.append("open_settings_window")

    def rebuild_lesson_index(self):
        self.calls.append("rebuild_lesson_index")

    def show_shadow_lessons(self):
        self.calls.append("show_shadow_lessons")

    def extend_plan_to_next_vacation(self):
        self.calls.append("extend_plan_to_next_vacation")

    def mark_selected_as_ub(self):
        self.calls.append("mark_selected_as_ub")

    def toggle_resume_or_mark_ub(self):
        self.calls.append("toggle_resume_or_mark_ub")

    def show_ub_achievements_view(self):
        self.calls.append("show_ub_achievements_view")

    def show_shortcut_overview(self):
        self.calls.append("show_shortcut_overview")

    def restore_selected_from_cancel_action(self):
        self.calls.append("restore_selected_from_cancel_action")

    def undo_history(self):
        self.calls.append("undo_history")

    def redo_history(self):
        self.calls.append("redo_history")

    def undo_history_to_recent_index(self, recent_index: int):
        self.calls.append(f"undo_history_to_recent_index:{recent_index}")

    def copy_selected_lesson(self):
        self.calls.append("copy_selected_lesson")

    def cut_selected_lesson(self):
        self.calls.append("cut_selected_lesson")

    def paste_copied_lesson(self):
        self.calls.append("paste_copied_lesson")

    def clear_selected_lesson_content(self):
        self.calls.append("clear_selected_lesson_content")


class _LessonConversionSpy:
    def __init__(self):
        self.calls: list[str] = []

    def convert_selected_to_unterricht(self, **_kwargs):
        self.calls.append("convert_selected_to_unterricht")

    def convert_selected_to_ausfall(self, **_kwargs):
        self.calls.append("convert_selected_to_ausfall")

    def convert_selected_to_lzk(self, **_kwargs):
        self.calls.append("convert_selected_to_lzk")

    def convert_selected_to_hospitation(self, **_kwargs):
        self.calls.append("convert_selected_to_hospitation")


class _ColumnReorderSpy:
    def __init__(self):
        self.calls: list[int] = []

    def move_selected_columns(self, direction: int):
        self.calls.append(direction)


class _SelectionControllerSpy:
    def __init__(self, *, select_first_result: bool = True):
        self.select_first_result = select_first_result
        self.select_first_calls = 0
        self.move_horizontal_calls: list[int] = []
        self.move_adjacent_calls: list[int] = []
        self.move_edge_calls: list[bool] = []
        self.set_edge_column_calls: list[bool] = []
        self.set_selected_cell_calls: list[tuple[str, int, bool]] = []
        self.set_single_column_calls: list[tuple[int, bool]] = []
        self.selected_indices: list[int] = []
        self.clear_calls = 0
        self.ensure_column_calls: list[int] = []
        self.ensure_row_calls: list[tuple[str, int]] = []

    def select_first_editable_in_selected_column(self) -> bool:
        self.select_first_calls += 1
        return self.select_first_result

    def move_selected_cell_horizontal(self, direction: int) -> bool:
        self.move_horizontal_calls.append(direction)
        return True

    def clear_selected_cell(self):
        self.clear_calls += 1

    def move_selection_to_adjacent(self, direction: int) -> bool:
        self.move_adjacent_calls.append(direction)
        return True

    def move_selected_cell_to_edge(self, *, to_end: bool) -> bool:
        self.move_edge_calls.append(bool(to_end))
        return True

    def set_edge_column_selection(self, *, to_end: bool, ensure_visible: bool = False) -> bool:
        del ensure_visible
        self.set_edge_column_calls.append(bool(to_end))
        return True

    def set_selected_cell(self, _field_key: str, _day_index: int, *, ensure_visible: bool = False) -> bool:
        self.set_selected_cell_calls.append((_field_key, _day_index, ensure_visible))
        return True

    def set_single_column_selection(self, day_index: int, *, ensure_visible: bool = False):
        self.set_single_column_calls.append((day_index, ensure_visible))

    def selected_indices_sorted(self) -> list[int]:
        return list(self.selected_indices)

    def ensure_column_visible(self, day_index: int):
        self.ensure_column_calls.append(day_index)

    def ensure_row_visible(self, field_key: str, day_index: int):
        self.ensure_row_calls.append((field_key, day_index))


class _EditorControllerSpy:
    def __init__(self):
        self.apply_calls: list[tuple[str, int, str]] = []
        self.save_calls: list[tuple[str, int]] = []
        self.save_result = True

    def apply_value(self, field_key: str, day_index: int, value: str):
        self.apply_calls.append((field_key, day_index, value))

    def save_cell(self, field_key: str, day_index: int):
        self.save_calls.append((field_key, day_index))
        return self.save_result


class _OverviewControllerSpy:
    def __init__(self):
        self.close_calls = 0

    def close_detail_view(self):
        self.close_calls += 1


class _CellWidgetSpy:
    def __init__(self, text: str = ""):
        self.focus_calls = 0
        self._text = text

    def focus_set(self):
        self.focus_calls += 1

    def get(self, *_args):
        return self._text

    def mark_set(self, *_args):
        return None

    def see(self, *_args):
        return None


def _build_dummy_app():
    action_controller = _ActionControllerSpy()
    lesson_conversion_controller = _LessonConversionSpy()
    column_reorder_controller = _ColumnReorderSpy()
    return SimpleNamespace(
        action_controller=action_controller,
        lesson_conversion_controller=lesson_conversion_controller,
        column_reorder_controller=column_reorder_controller,
        _to_int=KursplanerApp._to_int,
    )


def test_toolbar_plan_intent_delegates_to_lesson_conversion_controller():
    app = _build_dummy_app()

    KursplanerApp._handle_ui_intent(app, UiIntent.TOOLBAR_PLAN)

    assert app.lesson_conversion_controller.calls == ["convert_selected_to_unterricht"]


def test_ctrl_k_routes_to_lzk_expected_horizon_when_disjoint_action_visible():
    action_controller = _ActionControllerSpy()
    lesson_conversion_controller = _LessonConversionSpy()
    app = SimpleNamespace(
        action_controller=action_controller,
        lesson_conversion_controller=lesson_conversion_controller,
        column_reorder_controller=_ColumnReorderSpy(),
        ui_state=SimpleNamespace(
            selection_level="column",
            SELECTION_LEVEL_COLUMN="column",
            visible_toolbar_actions={"lzk_expected_horizon"},
        ),
        is_detail_view=True,
        _to_int=KursplanerApp._to_int,
    )
    action_controller.export_selected_lzk_expected_horizon_action = lambda: action_controller.calls.append(
        "export_selected_lzk_expected_horizon_action"
    )

    controller = ui_intent_controller.MainWindowUiIntentController(app)
    controller.handle_intent(UiIntent.TOOLBAR_LZK, from_shortcut=True)

    assert action_controller.calls == ["export_selected_lzk_expected_horizon_action"]
    assert lesson_conversion_controller.calls == []


def test_ctrl_k_routes_to_lzk_convert_when_lzk_action_visible():
    action_controller = _ActionControllerSpy()
    lesson_conversion_controller = _LessonConversionSpy()
    app = SimpleNamespace(
        action_controller=action_controller,
        lesson_conversion_controller=lesson_conversion_controller,
        column_reorder_controller=_ColumnReorderSpy(),
        ui_state=SimpleNamespace(
            selection_level="column",
            SELECTION_LEVEL_COLUMN="column",
            visible_toolbar_actions={"lzk"},
        ),
        is_detail_view=True,
        _to_int=KursplanerApp._to_int,
    )
    action_controller.export_selected_lzk_expected_horizon_action = lambda: action_controller.calls.append(
        "export_selected_lzk_expected_horizon_action"
    )

    controller = ui_intent_controller.MainWindowUiIntentController(app)
    controller.handle_intent(UiIntent.TOOLBAR_LZK, from_shortcut=True)

    assert lesson_conversion_controller.calls == ["convert_selected_to_lzk"]
    assert action_controller.calls == []


def test_toolbar_move_columns_intent_normalizes_direction_and_delegates():
    app = _build_dummy_app()

    KursplanerApp._handle_ui_intent(app, UiIntent.TOOLBAR_MOVE_COLUMNS, direction="-1")

    assert app.column_reorder_controller.calls == [-1]


def test_toolbar_ausfall_intent_marks_ausfall_for_non_cancel_selection():
    app = _build_dummy_app()
    app.day_columns = [{"is_cancel": False}]
    app._get_single_selected_or_warn = lambda: 0

    KursplanerApp._handle_ui_intent(app, UiIntent.TOOLBAR_AUSFALL)

    assert app.lesson_conversion_controller.calls == ["convert_selected_to_ausfall"]
    assert app.action_controller.calls == []


def test_toolbar_ausfall_intent_restores_cancel_selection():
    app = _build_dummy_app()
    app.day_columns = [{"is_cancel": True}]
    app._get_single_selected_or_warn = lambda: 0

    KursplanerApp._handle_ui_intent(app, UiIntent.TOOLBAR_AUSFALL)

    assert app.lesson_conversion_controller.calls == []
    assert app.action_controller.calls == ["restore_selected_from_cancel_action"]


def test_app_utility_intents_delegate_to_action_controller():
    app = _build_dummy_app()

    KursplanerApp._handle_ui_intent(app, UiIntent.OPEN_SETTINGS)
    KursplanerApp._handle_ui_intent(app, UiIntent.REBUILD_LESSON_INDEX)
    KursplanerApp._handle_ui_intent(app, UiIntent.SHOW_SHADOW_LESSONS)
    KursplanerApp._handle_ui_intent(app, UiIntent.TOOLBAR_EXTEND_TO_VACATION)
    KursplanerApp._handle_ui_intent(app, UiIntent.MARK_SELECTED_AS_UB)
    KursplanerApp._handle_ui_intent(app, UiIntent.TOGGLE_RESUME_OR_UB)
    KursplanerApp._handle_ui_intent(app, UiIntent.SHOW_UB_ACHIEVEMENTS)
    KursplanerApp._handle_ui_intent(app, UiIntent.SHOW_SHORTCUT_OVERVIEW)

    assert app.action_controller.calls == [
        "open_settings_window",
        "rebuild_lesson_index",
        "show_shadow_lessons",
        "extend_plan_to_next_vacation",
        "mark_selected_as_ub",
        "toggle_resume_or_mark_ub",
        "show_ub_achievements_view",
        "show_shortcut_overview",
    ]


def test_grid_enter_from_column_selection_selects_first_editable_cell():
    selection_controller = _SelectionControllerSpy(select_first_result=True)
    app = SimpleNamespace(
        action_controller=_ActionControllerSpy(),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        selection_controller=selection_controller,
        ui_state=MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN),
        is_detail_view=True,
        focus_get=lambda: None,
        _to_int=KursplanerApp._to_int,
    )

    result = KursplanerApp._handle_ui_intent(app, UiIntent.GRID_ENTER)

    assert result == "break"
    assert selection_controller.select_first_calls == 1


def test_escape_from_cell_selection_returns_to_column_mode_without_closing_detail():
    selection_controller = _SelectionControllerSpy(select_first_result=True)
    overview_controller = _OverviewControllerSpy()
    ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_CELL)
    ui_state.set_selected_cell("Stundenthema", 0)
    app = SimpleNamespace(
        action_controller=_ActionControllerSpy(),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        selection_controller=selection_controller,
        overview_controller=overview_controller,
        ui_state=ui_state,
        grid_canvas=SimpleNamespace(focus_set=lambda: None),
        is_detail_view=True,
        focus_get=lambda: None,
        _to_int=KursplanerApp._to_int,
    )

    result = KursplanerApp._handle_ui_intent(app, UiIntent.SHORTCUT_ESCAPE)

    assert result == "break"
    assert selection_controller.clear_calls == 1
    assert app.ui_state.selection_level == app.ui_state.SELECTION_LEVEL_COLUMN
    assert overview_controller.close_calls == 0


def test_escape_from_edit_mode_keeps_editor_active_when_save_fails():
    selection_controller = _SelectionControllerSpy(select_first_result=True)
    editor_controller = _EditorControllerSpy()
    editor_controller.save_result = False
    overview_controller = _OverviewControllerSpy()
    ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_EDIT)
    ui_state.set_selected_cell("Stundenthema", 0)
    ui_state.set_active_editor("Stundenthema", 0)
    app = SimpleNamespace(
        action_controller=_ActionControllerSpy(),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        selection_controller=selection_controller,
        editor_controller=editor_controller,
        overview_controller=overview_controller,
        ui_state=ui_state,
        grid_canvas=SimpleNamespace(focus_set=lambda: None),
        is_detail_view=True,
        focus_get=lambda: None,
        _to_int=KursplanerApp._to_int,
    )

    result = KursplanerApp._handle_ui_intent(app, UiIntent.SHORTCUT_ESCAPE)

    assert result == "break"
    assert editor_controller.save_calls == [("Stundenthema", 0)]
    assert app.ui_state.active_editor is not None
    assert app.ui_state.selection_level == app.ui_state.SELECTION_LEVEL_EDIT
    assert overview_controller.close_calls == 0


def test_alt_left_navigation_in_column_mode_uses_non_skip_path():
    selection_controller = _SelectionControllerSpy(select_first_result=True)
    app = SimpleNamespace(
        action_controller=_ActionControllerSpy(),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        selection_controller=selection_controller,
        ui_state=MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN),
        is_detail_view=True,
        focus_get=lambda: None,
        _to_int=KursplanerApp._to_int,
    )

    result = KursplanerApp._handle_ui_intent(app, UiIntent.SHORTCUT_DETAIL_LEFT_ALL)

    assert result == "break"
    assert selection_controller.move_adjacent_calls == [-1]


def test_grid_delete_cell_clears_selected_editable_cell():
    selection_controller = _SelectionControllerSpy(select_first_result=True)
    editor_controller = _EditorControllerSpy()
    ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_CELL)
    ui_state.set_selected_cell("Stundenthema", 0)
    app = SimpleNamespace(
        action_controller=SimpleNamespace(update_action_controls=lambda: None),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        selection_controller=selection_controller,
        editor_controller=editor_controller,
        row_display_mode_usecase=SimpleNamespace(is_editable=lambda _field_key, _day: True),
        ui_state=ui_state,
        day_columns=[{"datum": "2026-03-27"}],
        _collect_day_columns=lambda: None,
        _update_grid_column=lambda _day_index: None,
        _update_selected_lesson_metrics=lambda: None,
        is_detail_view=True,
        focus_get=lambda: None,
        _to_int=KursplanerApp._to_int,
    )

    result = KursplanerApp._handle_ui_intent(app, UiIntent.GRID_DELETE_CELL)

    assert result == "break"
    assert editor_controller.apply_calls == [("Stundenthema", 0, "")]


def test_grid_delete_cell_routes_content_delete_to_action_controller():
    action_controller = _ActionControllerSpy()
    editor_controller = _EditorControllerSpy()
    ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_CELL)
    ui_state.set_selected_cell("inhalt", 0)
    app = SimpleNamespace(
        action_controller=action_controller,
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        selection_controller=_SelectionControllerSpy(select_first_result=True),
        editor_controller=editor_controller,
        row_display_mode_usecase=SimpleNamespace(is_editable=lambda _field_key, _day: True),
        ui_state=ui_state,
        day_columns=[{"datum": "2026-03-27"}],
        _collect_day_columns=lambda: None,
        _update_grid_column=lambda _day_index: None,
        _update_selected_lesson_metrics=lambda: None,
        is_detail_view=True,
        focus_get=lambda: None,
        _to_int=KursplanerApp._to_int,
    )

    result = KursplanerApp._handle_ui_intent(app, UiIntent.GRID_DELETE_CELL)

    assert result == "break"
    assert action_controller.calls == ["clear_selected_lesson_content"]
    assert editor_controller.apply_calls == []


def test_grid_cell_click_marks_cell_without_entering_edit_on_first_click():
    selection_controller = _SelectionControllerSpy()
    app = SimpleNamespace(
        action_controller=_ActionControllerSpy(),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        selection_controller=selection_controller,
        ui_state=MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN),
        row_display_mode_usecase=SimpleNamespace(is_editable=lambda _field_key, _day: True),
        day_columns=[{"datum": "2026-03-27"}],
        grid_canvas=SimpleNamespace(focus_set=lambda: None),
        is_detail_view=True,
        focus_get=lambda: None,
        _to_int=KursplanerApp._to_int,
    )

    result = KursplanerApp._handle_ui_intent(
        app,
        UiIntent.GRID_CELL_CLICK,
        field_key="Stundenthema",
        day_index=0,
    )

    assert result == "break"
    assert selection_controller.set_selected_cell_calls == [("Stundenthema", 0, True)]
    assert selection_controller.select_first_calls == 0


def test_grid_cell_click_on_selected_cell_starts_edit_like_enter():
    selection_controller = _SelectionControllerSpy()
    cell_widget = _CellWidgetSpy()
    ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_CELL)
    ui_state.set_selected_cell("Stundenthema", 0)
    app = SimpleNamespace(
        action_controller=_ActionControllerSpy(),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        selection_controller=selection_controller,
        ui_state=ui_state,
        row_display_mode_usecase=SimpleNamespace(is_editable=lambda _field_key, _day: True),
        day_columns=[{"datum": "2026-03-27"}],
        cell_widgets={("Stundenthema", 0): cell_widget},
        grid_canvas=SimpleNamespace(focus_set=lambda: None),
        is_detail_view=True,
        focus_get=lambda: None,
        _to_int=KursplanerApp._to_int,
    )

    result = KursplanerApp._handle_ui_intent(
        app,
        UiIntent.GRID_CELL_CLICK,
        field_key="Stundenthema",
        day_index=0,
    )

    assert result == "break"
    assert cell_widget.focus_calls == 1


def test_grid_date_cell_click_switches_to_column_selection():
    selection_controller = _SelectionControllerSpy()
    ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_CELL)
    ui_state.set_selected_cell("Stundenthema", 0)
    app = SimpleNamespace(
        action_controller=_ActionControllerSpy(),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        selection_controller=selection_controller,
        ui_state=ui_state,
        day_columns=[{"datum": "2026-03-27"}, {"datum": "2026-03-28"}],
        grid_canvas=SimpleNamespace(focus_set=lambda: None),
        is_detail_view=True,
        focus_get=lambda: None,
        _to_int=KursplanerApp._to_int,
    )

    result = KursplanerApp._handle_ui_intent(app, UiIntent.GRID_DATE_CELL_CLICK, day_index=1)

    assert result == "break"
    assert selection_controller.set_single_column_calls == [(1, True)]


def test_grid_column_click_on_selected_column_uses_enter_behavior():
    selection_controller = _SelectionControllerSpy(select_first_result=True)
    selection_controller.selected_indices = [0]
    ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN)
    app = SimpleNamespace(
        action_controller=_ActionControllerSpy(),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        selection_controller=selection_controller,
        ui_state=ui_state,
        day_columns=[{"datum": "2026-03-27"}],
        grid_canvas=SimpleNamespace(focus_set=lambda: None),
        is_detail_view=True,
        focus_get=lambda: None,
        _to_int=KursplanerApp._to_int,
    )

    result = KursplanerApp._handle_ui_intent(app, UiIntent.GRID_COLUMN_CLICK, day_index=0)

    assert result == "break"
    assert selection_controller.select_first_calls == 1
    assert selection_controller.set_single_column_calls == []


def test_shortcut_move_columns_is_blocked_outside_column_selection_mode():
    app = _build_dummy_app()
    app.is_detail_view = True
    app.ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_CELL)
    app.ui_state.visible_toolbar_actions = {"move_left", "move_right"}

    KursplanerApp._handle_ui_intent(
        app,
        UiIntent.TOOLBAR_MOVE_COLUMNS,
        direction="-1",
        from_shortcut=True,
    )

    assert app.column_reorder_controller.calls == []


def test_shortcut_move_columns_works_in_column_selection_mode():
    app = _build_dummy_app()
    app.is_detail_view = True
    app.ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN)
    app.ui_state.visible_toolbar_actions = {"move_left", "move_right"}

    KursplanerApp._handle_ui_intent(
        app,
        UiIntent.TOOLBAR_MOVE_COLUMNS,
        direction="1",
        from_shortcut=True,
    )

    assert app.column_reorder_controller.calls == [1]


def test_ctrl_enter_commits_edit_mode_like_escape():
    selection_controller = _SelectionControllerSpy(select_first_result=True)
    editor_controller = _EditorControllerSpy()
    ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_EDIT)
    ui_state.set_selected_cell("Stundenthema", 0)
    ui_state.set_active_editor("Stundenthema", 0)
    app = SimpleNamespace(
        action_controller=_ActionControllerSpy(),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        selection_controller=selection_controller,
        editor_controller=editor_controller,
        overview_controller=_OverviewControllerSpy(),
        ui_state=ui_state,
        grid_canvas=SimpleNamespace(focus_set=lambda: None),
        is_detail_view=True,
        focus_get=lambda: None,
        _to_int=KursplanerApp._to_int,
    )

    result = KursplanerApp._handle_ui_intent(app, UiIntent.SHORTCUT_COMMIT_EDIT)

    assert result == "break"
    assert editor_controller.save_calls == [("Stundenthema", 0)]
    assert app.ui_state.active_editor is None
    assert app.ui_state.selection_level == app.ui_state.SELECTION_LEVEL_CELL


def test_ctrl_enter_is_ignored_outside_edit_mode():
    app = _build_dummy_app()
    app.is_detail_view = True
    app.ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_CELL)

    result = KursplanerApp._handle_ui_intent(app, UiIntent.SHORTCUT_COMMIT_EDIT)

    assert result is None


def test_ctrl_enter_column_shortcut_routes_to_unterricht_for_regular_column():
    app = _build_dummy_app()
    app.is_detail_view = True
    app.ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN)
    app.focus_get = lambda: None
    app.day_columns = [{"is_cancel": False, "is_hospitation": False, "is_lzk": False}]
    app._get_single_selected_or_warn = lambda: 0

    result = KursplanerApp._handle_ui_intent(app, UiIntent.SHORTCUT_COMMIT_COLUMN)

    assert result == "break"
    assert app.lesson_conversion_controller.calls == ["convert_selected_to_unterricht"]


def test_ctrl_enter_column_shortcut_routes_to_ausfall_for_cancel_column():
    app = _build_dummy_app()
    app.is_detail_view = True
    app.ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN)
    app.focus_get = lambda: None
    app.day_columns = [{"is_cancel": True, "is_hospitation": False, "is_lzk": False}]
    app._get_single_selected_or_warn = lambda: 0

    result = KursplanerApp._handle_ui_intent(app, UiIntent.SHORTCUT_COMMIT_COLUMN)

    assert result == "break"
    assert app.lesson_conversion_controller.calls == ["convert_selected_to_ausfall"]


def test_ctrl_enter_column_shortcut_routes_to_hospitation():
    app = _build_dummy_app()
    app.is_detail_view = True
    app.ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN)
    app.focus_get = lambda: None
    app.day_columns = [{"is_cancel": False, "is_hospitation": True, "is_lzk": False}]
    app._get_single_selected_or_warn = lambda: 0

    result = KursplanerApp._handle_ui_intent(app, UiIntent.SHORTCUT_COMMIT_COLUMN)

    assert result == "break"
    assert app.lesson_conversion_controller.calls == ["convert_selected_to_hospitation"]


def test_ctrl_enter_column_shortcut_routes_to_lzk():
    app = _build_dummy_app()
    app.is_detail_view = True
    app.ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN)
    app.focus_get = lambda: None
    app.day_columns = [{"is_cancel": False, "is_hospitation": False, "is_lzk": True}]
    app._get_single_selected_or_warn = lambda: 0

    result = KursplanerApp._handle_ui_intent(app, UiIntent.SHORTCUT_COMMIT_COLUMN)

    assert result == "break"
    assert app.lesson_conversion_controller.calls == ["convert_selected_to_lzk"]


def test_shortcut_undo_is_ignored_inside_text_widget(monkeypatch):
    class _FakeText:
        pass

    monkeypatch.setattr(ui_intent_controller.tk, "Text", _FakeText)

    app = _build_dummy_app()
    app.is_detail_view = True
    app.ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN)

    event = SimpleNamespace(widget=_FakeText())
    result = KursplanerApp._handle_ui_intent(app, UiIntent.TOOLBAR_UNDO, event=event)

    assert result is None
    assert "undo_history" not in app.action_controller.calls


def test_shortcut_redo_is_ignored_inside_text_widget(monkeypatch):
    class _FakeText:
        pass

    monkeypatch.setattr(ui_intent_controller.tk, "Text", _FakeText)

    app = _build_dummy_app()
    app.is_detail_view = True
    app.ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN)

    event = SimpleNamespace(widget=_FakeText())
    result = KursplanerApp._handle_ui_intent(app, UiIntent.TOOLBAR_REDO, event=event)

    assert result is None
    assert "redo_history" not in app.action_controller.calls


def test_edit_undo_to_recent_index_routes_to_action_controller():
    app = _build_dummy_app()
    app.is_detail_view = True
    app.ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN)

    result = KursplanerApp._handle_ui_intent(
        app,
        UiIntent.EDIT_UNDO_TO_RECENT_INDEX,
        recent_index=2,
    )

    assert result == "break"
    assert "undo_history_to_recent_index:2" in app.action_controller.calls


def test_shortcut_clear_is_blocked_outside_column_selection_mode():
    app = _build_dummy_app()
    app.is_detail_view = True
    app.ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_CELL)
    app.ui_state.visible_toolbar_actions = {"clear"}

    KursplanerApp._handle_ui_intent(
        app,
        UiIntent.TOOLBAR_CLEAR,
        from_shortcut=True,
    )

    assert "clear_selected_lesson_content" not in app.action_controller.calls


def test_shortcut_clear_works_in_column_selection_mode():
    app = _build_dummy_app()
    app.is_detail_view = True
    app.ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN)
    app.ui_state.visible_toolbar_actions = {"clear"}

    KursplanerApp._handle_ui_intent(
        app,
        UiIntent.TOOLBAR_CLEAR,
        from_shortcut=True,
    )

    assert app.action_controller.calls == ["clear_selected_lesson_content"]


def test_shortcut_copy_is_ignored_in_edit_mode():
    app = _build_dummy_app()
    app.is_detail_view = True
    app.ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_EDIT)
    app.focus_get = lambda: None

    event = SimpleNamespace(widget=object(), state=0)
    result = KursplanerApp._handle_ui_intent(app, UiIntent.SHORTCUT_COPY, event=event)

    assert result is None
    assert "copy_selected_lesson" not in app.action_controller.calls


def test_shortcut_copy_works_in_column_selection_mode():
    app = _build_dummy_app()
    app.is_detail_view = True
    app.ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN)
    app.focus_get = lambda: None

    event = SimpleNamespace(widget=object(), state=0)
    result = KursplanerApp._handle_ui_intent(app, UiIntent.SHORTCUT_COPY, event=event)

    assert result == "break"
    assert app.action_controller.calls == ["copy_selected_lesson"]


def test_shortcut_cut_works_in_column_selection_mode():
    app = _build_dummy_app()
    app.is_detail_view = True
    app.ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN)
    app.focus_get = lambda: None

    event = SimpleNamespace(widget=object(), state=0)
    result = KursplanerApp._handle_ui_intent(app, UiIntent.SHORTCUT_CUT, event=event)

    assert result == "break"
    assert app.action_controller.calls == ["cut_selected_lesson"]


def test_shortcut_copy_in_cell_selection_copies_selected_cell_content():
    app = _build_dummy_app()
    app.is_detail_view = True
    app.ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_CELL)
    app.ui_state.set_selected_cell("Stundenthema", 0)
    app.cell_widgets = {("Stundenthema", 0): _CellWidgetSpy("Alpha\nBeta")}
    copied_values: list[str] = []
    app.clipboard_clear = lambda: None
    app.clipboard_append = lambda value: copied_values.append(value)
    app.focus_get = lambda: None

    event = SimpleNamespace(widget=object(), state=0)
    result = KursplanerApp._handle_ui_intent(app, UiIntent.SHORTCUT_COPY, event=event)

    assert result == "break"
    assert copied_values == ["Alpha\nBeta"]
    assert app.action_controller.calls == []


def test_shortcut_paste_in_cell_selection_replaces_full_cell_content():
    selection_controller = _SelectionControllerSpy(select_first_result=True)
    editor_controller = _EditorControllerSpy()
    app = SimpleNamespace(
        action_controller=SimpleNamespace(update_action_controls=lambda: None),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        selection_controller=selection_controller,
        editor_controller=editor_controller,
        row_display_mode_usecase=SimpleNamespace(is_editable=lambda _field_key, _day: True),
        ui_state=MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_CELL),
        day_columns=[{"datum": "2026-03-27"}],
        _collect_day_columns=lambda: None,
        _update_grid_column=lambda _day_index: None,
        _update_selected_lesson_metrics=lambda: None,
        is_detail_view=True,
        focus_get=lambda: None,
        clipboard_get=lambda: "Neu\nKomplett",
        _to_int=KursplanerApp._to_int,
    )
    app.ui_state.set_selected_cell("Stundenthema", 0)

    event = SimpleNamespace(widget=object(), state=0)
    result = KursplanerApp._handle_ui_intent(app, UiIntent.SHORTCUT_PASTE, event=event)

    assert result == "break"
    assert editor_controller.apply_calls == [("Stundenthema", 0, "Neu\nKomplett")]


def test_toolbar_paste_in_cell_selection_replaces_full_cell_content():
    selection_controller = _SelectionControllerSpy(select_first_result=True)
    editor_controller = _EditorControllerSpy()
    app = SimpleNamespace(
        action_controller=SimpleNamespace(update_action_controls=lambda: None),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        selection_controller=selection_controller,
        editor_controller=editor_controller,
        row_display_mode_usecase=SimpleNamespace(is_editable=lambda _field_key, _day: True),
        ui_state=MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_CELL),
        day_columns=[{"datum": "2026-03-27"}],
        _collect_day_columns=lambda: None,
        _update_grid_column=lambda _day_index: None,
        _update_selected_lesson_metrics=lambda: None,
        is_detail_view=True,
        focus_get=lambda: None,
        clipboard_get=lambda: "Neu\nAus Toolbar",
        _to_int=KursplanerApp._to_int,
    )
    app.ui_state.set_selected_cell("Stundenthema", 0)

    result = KursplanerApp._handle_ui_intent(app, UiIntent.TOOLBAR_PASTE)

    assert result == "break"
    assert editor_controller.apply_calls == [("Stundenthema", 0, "Neu\nAus Toolbar")]


def test_toolbar_paste_in_cell_selection_is_ignored_for_whitespace_clipboard():
    selection_controller = _SelectionControllerSpy(select_first_result=True)
    editor_controller = _EditorControllerSpy()
    app = SimpleNamespace(
        action_controller=SimpleNamespace(update_action_controls=lambda: None),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        selection_controller=selection_controller,
        editor_controller=editor_controller,
        row_display_mode_usecase=SimpleNamespace(is_editable=lambda _field_key, _day: True),
        ui_state=MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_CELL),
        day_columns=[{"datum": "2026-03-27"}],
        _collect_day_columns=lambda: None,
        _update_grid_column=lambda _day_index: None,
        _update_selected_lesson_metrics=lambda: None,
        is_detail_view=True,
        focus_get=lambda: None,
        clipboard_get=lambda: "   \n",
        _to_int=KursplanerApp._to_int,
    )
    app.ui_state.set_selected_cell("Stundenthema", 0)

    result = KursplanerApp._handle_ui_intent(app, UiIntent.TOOLBAR_PASTE)

    assert result is None
    assert editor_controller.apply_calls == []


def test_shortcut_cut_in_cell_selection_copies_and_clears_selected_cell():
    selection_controller = _SelectionControllerSpy(select_first_result=True)
    editor_controller = _EditorControllerSpy()
    copied_values: list[str] = []
    app = SimpleNamespace(
        action_controller=SimpleNamespace(update_action_controls=lambda: None),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        selection_controller=selection_controller,
        editor_controller=editor_controller,
        row_display_mode_usecase=SimpleNamespace(is_editable=lambda _field_key, _day: True),
        ui_state=MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_CELL),
        day_columns=[{"datum": "2026-03-27"}],
        cell_widgets={("Stundenthema", 0): _CellWidgetSpy("Vorher")},
        _collect_day_columns=lambda: None,
        _update_grid_column=lambda _day_index: None,
        _update_selected_lesson_metrics=lambda: None,
        is_detail_view=True,
        focus_get=lambda: None,
        clipboard_clear=lambda: None,
        clipboard_append=lambda value: copied_values.append(value),
        _to_int=KursplanerApp._to_int,
    )
    app.ui_state.set_selected_cell("Stundenthema", 0)

    event = SimpleNamespace(widget=object(), state=0)
    result = KursplanerApp._handle_ui_intent(app, UiIntent.SHORTCUT_CUT, event=event)

    assert result == "break"
    assert copied_values == ["Vorher"]
    assert editor_controller.apply_calls == [("Stundenthema", 0, "")]


def test_shortcut_cut_routes_in_column_selection_mode():
    app = _build_dummy_app()
    app.is_detail_view = True
    app.ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN)
    app.focus_get = lambda: None

    event = SimpleNamespace(widget=object(), state=0)
    result = KursplanerApp._handle_ui_intent(app, UiIntent.SHORTCUT_CUT, event=event)

    assert result == "break"
    assert app.action_controller.calls == ["cut_selected_lesson"]


def test_grid_delete_is_ignored_when_event_originates_from_text_widget(monkeypatch):
    class _FakeText:
        pass

    monkeypatch.setattr(ui_intent_controller.tk, "Text", _FakeText)

    selection_controller = _SelectionControllerSpy(select_first_result=True)
    editor_controller = _EditorControllerSpy()
    ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_CELL)
    ui_state.set_selected_cell("Stundenthema", 0)
    app = SimpleNamespace(
        action_controller=SimpleNamespace(update_action_controls=lambda: None),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        selection_controller=selection_controller,
        editor_controller=editor_controller,
        row_display_mode_usecase=SimpleNamespace(is_editable=lambda _field_key, _day: True),
        ui_state=ui_state,
        day_columns=[{"datum": "2026-03-27"}],
        _collect_day_columns=lambda: None,
        _update_grid_column=lambda _day_index: None,
        _update_selected_lesson_metrics=lambda: None,
        is_detail_view=True,
        focus_get=lambda: None,
        _to_int=KursplanerApp._to_int,
    )

    event = SimpleNamespace(widget=_FakeText())
    result = KursplanerApp._handle_ui_intent(app, UiIntent.GRID_DELETE_CELL, event=event)

    assert result is None
    assert editor_controller.apply_calls == []


def test_grid_home_is_ignored_when_event_originates_from_text_widget(monkeypatch):
    class _FakeText:
        pass

    monkeypatch.setattr(ui_intent_controller.tk, "Text", _FakeText)

    selection_controller = _SelectionControllerSpy(select_first_result=True)
    app = SimpleNamespace(
        action_controller=_ActionControllerSpy(),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        selection_controller=selection_controller,
        ui_state=MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_CELL),
        is_detail_view=True,
        focus_get=lambda: None,
        _to_int=KursplanerApp._to_int,
    )

    event = SimpleNamespace(widget=_FakeText())
    result = KursplanerApp._handle_ui_intent(app, UiIntent.GRID_HOME, event=event)

    assert result is None
    assert selection_controller.move_edge_calls == []


def test_grid_end_is_ignored_when_focus_is_text_widget(monkeypatch):
    class _FakeText:
        pass

    monkeypatch.setattr(ui_intent_controller.tk, "Text", _FakeText)

    selection_controller = _SelectionControllerSpy(select_first_result=True)
    app = SimpleNamespace(
        action_controller=_ActionControllerSpy(),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        selection_controller=selection_controller,
        ui_state=MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_CELL),
        is_detail_view=True,
        focus_get=lambda: _FakeText(),
        _to_int=KursplanerApp._to_int,
    )

    result = KursplanerApp._handle_ui_intent(app, UiIntent.GRID_END)

    assert result is None
    assert selection_controller.move_edge_calls == []


def test_ctrl_down_expands_selected_row_in_cell_mode():
    ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_CELL)
    ui_state.set_selected_cell("Stundenthema", 0)
    rebuild_calls = {"count": 0}
    app = SimpleNamespace(
        action_controller=_ActionControllerSpy(),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        ui_state=ui_state,
        row_expanded={"Stundenthema": False},
        _rebuild_grid=lambda: rebuild_calls.__setitem__("count", rebuild_calls["count"] + 1),
        is_detail_view=True,
        focus_get=lambda: None,
        _to_int=KursplanerApp._to_int,
    )

    event = SimpleNamespace(widget=object(), state=0)
    result = KursplanerApp._handle_ui_intent(app, UiIntent.SHORTCUT_EXPAND_SELECTED_ROW, event=event)

    assert result == "break"
    assert app.row_expanded["Stundenthema"] is True
    assert rebuild_calls["count"] == 1


def test_ctrl_up_collapses_selected_row_in_cell_mode():
    ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_CELL)
    ui_state.set_selected_cell("Stundenthema", 0)
    rebuild_calls = {"count": 0}
    app = SimpleNamespace(
        action_controller=_ActionControllerSpy(),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        ui_state=ui_state,
        row_expanded={"Stundenthema": True},
        _rebuild_grid=lambda: rebuild_calls.__setitem__("count", rebuild_calls["count"] + 1),
        is_detail_view=True,
        focus_get=lambda: None,
        _to_int=KursplanerApp._to_int,
    )

    event = SimpleNamespace(widget=object(), state=0)
    result = KursplanerApp._handle_ui_intent(app, UiIntent.SHORTCUT_COLLAPSE_SELECTED_ROW, event=event)

    assert result == "break"
    assert app.row_expanded["Stundenthema"] is False
    assert rebuild_calls["count"] == 1


def test_ctrl_down_is_ignored_outside_cell_mode():
    ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN)
    ui_state.set_selected_cell("Stundenthema", 0)
    rebuild_calls = {"count": 0}
    app = SimpleNamespace(
        action_controller=_ActionControllerSpy(),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        ui_state=ui_state,
        row_expanded={"Stundenthema": False},
        _rebuild_grid=lambda: rebuild_calls.__setitem__("count", rebuild_calls["count"] + 1),
        is_detail_view=True,
        focus_get=lambda: None,
        _to_int=KursplanerApp._to_int,
    )
    app.ui_state.set_selection_level(app.ui_state.SELECTION_LEVEL_COLUMN)

    event = SimpleNamespace(widget=object(), state=0)
    result = KursplanerApp._handle_ui_intent(app, UiIntent.SHORTCUT_EXPAND_SELECTED_ROW, event=event)

    assert result is None
    assert app.row_expanded["Stundenthema"] is False
    assert rebuild_calls["count"] == 0


def test_ctrl_down_expand_rebuild_pipeline_ensures_selected_cell_visible():
    selection_controller = _SelectionControllerSpy(select_first_result=True)
    ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_CELL)
    ui_state.set_selected_cell("Stundenthema", 0)
    rebuild_calls = {"count": 0}
    app = SimpleNamespace(
        action_controller=_ActionControllerSpy(),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        selection_controller=selection_controller,
        ui_state=ui_state,
        row_expanded={"Stundenthema": False},
        cell_widgets={("Stundenthema", 0): object()},
        _rebuild_grid=lambda: rebuild_calls.__setitem__("count", rebuild_calls["count"] + 1),
        is_detail_view=True,
        focus_get=lambda: None,
        _to_int=KursplanerApp._to_int,
    )

    event = SimpleNamespace(widget=object(), state=0)
    result = KursplanerApp._handle_ui_intent(app, UiIntent.SHORTCUT_EXPAND_SELECTED_ROW, event=event)

    assert result == "break"
    assert rebuild_calls["count"] == 1
    assert selection_controller.ensure_column_calls == [0]
    assert selection_controller.ensure_row_calls == [("Stundenthema", 0)]


def test_toggle_expand_mode_uses_rebuild_pipeline_and_ensures_selected_cell_visible():
    selection_controller = _SelectionControllerSpy(select_first_result=True)
    ui_state = MainWindowUiState(selection_level=MainWindowUiState.SELECTION_LEVEL_CELL)
    ui_state.set_selected_cell("Stundenthema", 0)
    rebuild_calls = {"count": 0}
    app = SimpleNamespace(
        action_controller=_ActionControllerSpy(),
        lesson_conversion_controller=_LessonConversionSpy(),
        column_reorder_controller=_ColumnReorderSpy(),
        selection_controller=selection_controller,
        ui_state=ui_state,
        row_defs=[("Stundenthema", "Thema"), ("Kompetenzen", "Kompetenzen")],
        row_expanded={"Stundenthema": False, "Kompetenzen": False},
        expand_long_rows_var=SimpleNamespace(get=lambda: True),
        cell_widgets={("Stundenthema", 0): object()},
        _rebuild_grid=lambda: rebuild_calls.__setitem__("count", rebuild_calls["count"] + 1),
        is_detail_view=True,
        focus_get=lambda: None,
        _to_int=KursplanerApp._to_int,
    )

    result = KursplanerApp._handle_ui_intent(app, UiIntent.TOGGLE_EXPAND_MODE)

    assert result is None
    assert app.row_expanded == {"Stundenthema": True, "Kompetenzen": True}
    assert rebuild_calls["count"] == 1
    assert selection_controller.ensure_column_calls == [0]
    assert selection_controller.ensure_row_calls == [("Stundenthema", 0)]
