"""Tests für `create_rounded_rectangle` -- nutzt einen echten `tk.Canvas` (siehe `tests/conftest.py::tk_root`)."""

from __future__ import annotations

import tkinter as tk

from kursplaner.adapters.gui.kompetenzgraph_canvas_shapes import create_rounded_rectangle


def test_create_rounded_rectangle_returns_a_polygon_item(tk_root):
    canvas = tk.Canvas(tk_root)

    item_id = create_rounded_rectangle(canvas, 0, 0, 100, 40, radius=12.0, fill="#FFFFFF")

    assert canvas.type(item_id) == "polygon"


def test_oversized_radius_is_capped_without_crashing(tk_root):
    """Ein Radius größer als die halbe Höhe darf nicht crashen oder die Box aufblähen (Regel 7 aus dem Redesign-Plan)."""
    canvas = tk.Canvas(tk_root)

    item_id = create_rounded_rectangle(canvas, 0, 0, 200, 20, radius=50.0)

    bbox = canvas.bbox(item_id)
    assert bbox is not None
    assert bbox[2] - bbox[0] <= 202  # keine spürbare Ausdehnung über die angegebene Breite hinaus
    assert bbox[3] - bbox[1] <= 22


def test_passes_through_kwargs_like_fill_and_tags(tk_root):
    canvas = tk.Canvas(tk_root)

    item_id = create_rounded_rectangle(canvas, 0, 0, 60, 30, tags=("my-tag",))

    assert "my-tag" in canvas.gettags(item_id)
