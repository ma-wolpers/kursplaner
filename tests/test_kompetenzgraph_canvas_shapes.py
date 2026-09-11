"""Tests für `kompetenzgraph_canvas_shapes.py` (Rounded-Rect-Rendering + Andockpunkt-Geometrie)."""

from __future__ import annotations

import tkinter as tk

from kursplaner.adapters.gui.kompetenzgraph_canvas_shapes import create_rounded_rectangle, ray_rectangle_intersection


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


# --- ray_rectangle_intersection() -- reine Geometrie, kein Canvas nötig ---


def test_intersection_straight_right_hits_the_right_edge():
    x, y = ray_rectangle_intersection(0.0, 0.0, 100.0, 0.0, half_width=50.0, half_height=30.0)
    assert (x, y) == (50.0, 0.0)


def test_intersection_straight_left_hits_the_left_edge():
    x, y = ray_rectangle_intersection(0.0, 0.0, -100.0, 0.0, half_width=50.0, half_height=30.0)
    assert (x, y) == (-50.0, 0.0)


def test_intersection_straight_up_hits_the_top_edge():
    x, y = ray_rectangle_intersection(0.0, 0.0, 0.0, -100.0, half_width=50.0, half_height=30.0)
    assert (x, y) == (0.0, -30.0)


def test_intersection_straight_down_hits_the_bottom_edge():
    x, y = ray_rectangle_intersection(0.0, 0.0, 0.0, 100.0, half_width=50.0, half_height=30.0)
    assert (x, y) == (0.0, 30.0)


def test_intersection_diagonal_toward_a_far_corner_exits_via_the_shorter_axis():
    """45°-Richtung, aber Rechteck ist breiter als hoch -- der Strahl verlässt zuerst über die
    Höhen-Kante (y=±half_height), nicht über die Breiten-Kante."""
    x, y = ray_rectangle_intersection(0.0, 0.0, 100.0, 100.0, half_width=50.0, half_height=30.0)
    assert (x, y) == (30.0, 30.0)
    assert abs(x) <= 50.0  # bleibt innerhalb der Breite -- Kontrolle, dass die richtige Kante gewählt wurde


def test_intersection_diagonal_in_each_quadrant_stays_within_the_rectangle_bounds():
    for toward_x, toward_y in ((100.0, 50.0), (-100.0, 50.0), (-100.0, -50.0), (100.0, -50.0)):
        x, y = ray_rectangle_intersection(0.0, 0.0, toward_x, toward_y, half_width=50.0, half_height=30.0)
        assert -50.0 <= x <= 50.0
        assert -30.0 <= y <= 30.0
        # mindestens eine Koordinate liegt exakt auf dem Rand (der Strahl trifft eine Kante)
        assert abs(abs(x) - 50.0) < 1e-9 or abs(abs(y) - 30.0) < 1e-9


def test_intersection_toward_the_center_itself_returns_the_center():
    """Entartungsfall: `toward_point == center` -- keine Division durch Null, sondern der Mittelpunkt selbst."""
    x, y = ray_rectangle_intersection(5.0, 7.0, 5.0, 7.0, half_width=50.0, half_height=30.0)
    assert (x, y) == (5.0, 7.0)
