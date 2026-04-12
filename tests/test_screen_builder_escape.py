from types import SimpleNamespace

from kursplaner.adapters.gui.screen_builder import ScreenBuilder


class _IntentSink:
    def __init__(self):
        self.calls = []

    def __call__(self, intent: str, **payload):
        self.calls.append((intent, payload))
        return "handled"


def test_escape_is_blocked_when_popup_is_active(monkeypatch):
    sink = _IntentSink()
    app = SimpleNamespace(_handle_ui_intent=sink)
    builder = ScreenBuilder(app)
    closed = {"value": False}

    monkeypatch.setattr(
        "kursplaner.adapters.gui.screen_builder.ScrollablePopupWindow.has_active_popup",
        staticmethod(lambda: True),
    )
    monkeypatch.setattr(
        "kursplaner.adapters.gui.screen_builder.ScrollablePopupWindow.close_active_popup",
        staticmethod(lambda: closed.__setitem__("value", True) or True),
    )

    result = builder._on_escape(object())

    assert result == "break"
    assert closed["value"] is True
    assert sink.calls == []


def test_escape_delegates_to_intent_when_no_popup_is_active(monkeypatch):
    sink = _IntentSink()
    app = SimpleNamespace(_handle_ui_intent=sink)
    builder = ScreenBuilder(app)

    monkeypatch.setattr(
        "kursplaner.adapters.gui.screen_builder.ScrollablePopupWindow.has_active_popup",
        staticmethod(lambda: False),
    )

    event = object()
    result = builder._on_escape(event)

    assert result == "handled"
    assert len(sink.calls) == 1
    assert sink.calls[0][0] == "shortcut.escape"
    assert sink.calls[0][1]["event"] is event
