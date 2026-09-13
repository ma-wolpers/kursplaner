"""Konstruktions-Regressionstest für `SearchOverlayView`.

Nutzt einen echten Tk-Parent (`tk_root`-Fixture) statt eines Stubs: der Konstruktor von
`RegexEntryField` (bw-gui) ruft synchron `on_change` auf (Initial-Kompilierung für die
Rahmenfarbe), was bei falscher Attribut-Reihenfolge in `SearchOverlayView.__init__` zu einem
`AttributeError` führt -- ein reiner Quelltext-/Stub-Test hätte das nicht gefangen (siehe
Implementierungsplan-Nachtrag: dieser Fehler ging beim ersten Umsetzungsdurchlauf erst beim
tatsächlichen App-Start auf, nicht in der Testsuite).
"""

from __future__ import annotations

import tkinter as tk
from types import SimpleNamespace

from kursplaner.adapters.gui.search_controller import MainWindowSearchController
from kursplaner.adapters.gui.search_overlay_view import SearchOverlayView
from kursplaner.adapters.gui.search_state import SearchOverlayState


def _build_app_stub() -> SimpleNamespace:
    app = SimpleNamespace(search_state=SearchOverlayState(), day_columns=[])
    app.search_controller = MainWindowSearchController(app)
    return app


def test_construction_does_not_raise(tk_root):
    """Reproduziert exakt den App-Start-Pfad: `RegexEntryField`s Konstruktor feuert `on_change`
    synchron, noch bevor `SearchOverlayView.__init__` zurückkehrt."""
    toplevel = tk.Toplevel(tk_root)
    app = _build_app_stub()

    view = SearchOverlayView(app, toplevel)

    assert view._status_label.cget("text") == ""


def test_show_resets_field_and_status(tk_root):
    toplevel = tk.Toplevel(tk_root)
    app = _build_app_stub()
    view = SearchOverlayView(app, toplevel)
    view._field.set_text("alt")

    view.show()

    assert view._field.get_text() == ""
    assert view._status_label.cget("text") == ""


def test_typing_updates_status_label_via_search_controller(tk_root):
    toplevel = tk.Toplevel(tk_root)
    app = _build_app_stub()
    view = SearchOverlayView(app, toplevel)

    view._field.set_text("nicht[gueltig")  # ungueltiges Regex

    assert view._status_label.cget("text") == "Ungültiger Ausdruck"
