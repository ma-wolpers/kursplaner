"""Tests für `kompetenzgraph_canvas_shapes.py` (Andockpunkt-Geometrie; abgerundete Rechtecke testet bw-gui)."""

from __future__ import annotations

from kursplaner.adapters.gui.kompetenzgraph_canvas_shapes import ray_rectangle_intersection

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
