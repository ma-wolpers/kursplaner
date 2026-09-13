"""Konstruktions-Regressionstest fuer `KompetenzGraphTextSearchPanel`.

Analog zu `test_search_overlay_view.py`: baut das Panel in einem echten Tk-Parent statt
gegen einen Stub, um Konstruktions-Reihenfolge-Fehler zu fangen, die ein reiner Quelltext-Test
nicht sieht. Dieses Panel verkabelt bewusst KEIN `on_change` an `RegexEntryField` (Teil-B-Design:
Suche nur auf Buttondruck), ist also von der Klasse Bug, die `search_overlay_view.py` hatte,
strukturell nicht betroffen -- hier trotzdem verifiziert statt nur angenommen.
"""

from __future__ import annotations

import tkinter as tk

from kursplaner.adapters.gui.kompetenzgraph_text_search_panel import KompetenzGraphTextSearchPanel
from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphFilter


def test_construction_does_not_raise(tk_root):
    toplevel = tk.Toplevel(tk_root)
    calls = []

    panel = KompetenzGraphTextSearchPanel(
        toplevel, initial_filter=KompetenzGraphFilter(), on_search=lambda *args: calls.append(args)
    )

    assert panel._field.get_text() == ""


def test_trigger_search_invokes_callback_with_current_field_and_toggle_state(tk_root):
    toplevel = tk.Toplevel(tk_root)
    calls = []
    panel = KompetenzGraphTextSearchPanel(
        toplevel, initial_filter=KompetenzGraphFilter(), on_search=lambda *args: calls.append(args)
    )
    panel._field.set_text("Vektor")
    panel._beispiel_var.set(False)

    panel._trigger_search()

    assert len(calls) == 1
    text, pattern, kc, titel, beispiel, rest = calls[0]
    assert text == "Vektor"
    assert pattern is not None
    assert beispiel is False
