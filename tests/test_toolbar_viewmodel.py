from kursplaner.adapters.gui.toolbar_viewmodel import build_toolbar_view_model
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


def test_toolbar_vm_keeps_new_and_refresh_visible():
    vm = build_toolbar_view_model(action_state=_state(), can_undo=False, can_redo=False)

    assert vm.actions["new"].visible is True
    assert vm.actions["refresh"].visible is True


def test_toolbar_vm_hides_context_actions_without_selection_state():
    vm = build_toolbar_view_model(action_state=_state(), can_undo=False, can_redo=False)

    disabled_keys = {
        "plan",
        "lzk",
        "lzk_expected_horizon",
        "extend_to_vacation",
        "ausfall",
        "hospitation",
        "mark_ub",
        "split",
        "merge",
        "move_left",
        "move_right",
        "clear",
        "find",
        "copy",
        "export_as",
        "rename",
        "paste",
        "undo",
        "redo",
    }
    for key in disabled_keys:
        assert vm.actions[key].visible is True
        assert vm.actions[key].enabled is False


def test_toolbar_vm_maps_fach_flags_1_to_1():
    vm = build_toolbar_view_model(
        action_state=_state(
            can_plan=True,
            can_lzk=True,
            can_extend_to_vacation=True,
            can_ausfall=True,
            can_hospitation=True,
            can_mark_ub=True,
            can_split=True,
            can_merge=True,
            can_move_left=True,
            can_move_right=True,
            can_clear=True,
            can_find=True,
            can_copy=True,
            can_paste=True,
            can_export_topic_pdf=True,
            can_export_lzk_expected_horizon=True,
        ),
        can_undo=True,
        can_redo=True,
    )

    enabled_keys = {
        "plan",
        "lzk",
        "lzk_expected_horizon",
        "extend_to_vacation",
        "ausfall",
        "hospitation",
        "mark_ub",
        "split",
        "merge",
        "move_left",
        "move_right",
        "clear",
        "find",
        "copy",
        "export_as",
        "rename",
        "paste",
        "undo",
        "redo",
    }
    for key in enabled_keys:
        assert vm.actions[key].visible is True
        assert vm.actions[key].enabled is True


def test_toolbar_vm_rename_follows_copy_rule():
    vm_hidden = build_toolbar_view_model(action_state=_state(can_copy=False), can_undo=False, can_redo=False)
    vm_shown = build_toolbar_view_model(action_state=_state(can_copy=True), can_undo=False, can_redo=False)

    assert vm_hidden.actions["rename"].visible is True
    assert vm_hidden.actions["rename"].enabled is False
    assert vm_shown.actions["rename"].visible is True
    assert vm_shown.actions["rename"].enabled is True


def test_toolbar_vm_undo_redo_follow_history_flags():
    vm = build_toolbar_view_model(action_state=_state(), can_undo=True, can_redo=False)

    assert vm.actions["undo"].visible is True
    assert vm.actions["undo"].enabled is True
    assert vm.actions["redo"].visible is True
    assert vm.actions["redo"].enabled is False


def test_toolbar_vm_all_actions_remain_visible():
    vm = build_toolbar_view_model(
        action_state=_state(can_plan=True, can_find=True, can_copy=True),
        can_undo=False,
        can_redo=True,
    )

    for view in vm.actions.values():
        assert view.visible is True
