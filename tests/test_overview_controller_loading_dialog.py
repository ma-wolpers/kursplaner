from types import SimpleNamespace

from kursplaner.adapters.gui.overview_controller import MainWindowOverviewController
from kursplaner.adapters.gui.screen_builder import ScreenBuilder


class _FakeWidget:
    """Stand-in for ttk widgets so no real Tk interpreter is required."""

    def __init__(self, *_args, **_kwargs):
        """Accept and discard any ttk widget constructor arguments."""
        pass

    def pack(self, *_args, **_kwargs):
        """No-op replacement for the real geometry-manager call."""
        return None

    def start(self, *_args, **_kwargs):
        """No-op replacement for Progressbar.start()."""
        return None

    def stop(self, *_args, **_kwargs):
        """No-op replacement for Progressbar.stop()."""
        return None


class _FakeToplevel:
    """Stand-in for ui.Toplevel matching the interface the loading dialog needs."""

    def __init__(self, *_args, **_kwargs):
        """Accept any Toplevel constructor arguments and start out "existing"."""
        self._exists = True

    def __str__(self):
        """Return a fixed Tk widget-path-like id."""
        return ".fake-loading-dialog"

    def title(self, *_args, **_kwargs):
        """Return the fixed window title, mirroring Tk's title() getter/setter shape."""
        return "Lade Kurs"

    def transient(self, *_args, **_kwargs):
        """No-op replacement for Toplevel.transient()."""
        return None

    def resizable(self, *_args, **_kwargs):
        """No-op replacement for Toplevel.resizable()."""
        return None

    def geometry(self, *_args, **_kwargs):
        """No-op replacement for Toplevel.geometry()."""
        return None

    def protocol(self, *_args, **_kwargs):
        """No-op replacement for Toplevel.protocol() (e.g. WM_DELETE_WINDOW)."""
        return None

    def update_idletasks(self):
        """No-op replacement for Toplevel.update_idletasks()."""
        return None

    def winfo_exists(self):
        """Return whether destroy() has been called yet, like the real Tk check."""
        return self._exists

    def destroy(self):
        """Mark the fake window as destroyed."""
        self._exists = False


def test_loading_dialog_is_registered_as_non_modal(monkeypatch):
    """Assert _show_loading_dialog registers its window as a non-modal overlay.

    The loading hint must never block the main window's shortcuts or swallow Escape
    (the original bug, from the time a toplevel scan auto-classified unknown windows as
    blocking). It registers in the bw-gui overlay stack as ``NON_MODAL_POPUP`` through
    ``ScreenBuilder._register_non_modal_window``; the real gating is covered with a Tk
    interpreter in ``test_overlay_gating_tk.py``.
    """
    monkeypatch.setattr("kursplaner.adapters.gui.overview_controller.ui.Toplevel", _FakeToplevel)
    monkeypatch.setattr("kursplaner.adapters.gui.overview_controller.widgets.Frame", _FakeWidget)
    monkeypatch.setattr("kursplaner.adapters.gui.overview_controller.widgets.Label", _FakeWidget)
    monkeypatch.setattr("kursplaner.adapters.gui.overview_controller.widgets.Progressbar", _FakeWidget)

    screen_builder_app = SimpleNamespace(bind_all=lambda *args, **kwargs: None)
    screen_builder = ScreenBuilder(screen_builder_app)
    tracked_calls = []
    screen_builder._register_non_modal_window = tracked_calls.append
    app = SimpleNamespace(screen_builder=screen_builder, update_idletasks=lambda: None)

    close_loading = MainWindowOverviewController._show_loading_dialog(SimpleNamespace(app=app), "Kursplan wird geladen …")

    assert len(tracked_calls) == 1
    assert isinstance(tracked_calls[0], _FakeToplevel)

    close_loading()
