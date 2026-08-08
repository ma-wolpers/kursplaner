from types import SimpleNamespace

from kursplaner.adapters.gui.ui_intent_controller import MainWindowUiIntentController, ui


def _make_controller(*, focused):
    """Build a MainWindowUiIntentController with a minimal fake app for focus tests."""
    ui_state = SimpleNamespace(active_editor=SimpleNamespace(field_key="Inhalt", day_index=0))
    app = SimpleNamespace(ui_state=ui_state, focus_get=lambda: focused)
    return MainWindowUiIntentController(app)


def test_global_click_commit_resets_grid_focus_when_target_not_editable():
    """Clicking a non-editable widget (e.g. a toolbar button) must reclaim grid focus.

    Regression test: leaving focus dangling on the just-committed cell's Text widget
    caused Ctrl+Z to be silently blocked afterwards (evaluate_runtime saw a text
    input still focused), even though editing had already ended.
    """
    focused_cell = ui.Text.__new__(ui.Text)
    controller = _make_controller(focused=focused_cell)
    calls = []
    controller._leave_edit_mode_to_cell = lambda *, set_grid_focus: calls.append(set_grid_focus)

    clicked_button = object()
    event = SimpleNamespace(widget=clicked_button)

    result = controller.intent_global_click_commit_cell(event)

    assert result is None
    assert calls == [True]


def test_global_click_commit_preserves_focus_when_target_is_editable():
    """Clicking into another editable widget must not steal its just-assigned focus."""
    focused_cell = ui.Text.__new__(ui.Text)
    controller = _make_controller(focused=focused_cell)
    calls = []
    controller._leave_edit_mode_to_cell = lambda *, set_grid_focus: calls.append(set_grid_focus)

    clicked_entry = ui.Entry.__new__(ui.Entry)
    event = SimpleNamespace(widget=clicked_entry)

    result = controller.intent_global_click_commit_cell(event)

    assert result is None
    assert calls == [False]
