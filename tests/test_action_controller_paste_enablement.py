from types import SimpleNamespace

from kursplaner.adapters.gui.action_controller import MainWindowActionController
from kursplaner.adapters.gui.toolbar_viewmodel import ToolbarActionView, ToolbarViewModel
from kursplaner.core.usecases.action_button_state_usecase import ActionButtonState


def _state(**overrides):
    values = {
        "can_plan": False,
        "can_extend_to_vacation": False,
        "can_lzk": False,
        "can_ausfall": False,
        "can_hospitation": False,
        "can_mark_ub": False,
        "can_resume": False,
        "can_split": False,
        "can_merge": False,
        "can_move_left": False,
        "can_move_right": False,
        "can_clear": False,
        "can_find": False,
        "can_copy": False,
        "can_paste": False,
        "can_export_topic_pdf": False,
        "can_export_lzk_expected_horizon": False,
    }
    values.update(overrides)
    return ActionButtonState(**values)


def _controller_for_update(*, selection_level: str, clipboard_value: str, can_paste: bool):
    controller = MainWindowActionController.__new__(MainWindowActionController)
    ui_state = SimpleNamespace(
        selection_level=selection_level,
        SELECTION_LEVEL_CELL="cell",
        visible_toolbar_actions=set(),
    )
    app = SimpleNamespace(
        action_buttons={"paste": object()},
        selected_day_indices=set(),
        day_columns=[],
        current_table=None,
        clipboard_lesson_path=None,
        is_detail_view=True,
        ui_state=ui_state,
        clipboard_get=lambda: clipboard_value,
    )

    controller.app = app
    controller._action_button_state_uc = SimpleNamespace(compute=lambda **_kwargs: _state(can_paste=can_paste))
    controller._history_uc = SimpleNamespace(can_undo=lambda: False, can_redo=lambda: False)

    captured: dict[str, object] = {}

    def _apply(vm):
        captured["vm"] = vm
        return {"paste"}

    controller._apply_toolbar_view_model = _apply
    return controller, captured


def test_update_action_controls_enables_paste_in_cell_mode_for_non_whitespace_clipboard():
    controller, captured = _controller_for_update(selection_level="cell", clipboard_value="abc", can_paste=False)

    controller.update_action_controls()

    vm = captured["vm"]
    assert vm.actions["paste"].enabled is True


def test_update_action_controls_disables_paste_in_cell_mode_for_whitespace_clipboard():
    controller, captured = _controller_for_update(selection_level="cell", clipboard_value="  \n", can_paste=True)

    controller.update_action_controls()

    vm = captured["vm"]
    assert vm.actions["paste"].enabled is False


def test_apply_toolbar_view_model_returns_only_enabled_actions_for_shortcut_guards():
    class _ButtonSpy:
        def __init__(self):
            self.state_calls: list[list[str]] = []

        def state(self, args):
            self.state_calls.append(list(args))

    plan_button = _ButtonSpy()
    lzk_button = _ButtonSpy()

    controller = MainWindowActionController.__new__(MainWindowActionController)
    controller.app = SimpleNamespace(
        action_buttons={"plan": plan_button, "lzk": lzk_button},
        toolbar_icon_styler=None,
        theme_var=SimpleNamespace(get=lambda: "light"),
    )
    controller._set_slot_visibility = lambda *_args, **_kwargs: None
    controller._update_contextual_toolbar_help = lambda: None

    toolbar_vm = ToolbarViewModel(
        actions={
            "plan": ToolbarActionView(visible=True, enabled=False),
            "lzk": ToolbarActionView(visible=True, enabled=True),
        }
    )

    visible_actions = controller._apply_toolbar_view_model(toolbar_vm)

    assert visible_actions == {"lzk"}
    assert plan_button.state_calls == [["disabled"]]
    assert lzk_button.state_calls == [["!disabled"]]
