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


def test_reapply_zoom_restores_visual_scale_after_simulated_redraw(tk_root):
    """Kernregression für den Zoom-Reset-Bug: `_scale` überlebt ein volles Redraw (`canvas.delete("all")`
    + Neuerzeugung bei rohen 1:1-Koordinaten), UND `reapply_zoom()` bringt die Darstellung wieder
    auf die gehaltene Skalierung -- ohne das bleibt der Zoom nur optisch verloren, während `_scale`
    unverändert (fälschlich) am Limit steht."""
    canvas = tk.Canvas(tk_root)
    zoom_pan = KompetenzGraphCanvasZoomPan(canvas)
    canvas.create_rectangle(0, 0, 100, 100, tags=("node",))
    zoom_pan._zoom_in()
    zoom_pan._zoom_in()
    scale_before_redraw = zoom_pan._scale

    # Simuliert einen vollen Canvas-Redraw: Items werden an rohen (unskalierten) Koordinaten neu erzeugt.
    canvas.delete("all")
    canvas.create_rectangle(0, 0, 100, 100, tags=("node",))
    raw_bbox = canvas.bbox("node")

    zoom_pan.reapply_zoom()

    assert zoom_pan._scale == scale_before_redraw  # _scale bleibt unverändert, wird nie zurückgesetzt
    scaled_bbox = canvas.bbox("node")
    assert scaled_bbox != raw_bbox  # die Darstellung wurde tatsächlich wieder skaliert


def test_reapply_zoom_is_noop_at_default_scale(tk_root):
    canvas = tk.Canvas(tk_root)
    zoom_pan = KompetenzGraphCanvasZoomPan(canvas)
    canvas.create_rectangle(0, 0, 100, 100, tags=("node",))
    bbox_before = canvas.bbox("node")

    zoom_pan.reapply_zoom()

    assert canvas.bbox("node") == bbox_before


def test_reapply_zoom_does_not_block_further_zoom_out_after_redraw(tk_root):
    """Regressionstest für das ursprüngliche Symptom: nach mehrfachem Rauszoomen, simuliertem
    Redraw und `reapply_zoom()` muss weiteres Rauszoomen weiterhin möglich sein -- `_scale` darf
    nicht durch das Redraw fälschlich am Minimum hängen bleiben."""
    canvas = tk.Canvas(tk_root)
    zoom_pan = KompetenzGraphCanvasZoomPan(canvas)
    canvas.create_rectangle(0, 0, 100, 100, tags=("node",))
    zoom_pan._zoom_out()
    scale_after_first_zoom_out = zoom_pan._scale

    canvas.delete("all")
    canvas.create_rectangle(0, 0, 100, 100, tags=("node",))
    zoom_pan.reapply_zoom()

    zoom_pan._zoom_out()
    assert zoom_pan._scale < scale_after_first_zoom_out
