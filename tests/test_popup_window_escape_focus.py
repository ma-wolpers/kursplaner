from types import SimpleNamespace

from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow


class _FakeEditable:
    pass


class _FakePopup:
    def __init__(self, focused_widget, is_descendant: bool):
        self._focused_widget = focused_widget
        self._is_descendant = is_descendant
        self.focus_force_calls = 0
        self.request_close_calls = 0

    def focus_get(self):
        return self._focused_widget

    def _is_descendant_of_popup(self, _widget):
        return self._is_descendant

    def focus_force(self):
        self.focus_force_calls += 1

    def _request_close(self):
        self.request_close_calls += 1
        return "break"


def test_escape_with_text_focus_only_lifts_focus(monkeypatch):
    popup = _FakePopup(focused_widget=_FakeEditable(), is_descendant=True)

    monkeypatch.setattr(ScrollablePopupWindow, "_is_editable_widget", staticmethod(lambda widget: True))

    result = ScrollablePopupWindow._handle_escape_request(popup)

    assert result == "break"
    assert popup.focus_force_calls == 1
    assert popup.request_close_calls == 0


def test_escape_with_popup_focus_closes_popup(monkeypatch):
    popup = _FakePopup(focused_widget=SimpleNamespace(), is_descendant=True)

    monkeypatch.setattr(ScrollablePopupWindow, "_is_editable_widget", staticmethod(lambda widget: False))

    result = ScrollablePopupWindow._handle_escape_request(popup)

    assert result == "break"
    assert popup.focus_force_calls == 0
    assert popup.request_close_calls == 1
