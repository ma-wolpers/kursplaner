from types import SimpleNamespace

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

    monkeypatch.setattr(
        "kursplaner.adapters.gui.screen_builder.ScrollablePopupWindow.has_active_popup",
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

    monkeypatch.setattr(
        "kursplaner.adapters.gui.screen_builder.ScrollablePopupWindow.has_active_popup",
        staticmethod(lambda: False),
    )

    event = object()
    result = builder._on_ctrl_enter(event)

    assert result == "handled"
    assert sink.calls[0][0] == UiIntent.SHORTCUT_COMMIT_EDIT
    assert sink.calls[0][1]["event"] is event
