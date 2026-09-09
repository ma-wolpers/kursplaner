from kursplaner.adapters.gui.kompetenzgraph_canvas_selection import (
    handle_double_click_or_enter,
    handle_single_click,
)
from kursplaner.adapters.gui.kompetenzgraph_ui_state import KompetenzGraphUiState
from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphFilter


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
