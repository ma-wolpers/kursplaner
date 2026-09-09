"""Tests für die zoomabhängige Label-Sichtbarkeit (`KompetenzGraphCanvasZoomPan`).

Nutzt bewusst einen echten `tk.Canvas` (über die session-weite `tk_root`-
Fixture aus `tests/conftest.py`) statt eines Fakes -- `canvas.scale()`,
`canvas.itemcget()`/`itemconfigure()` mit Tag-Adressierung sind reines
Tcl/Tk-Verhalten, das ein Stub nur unzuverlässig nachbilden könnte.
"""

from __future__ import annotations

import tkinter as tk

from kursplaner.adapters.gui.kompetenzgraph_canvas_render import LABEL_TAG
from kursplaner.adapters.gui.kompetenzgraph_canvas_zoom_pan import KompetenzGraphCanvasZoomPan


def test_labels_hidden_below_threshold_and_shown_again_above(tk_root):
    canvas = tk.Canvas(tk_root)
    label_item = canvas.create_text(10, 10, text="Label", tags=(LABEL_TAG,))
    zoom_pan = KompetenzGraphCanvasZoomPan(canvas)
    assert canvas.itemcget(label_item, "state") != "hidden"  # Tk-Default ist "" (== sichtbar), nicht literal "normal"

    for _ in range(20):  # reichlich Schritte, um sicher unter die Schwelle zu fallen (Skalierung ist geclampt)
        zoom_pan._zoom_out()

    assert canvas.itemcget(label_item, "state") == "hidden"

    for _ in range(20):  # und wieder sicher darüber
        zoom_pan._zoom_in()

    assert canvas.itemcget(label_item, "state") == "normal"


def test_no_redundant_itemconfigure_calls_within_same_zoom_state(tk_root):
    canvas = tk.Canvas(tk_root)
    canvas.create_text(10, 10, text="Label", tags=(LABEL_TAG,))
    zoom_pan = KompetenzGraphCanvasZoomPan(canvas)

    call_count = [0]
    original_itemconfigure = canvas.itemconfigure

    def _counting_itemconfigure(*args, **kwargs):
        call_count[0] += 1
        return original_itemconfigure(*args, **kwargs)

    canvas.itemconfigure = _counting_itemconfigure

    for _ in range(20):
        zoom_pan._zoom_out()

    # Genau EIN tatsächlicher Schwellen-Übergang -- keine wiederholten
    # Reconfigure-Aufrufe für jeden einzelnen Zoom-Tick im selben Zustand.
    assert call_count[0] == 1


def test_reapply_label_visibility_restores_hidden_state_after_simulated_redraw(tk_root):
    canvas = tk.Canvas(tk_root)
    label_item = canvas.create_text(10, 10, text="Label", tags=(LABEL_TAG,))
    zoom_pan = KompetenzGraphCanvasZoomPan(canvas)
    for _ in range(20):
        zoom_pan._zoom_out()
    assert canvas.itemcget(label_item, "state") == "hidden"

    # Simuliert einen vollen Canvas-Redraw (`KompetenzGraphCanvasRenderer.render()`:
    # `canvas.delete("all")` + Neuerzeugung aller Items) -- ein neu erzeugtes
    # Textitem startet unabhängig von der aktuellen Zoomstufe im Default-Zustand.
    canvas.delete("all")
    new_label_item = canvas.create_text(20, 20, text="Label", tags=(LABEL_TAG,))
    assert canvas.itemcget(new_label_item, "state") != "hidden"  # Tk-Default ist "" (== sichtbar)

    zoom_pan.reapply_label_visibility()

    assert canvas.itemcget(new_label_item, "state") == "hidden"


def test_reapply_label_visibility_is_noop_when_labels_were_never_hidden(tk_root):
    canvas = tk.Canvas(tk_root)
    label_item = canvas.create_text(10, 10, text="Label", tags=(LABEL_TAG,))
    zoom_pan = KompetenzGraphCanvasZoomPan(canvas)

    zoom_pan.reapply_label_visibility()

    assert canvas.itemcget(label_item, "state") == "normal"
