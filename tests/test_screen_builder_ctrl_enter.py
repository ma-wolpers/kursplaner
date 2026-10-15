from types import SimpleNamespace

from bw_libs.ui_contract.keybinding import (
    UI_MODE_EDITOR,
    UI_MODE_PREVIEW,
    KeyBindingDefinition,
    KeybindingRegistry,
    KeybindingRuntimeContext,
)

from kursplaner.adapters.gui.screen_builder import ScreenBuilder
from kursplaner.adapters.gui.ui_intents import UiIntent


class _IntentSink:
    def __init__(self):
        self.calls = []

    def __call__(self, intent: str, **payload):
        self.calls.append((intent, payload))
        return "handled"


def test_ctrl_enter_emits_column_intent_in_column_mode(monkeypatch):
    sink = _IntentSink()
    ui_state = SimpleNamespace(selection_level="column", SELECTION_LEVEL_COLUMN="column")
    app = SimpleNamespace(_handle_ui_intent=sink, ui_state=ui_state)
    builder = ScreenBuilder(app)
    builder._shortcut_dialog_open = lambda: False  # kein Tk-Interpreter: Overlay-Stack leer

    monkeypatch.setattr(
        "kursplaner.adapters.gui.popup_window.ScrollablePopupWindow.has_active_popup",
        staticmethod(lambda: False),
    )

    event = object()
    result = builder._on_ctrl_enter(event)

    assert result == "handled"
    assert sink.calls[0][0] == UiIntent.SHORTCUT_COMMIT_COLUMN
    assert sink.calls[0][1]["event"] is event


def test_ctrl_enter_emits_edit_intent_outside_column_mode(monkeypatch):
    sink = _IntentSink()
    ui_state = SimpleNamespace(selection_level="cell", SELECTION_LEVEL_COLUMN="column")
    app = SimpleNamespace(_handle_ui_intent=sink, ui_state=ui_state)
    builder = ScreenBuilder(app)
    builder._shortcut_dialog_open = lambda: False  # kein Tk-Interpreter: Overlay-Stack leer

    monkeypatch.setattr(
        "kursplaner.adapters.gui.popup_window.ScrollablePopupWindow.has_active_popup",
        staticmethod(lambda: False),
    )

    event = object()
    result = builder._on_ctrl_enter(event)

    assert result == "handled"
    assert sink.calls[0][0] == UiIntent.SHORTCUT_COMMIT_EDIT
    assert sink.calls[0][1]["event"] is event


def test_ctrl_enter_binding_is_active_while_editing_a_cell():
    """Regression test: Ctrl+Enter must reach the handler while a cell is being edited.

    Editing a grid cell focuses its ui.Text widget, which flips the runtime shortcut
    context to UI_MODE_EDITOR. The production binding previously only declared
    modes=(UI_MODE_PREVIEW,), so evaluate_runtime rejected the shortcut purely on the
    mode check before allow_when_text_input was ever consulted, and the commit-edit
    handler was never reached.
    """
    builder = ScreenBuilder(SimpleNamespace())
    rows = [row for row in builder._shortcut_rows() if row.binding_id == "grid.commit.ctrl-enter"]
    assert len(rows) == 1
    row = rows[0]
    definition = KeyBindingDefinition(
        binding_id=row.binding_id,
        keys=row.keys,
        intent=row.intent,
        modes=row.modes,
        allow_when_text_input=row.allow_when_text_input,
    )
    registry = KeybindingRegistry()
    registry.register(definition)

    editor_context = KeybindingRuntimeContext(active_mode=UI_MODE_EDITOR, text_input_focused=True)
    can_execute, reason = registry.evaluate_runtime(definition, editor_context)
    assert can_execute is True, reason

    preview_context = KeybindingRuntimeContext(active_mode=UI_MODE_PREVIEW, text_input_focused=False)
    can_execute, reason = registry.evaluate_runtime(definition, preview_context)
    assert can_execute is True, reason
