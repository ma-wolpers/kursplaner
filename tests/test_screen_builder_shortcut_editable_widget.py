from types import SimpleNamespace

from kursplaner.adapters.gui.screen_builder import ScreenBuilder


class _IntentSink:
    def __init__(self):
        self.calls = []

    def __call__(self, intent: str, **payload):
        self.calls.append((intent, payload))
        return "handled"


def _entry(intent: str, *, from_shortcut: bool = True, payload: dict | None = None):
    return SimpleNamespace(
        key_sequence="<Control-Left>",
        display_shortcut="Strg+Links",
        action_label="Dummy",
        intent=intent,
        from_shortcut=from_shortcut,
        payload={} if payload is None else payload,
    )


def test_toolbar_shortcut_is_ignored_in_editable_widget(monkeypatch):
    sink = _IntentSink()
    app = SimpleNamespace(_handle_ui_intent=sink)
    builder = ScreenBuilder(app)

    monkeypatch.setattr(builder, "_is_editable_widget", lambda _widget: True)

    handler = builder._build_shortcut_handler(_entry("toolbar.move_columns", payload={"direction": -1}))
    event = SimpleNamespace(widget=object())

    result = handler(event)

    assert result is None
    assert sink.calls == []


def test_non_toolbar_shortcut_still_delegates_in_editable_widget(monkeypatch):
    sink = _IntentSink()
    app = SimpleNamespace(_handle_ui_intent=sink)
    builder = ScreenBuilder(app)

    monkeypatch.setattr(builder, "_is_editable_widget", lambda _widget: True)

    handler = builder._build_shortcut_handler(_entry("shortcut.copy", payload={"x": 1}))
    event = SimpleNamespace(widget=object())

    result = handler(event)

    assert result == "handled"
    assert len(sink.calls) == 1
    intent, payload = sink.calls[0]
    assert intent == "shortcut.copy"
    assert payload["from_shortcut"] is True


def test_shortcut_handler_blocks_when_popup_is_active(monkeypatch):
    sink = _IntentSink()
    app = SimpleNamespace(_handle_ui_intent=sink)
    builder = ScreenBuilder(app)

    monkeypatch.setattr(
        "kursplaner.adapters.gui.screen_builder.ScrollablePopupWindow.has_active_popup",
        staticmethod(lambda: True),
    )

    handler = builder._build_shortcut_handler(_entry("detail.open_column_visibility_settings"))
    result = handler(SimpleNamespace(widget=object()))

    assert result == "break"
    assert sink.calls == []
