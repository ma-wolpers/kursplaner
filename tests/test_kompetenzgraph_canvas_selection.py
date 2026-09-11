from kursplaner.adapters.gui.kompetenzgraph_canvas_selection import (
    handle_double_click_or_enter,
    handle_single_click,
    select_nearest_in_direction,
)
from kursplaner.adapters.gui.kompetenzgraph_ui_state import KompetenzGraphUiState
from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphFilter, KompetenzGraphVisibleSet
from kursplaner.core.domain.kompetenzgraph_layout import GraphNodePosition, KompetenzGraphLayout
from kursplaner.core.domain.kompetenzgraph_view import KompetenzGraphView


def _state(**overrides) -> KompetenzGraphUiState:
    base = {"filter": KompetenzGraphFilter(), "selected_id": None, "focus_id": None}
    base.update(overrides)
    return KompetenzGraphUiState(**base)


def test_single_click_sets_selection_only():
    state = _state(selected_id="A", focus_id="A")

    handle_single_click(state, "B")

    assert state.selected_id == "B"
    assert state.focus_id == "A"  # Fokus bleibt beim alten Knoten


def test_double_click_on_selected_node_sets_focus_and_selection():
    state = _state(selected_id="A")

    handle_double_click_or_enter(state, "A")

    assert state.focus_id == "A"
    assert state.selected_id == "A"


def test_double_click_on_same_focused_node_clears_focus():
    state = _state(selected_id="A", focus_id="A")

    handle_double_click_or_enter(state, "A")

    assert state.focus_id is None


def test_double_click_on_different_node_moves_focus_there():
    state = _state(selected_id="B", focus_id="A")

    handle_double_click_or_enter(state, "B")

    assert state.focus_id == "B"
    assert state.selected_id == "B"


def test_enter_uses_current_selection_as_target():
    state = _state(selected_id="C", focus_id=None)

    handle_double_click_or_enter(state, None)

    assert state.focus_id == "C"


def test_enter_with_no_selection_does_nothing():
    state = _state(selected_id=None, focus_id=None)

    handle_double_click_or_enter(state, None)

    assert state.focus_id is None


def _layout_and_view(positions: dict[str, tuple[float, float]]) -> tuple[KompetenzGraphLayout, KompetenzGraphView]:
    layout = KompetenzGraphLayout(
        positions={node_id: GraphNodePosition(x=x, y=y) for node_id, (x, y) in positions.items()},
        unresolved_marker_positions={},
    )
    visible = KompetenzGraphVisibleSet(primary_ids=frozenset(positions.keys()))
    view = KompetenzGraphView(visible=visible, visible_bereich_ids=frozenset())
    return layout, view


def test_select_nearest_in_direction_moves_to_closest_node_in_cone():
    state = _state(selected_id="A")
    layout, view = _layout_and_view({"A": (0.0, 0.0), "B": (200.0, 0.0), "C": (0.0, 200.0)})

    changed = select_nearest_in_direction(state, layout, view, (1.0, 0.0))  # Richtung Osten

    assert changed is True
    assert state.selected_id == "B"


def test_select_nearest_in_direction_returns_false_without_selection():
    state = _state(selected_id=None)
    layout, view = _layout_and_view({"B": (200.0, 0.0)})

    changed = select_nearest_in_direction(state, layout, view, (1.0, 0.0))

    assert changed is False
    assert state.selected_id is None


def test_select_nearest_in_direction_returns_false_when_no_candidate_in_cone():
    state = _state(selected_id="A")
    layout, view = _layout_and_view({"A": (0.0, 0.0), "C": (0.0, 200.0)})  # C liegt suedlich, nicht oestlich

    changed = select_nearest_in_direction(state, layout, view, (1.0, 0.0))

    assert changed is False
    assert state.selected_id == "A"


def test_select_nearest_in_direction_ignores_invisible_candidates():
    """Ein Kandidat, der nicht (mehr) in `view.visible.all_ids` steckt, darf nie Ziel werden."""
    state = _state(selected_id="A")
    layout = KompetenzGraphLayout(
        positions={"A": GraphNodePosition(x=0.0, y=0.0), "B": GraphNodePosition(x=200.0, y=0.0)},
        unresolved_marker_positions={},
    )
    visible = KompetenzGraphVisibleSet(primary_ids=frozenset({"A"}))  # B absichtlich NICHT sichtbar
    view = KompetenzGraphView(visible=visible, visible_bereich_ids=frozenset())

    changed = select_nearest_in_direction(state, layout, view, (1.0, 0.0))

    assert changed is False
    assert state.selected_id == "A"
