from kursplaner.core.domain.kompetenzgraph_layout import compute_layered_layout
from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from kursplaner.core.domain.kompetenzgraph_view_mode import MODE_OBER_TEIL
from tests.kompetenzgraph_test_support import make_bereich, make_node


def _diamond_snapshot():
    root = make_node("ROOT")
    a = make_node("A", oberkompetenzen_ids=("ROOT",))
    b = make_node("B", oberkompetenzen_ids=("ROOT",))
    leaf = make_node("LEAF", oberkompetenzen_ids=("A", "B"))
    return build_kompetenz_graph_snapshot([root, a, b, leaf], [])


def test_diamond_dag_gets_correct_layer_depths():
    snapshot = _diamond_snapshot()
    visible = frozenset({"ROOT", "A", "B", "LEAF"})

    layout = compute_layered_layout(snapshot, MODE_OBER_TEIL, visible, frozenset())

    assert layout.positions["ROOT"].y == 0.0
    assert layout.positions["A"].y == layout.positions["B"].y
    assert layout.positions["A"].y > layout.positions["ROOT"].y
    assert layout.positions["LEAF"].y > layout.positions["A"].y


def test_layout_is_deterministic_across_repeated_calls():
    snapshot = _diamond_snapshot()
    visible = frozenset({"ROOT", "A", "B", "LEAF"})

    first = compute_layered_layout(snapshot, MODE_OBER_TEIL, visible, frozenset())
    second = compute_layered_layout(snapshot, MODE_OBER_TEIL, visible, frozenset())

    assert first.positions == second.positions


def test_cyclic_data_produces_complete_terminating_layout():
    node_a = make_node("A", oberkompetenzen_ids=("B",))
    node_b = make_node("B", oberkompetenzen_ids=("A",))
    snapshot = build_kompetenz_graph_snapshot([node_a, node_b], [])
    visible = frozenset({"A", "B"})

    layout = compute_layered_layout(snapshot, MODE_OBER_TEIL, visible, frozenset())

    assert set(layout.positions.keys()) == {"A", "B"}


def test_bereich_hub_gets_fixed_row_independent_of_competency_layers():
    bereich = make_bereich("I-Test", kind="inhaltsbereich")
    node = make_node("A", primarer_bereich_id="I-Test")
    snapshot = build_kompetenz_graph_snapshot([node], [bereich])

    layout = compute_layered_layout(snapshot, MODE_OBER_TEIL, frozenset({"A"}), frozenset({"I-Test"}))

    assert layout.positions["I-Test"].y != layout.positions["A"].y
    assert layout.positions["I-Test"].y < 0


def test_unresolved_link_marker_is_offset_from_referencing_node():
    bereich = make_bereich("I-Test", kind="inhaltsbereich")
    node = make_node("A", oberkompetenzen_ids=("NICHT-VORHANDEN",))
    snapshot = build_kompetenz_graph_snapshot([node], [bereich])

    layout = compute_layered_layout(snapshot, MODE_OBER_TEIL, frozenset({"A"}), frozenset())

    assert len(layout.unresolved_marker_positions) == 1
    marker_position = next(iter(layout.unresolved_marker_positions.values()))
    node_position = layout.positions["A"]
    assert marker_position != node_position


def test_invisible_nodes_are_not_included_in_positions():
    snapshot = _diamond_snapshot()

    layout = compute_layered_layout(snapshot, MODE_OBER_TEIL, frozenset({"ROOT", "A"}), frozenset())

    assert set(layout.positions.keys()) == {"ROOT", "A"}
