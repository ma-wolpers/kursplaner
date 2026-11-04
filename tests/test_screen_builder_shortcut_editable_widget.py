from types import SimpleNamespace

from bw_gui.contracts import KeySpec
from bw_gui.contracts.events import EventResult

from kursplaner.adapters.gui.screen_builder import ScreenBuilder


class _IntentSink:
    def __init__(self):
        self.calls = []

    def __call__(self, intent: str, **payload):
        self.calls.append((intent, payload))
        return "handled"


def _entry(intent: str, *, from_shortcut: bool = True, payload: dict | None = None):
    return SimpleNamespace(
        key=KeySpec.parse("Ctrl+Left"),
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
    builder._shortcut_dialog_open = lambda: False  # kein Tk-Interpreter: Overlay-Stack leer

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
    builder._shortcut_dialog_open = lambda: False  # kein Tk-Interpreter: Overlay-Stack leer

    monkeypatch.setattr(builder, "_is_editable_widget", lambda _widget: True)

    handler = builder._build_shortcut_handler(_entry("shortcut.copy", payload={"x": 1}))
    event = SimpleNamespace(widget=object())

    result = handler(event)

    assert result == "handled"
    assert len(sink.calls) == 1
    intent, payload = sink.calls[0]
    assert intent == "shortcut.copy"
    assert payload["from_shortcut"] is True


def test_shortcut_handler_blocks_only_for_blocking_overlays(monkeypatch):
    """Ein offenes nicht-modales Werkzeugfenster (Kompetenznetz, Sequenzleiter) legt das
    Hauptfenster nicht mehr lahm; modale Dialoge/Menüs (``dialog_open``) sperren weiter."""
    sink = _IntentSink()
    app = SimpleNamespace(_handle_ui_intent=sink)
    builder = ScreenBuilder(app)
    builder._shortcut_dialog_open = lambda: False  # kein Tk-Interpreter: Overlay-Stack leer
    monkeypatch.setattr(
        "kursplaner.adapters.gui.popup_window.ScrollablePopupWindow.has_active_popup",
        staticmethod(lambda: True),
    )
    handler = builder._build_shortcut_handler(_entry("detail.open_column_visibility_settings"))

    handler(SimpleNamespace(widget=object()))
    assert [call[0] for call in sink.calls] == ["detail.open_column_visibility_settings"]

    sink.calls.clear()
    builder._shortcut_dialog_open = lambda: True
    assert handler(SimpleNamespace(widget=object())) is EventResult.HANDLED
    assert sink.calls == []
