import math

from kursplaner.core.domain.kompetenzgraph_arrow_navigation import (
    DIRECTION_VECTORS,
    find_nearest_node_in_direction,
)

_EAST = DIRECTION_VECTORS["E"]


def _point_at_angle_degrees(angle_degrees: float, distance: float) -> tuple[float, float]:
    """Baut einen Punkt relativ zum Ursprung, `angle_degrees` von Osten entfernt, im Uhrzeigersinn (Canvas-y nach unten)."""
    radians = math.radians(angle_degrees)
    return distance * math.cos(radians), distance * math.sin(radians)


def test_no_direction_vector_returns_none():
    candidates = {"A": (10.0, 0.0)}

    assert find_nearest_node_in_direction((0.0, 0.0), candidates, (0.0, 0.0)) is None


def test_no_candidate_in_cone_returns_none():
    candidates = {"A": _point_at_angle_degrees(45.0, 5.0)}

    assert find_nearest_node_in_direction((0.0, 0.0), candidates, _EAST) is None


def test_candidate_clearly_inside_cone_is_found():
    candidates = {"A": _point_at_angle_degrees(29.9, 10.0)}

    assert find_nearest_node_in_direction((0.0, 0.0), candidates, _EAST) == "A"


def test_candidate_clearly_outside_cone_is_ignored():
    candidates = {"A": _point_at_angle_degrees(30.1, 10.0)}

    assert find_nearest_node_in_direction((0.0, 0.0), candidates, _EAST) is None


def test_nearest_candidate_wins_over_farther_one():
    candidates = {"NEAR": (5.0, 0.0), "FAR": (10.0, 0.0)}

    assert find_nearest_node_in_direction((0.0, 0.0), candidates, _EAST) == "NEAR"


def test_tie_break_prefers_smaller_angle_at_equal_distance():
    on_axis = _point_at_angle_degrees(0.0, 10.0)
    off_axis = _point_at_angle_degrees(20.0, 10.0)
    candidates = {"ON_AXIS": on_axis, "OFF_AXIS": off_axis}

    assert find_nearest_node_in_direction((0.0, 0.0), candidates, _EAST) == "ON_AXIS"


def test_tie_break_prefers_lexicographically_smaller_id_at_equal_distance_and_angle():
    same_position = (10.0, 0.0)
    candidates = {"Z-CANDIDATE": same_position, "A-CANDIDATE": same_position}

    assert find_nearest_node_in_direction((0.0, 0.0), candidates, _EAST) == "A-CANDIDATE"


def test_candidate_at_current_position_is_skipped():
    candidates = {"SAME_SPOT": (0.0, 0.0), "REAL": (10.0, 0.0)}

    assert find_nearest_node_in_direction((0.0, 0.0), candidates, _EAST) == "REAL"


def test_diagonal_direction_finds_candidate_in_that_direction():
    candidates = {"NE": _point_at_angle_degrees(-45.0, 10.0), "E": (10.0, 0.0)}

    assert find_nearest_node_in_direction((0.0, 0.0), candidates, DIRECTION_VECTORS["NE"]) == "NE"
