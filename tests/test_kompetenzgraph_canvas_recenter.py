"""Tests für die Recenter-Geometrie (`kompetenzgraph_canvas_recenter.py`).

Nutzt bewusst einen echten `tk.Canvas` (über die session-weite `tk_root`-
Fixture aus `tests/conftest.py`) statt eines Fakes -- `canvas.bbox()`,
`canvas.canvasx()`/`canvas.canvasy()` und `canvas.scale()` sind reines
Tcl/Tk-Verhalten, das ein Stub nur unzuverlässig nachbilden könnte (siehe
`test_kompetenzgraph_canvas_zoom_pan_labels.py` für dasselbe Muster).
"""

from __future__ import annotations

import tkinter as tk

from kursplaner.adapters.gui.kompetenzgraph_canvas_recenter import (
    is_node_fully_visible,
    recenter_on_selection,
    recenter_on_selection_if_offscreen,
)
from kursplaner.adapters.gui.kompetenzgraph_canvas_render import NODE_TAG_PREFIX

_TAG = f"{NODE_TAG_PREFIX}A"


def _make_canvas(tk_root, *, width: int = 400, height: int = 300) -> tk.Canvas:
    """Baut einen Canvas mit verlässlich korrekter, tatsächlich zugewiesener Größe.

    Eigenes `Toplevel` statt direktem Packen in die session-weite `tk_root` --
    mehrere Tests würden sich sonst denselben, in der Fixture fest auf
    "400x300" GEOMETRIE-fixierten Root teilen und könnten sich gegenseitig
    beim Platz für `winfo_width()`/`winfo_height()` verdrängen. `update()`
    (nicht nur `update_idletasks()`) ist nötig, damit der Geometrie-Manager
    die reale Größe tatsächlich zuteilt -- ein ungemapptes Widget liefert
    sonst den Tk-Platzhalterwert `1`. `highlightthickness=0`/`bd=0` verhindert
    einen Rahmen-Offset, der `canvasx(0)` sonst leicht von `0` verschieben würde.
    """
    toplevel = tk.Toplevel(tk_root)
    toplevel.geometry(f"{width}x{height}+3000+3000")
    canvas = tk.Canvas(toplevel, width=width, height=height, highlightthickness=0, bd=0)
    canvas.pack(fill="both", expand=True)
    toplevel.update()
    return canvas


def test_is_node_fully_visible_true_for_node_within_viewport(tk_root):
    canvas = _make_canvas(tk_root)
    canvas.create_rectangle(50, 50, 100, 100, tags=(_TAG,))

    assert is_node_fully_visible(canvas, _TAG) is True


def test_is_node_fully_visible_false_for_node_outside_viewport(tk_root):
    canvas = _make_canvas(tk_root)
    canvas.create_rectangle(5000, 5000, 5050, 5050, tags=(_TAG,))

    assert is_node_fully_visible(canvas, _TAG) is False


def test_is_node_fully_visible_false_for_node_only_partially_visible(tk_root):
    canvas = _make_canvas(tk_root, width=200, height=200)
    canvas.create_rectangle(180, 180, 260, 260, tags=(_TAG,))

    assert is_node_fully_visible(canvas, _TAG) is False


def test_is_node_fully_visible_false_when_tag_has_no_item(tk_root):
    canvas = _make_canvas(tk_root)

    assert is_node_fully_visible(canvas, _TAG) is False


def test_recenter_on_selection_is_noop_when_nothing_selected(tk_root):
    canvas = _make_canvas(tk_root)
    canvas.create_rectangle(50, 50, 100, 100, tags=(_TAG,))
    canvas.configure(scrollregion=(0, 0, 1000, 1000))

    recenter_on_selection(canvas, None)  # darf nicht werfen, kein Knoten zu zentrieren


def test_recenter_on_selection_if_offscreen_scrolls_only_when_needed(tk_root):
    canvas = _make_canvas(tk_root, width=200, height=200)
    canvas.create_rectangle(50, 50, 100, 100, tags=(_TAG,))
    canvas.configure(scrollregion=(0, 0, 1000, 1000))

    initial_view = canvas.xview()
    recenter_on_selection_if_offscreen(canvas, "A")

    assert canvas.xview() == initial_view  # Knoten war sichtbar -- keine Scroll-Aenderung

    canvas.delete(_TAG)
    canvas.create_rectangle(5000, 5000, 5050, 5050, tags=(_TAG,))
    recenter_on_selection_if_offscreen(canvas, "A")

    assert canvas.xview() != initial_view  # Knoten war ausserhalb -- Scroll-Position musste sich aendern
