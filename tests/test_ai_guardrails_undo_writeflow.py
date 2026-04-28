import ast

from tools.ci import check_ai_guardrails as guardrails


def _module(code: str) -> ast.Module:
    return ast.parse(code)


def test_undo_writeflow_guardrail_flags_direct_delete_apply_value(monkeypatch):
    ui_bad = _module(
        """
class MainWindowUiIntentController:
    def intent_grid_delete_cell(self):
        self.app.editor_controller.apply_value('inhalt', 0, '')
"""
    )
    action_good = _module(
        """
class MainWindowActionController:
    def clear_selected_lesson_content(self):
        self._run_tracked_write(label='x', action=lambda: None, extra_after_from_result=lambda item: [])

    def paste_copied_lesson(self):
        self._ask_paste_ub_copy_mode(None)
        self._run_tracked_write(label='x', action=lambda: None)
"""
    )

    def _fake_parse_module(rel_path: str, errors: list[str]):
        if rel_path.endswith("ui_intent_controller.py"):
            return ui_bad
        if rel_path.endswith("action_controller.py"):
            return action_good
        return None

    monkeypatch.setattr(guardrails, "_parse_module", _fake_parse_module)

    errors: list[str] = []
    guardrails._check_undo_writeflow_guardrails(errors)

    assert any("intent_grid_delete_cell must not call" in item for item in errors)


def test_undo_writeflow_guardrail_accepts_tracked_flow(monkeypatch):
    ui_good = _module(
        """
class MainWindowUiIntentController:
    def intent_grid_delete_cell(self):
        return self._set_selected_cell_value('')
"""
    )
    action_good = _module(
        """
class MainWindowActionController:
    def clear_selected_lesson_content(self):
        self._run_tracked_write(label='x', action=lambda: None, extra_after_from_result=lambda item: [])

    def paste_copied_lesson(self):
        self._ask_paste_ub_copy_mode(None)
        self._run_tracked_write(label='x', action=lambda: None)
"""
    )

    def _fake_parse_module(rel_path: str, errors: list[str]):
        if rel_path.endswith("ui_intent_controller.py"):
            return ui_good
        if rel_path.endswith("action_controller.py"):
            return action_good
        return None

    monkeypatch.setattr(guardrails, "_parse_module", _fake_parse_module)

    errors: list[str] = []
    guardrails._check_undo_writeflow_guardrails(errors)

    assert errors == []
