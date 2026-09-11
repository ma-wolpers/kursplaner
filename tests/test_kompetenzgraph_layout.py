from kursplaner.core.domain import kompetenzgraph_layout
from kursplaner.core.domain.kompetenzgraph_layout import compute_layered_layout
from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from kursplaner.core.domain.kompetenzgraph_view_mode import MODE_ABHAENGIGKEITEN, MODE_OBER_TEIL
from tests.kompetenzgraph_test_support import make_bereich, make_node

_MAX_VERTICAL_JITTER = 20.0
"""Muss zum betragsmäßig größten Wert in `kompetenzgraph_layout.py::_VERTICAL_JITTER_PATTERN`
passen -- hier bewusst dupliziert statt importiert, damit ein Test fehlschlägt, falls die
Implementierung den Versatz je vergrößert, ohne dass die Schichtgrenzen-Sicherheitsmarge
(Tests unten) explizit gegengeprüft wird."""


def _diamond_snapshot():
    root = make_node("ROOT")
    a = make_node("A", oberkompetenzen_ids=("ROOT",))
    b = make_node("B", oberkompetenzen_ids=("ROOT",))
    leaf = make_node("LEAF", oberkompetenzen_ids=("A", "B"))
    return build_kompetenz_graph_snapshot([root, a, b, leaf], [])


def test_diamond_dag_gets_correct_layer_depths():
    """Y bleibt strikt die Hierarchieschicht -- ein kleiner kosmetischer Y-Versatz innerhalb
    einer Schicht (siehe `_VERTICAL_JITTER_PATTERN`) ist erlaubt, daher keine exakten
    Absolutwerte, sondern nur die relative Schicht-Reihenfolge wird geprüft."""
    snapshot = _diamond_snapshot()
    visible = frozenset({"ROOT", "A", "B", "LEAF"})

    layout = compute_layered_layout(snapshot, MODE_OBER_TEIL, visible, frozenset())

    assert layout.positions["A"].y > layout.positions["ROOT"].y + _MAX_VERTICAL_JITTER
    assert layout.positions["LEAF"].y > layout.positions["A"].y + _MAX_VERTICAL_JITTER


def test_vertical_jitter_pattern_never_crosses_a_layer_boundary():
    """Harte Invariante, algebraisch geprüft: selbst der betragsmäßig größte Y-Versatz auf BEIDEN
    Seiten einer Schichtgrenze darf `_LAYER_SPACING` nicht aufzehren -- sonst könnte ein Knoten
    aus Schicht N tiefer erscheinen als einer aus Schicht N+1 ("höher/niedriger" würde mehrdeutig)."""
    max_jitter = max(abs(value) for value in kompetenzgraph_layout._VERTICAL_JITTER_PATTERN)

    assert kompetenzgraph_layout._LAYER_SPACING - 2 * max_jitter > 0


def test_diamond_layer_gap_leaves_a_visible_safety_margin_with_real_jitter():
    """Ergänzender End-zu-Ende-Check mit echten Knoten (mehrere pro Schicht, damit der Versatz
    tatsächlich zyklisch angewendet wird): die Schichten bleiben klar getrennt."""
    root = make_node("ROOT")
    children = [make_node(f"CHILD-{i}", oberkompetenzen_ids=("ROOT",)) for i in range(5)]
    snapshot = build_kompetenz_graph_snapshot([root, *children], [])
    visible = frozenset({"ROOT", *(c.id for c in children)})

    layout = compute_layered_layout(snapshot, MODE_OBER_TEIL, visible, frozenset())

    root_y = layout.positions["ROOT"].y
    min_child_y = min(layout.positions[c.id].y for c in children)
    assert min_child_y > root_y


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


def test_abhaengigkeiten_mode_layers_mixed_edge_types_consistently():
    """P-1 -> K-1 (Teilkompetenz, ueber umgedrehte oberkompetenzen) und K-1 -> V-1 (Voraussetzung)
    sind zwei verschiedene Kantentypen entlang EINES Pfades -- beide muessen in MODE_ABHAENGIGKEITEN
    zur selben, konsistent aufsteigenden Schichttiefe fuehren (P-1 ueber K-1 ueber V-1)."""
    parent = make_node("P-1")
    child = make_node("K-1", oberkompetenzen_ids=("P-1",), voraussetzungen_ids=("V-1",))
    voraussetzung = make_node("V-1")
    snapshot = build_kompetenz_graph_snapshot([parent, child, voraussetzung], [])
    visible = frozenset({"P-1", "K-1", "V-1"})

    layout = compute_layered_layout(snapshot, MODE_ABHAENGIGKEITEN, visible, frozenset())

    assert layout.positions["K-1"].y > layout.positions["P-1"].y + _MAX_VERTICAL_JITTER
    assert layout.positions["V-1"].y > layout.positions["K-1"].y + _MAX_VERTICAL_JITTER
