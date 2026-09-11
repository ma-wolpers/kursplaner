from kursplaner.core.domain.kompetenzgraph_focus import compute_focus_visible_ids
from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from kursplaner.core.domain.kompetenzgraph_view_mode import MODE_ABHAENGIGKEITEN, MODE_OBER_TEIL
from tests.kompetenzgraph_test_support import make_node


def test_focus_includes_ancestors_and_descendants_not_siblings():
    """Diamant: ROOT hat zwei Kinder A und B, A hat ein Kind LEAF.

    Fokus auf A muss ROOT (Vorfahre) und LEAF (Nachfahre) enthalten,
    aber NICHT B -- B ist nur ueber den gemeinsamen Vorfahren ROOT
    verbunden ("ueber Eck"), nicht auf dem eigenen Ahnen-/Nachkommenpfad
    von A.
    """
    root = make_node("ROOT")
    a = make_node("A", oberkompetenzen_ids=("ROOT",))
    b = make_node("B", oberkompetenzen_ids=("ROOT",))
    leaf = make_node("LEAF", oberkompetenzen_ids=("A",))
    snapshot = build_kompetenz_graph_snapshot([root, a, b, leaf], [])

    focus_visible = compute_focus_visible_ids(snapshot, MODE_OBER_TEIL, "A")

    assert focus_visible == frozenset({"ROOT", "A", "LEAF"})
    assert "B" not in focus_visible


def test_focus_on_leaf_node_includes_only_itself_and_ancestors():
    root = make_node("ROOT")
    child = make_node("K-1", oberkompetenzen_ids=("ROOT",))
    snapshot = build_kompetenz_graph_snapshot([root, child], [])

    focus_visible = compute_focus_visible_ids(snapshot, MODE_OBER_TEIL, "K-1")

    assert focus_visible == frozenset({"ROOT", "K-1"})


def test_focus_in_abhaengigkeiten_mode_closes_transitively_over_both_edge_kinds():
    """A ist Teilkompetenz von ROOT (oberkompetenzen), B ist Voraussetzung von A -- Fokus auf A
    muss in MODE_ABHAENGIGKEITEN beide erreichen, ohne separaten Traversierungspfad."""
    root = make_node("ROOT")
    a = make_node("A", oberkompetenzen_ids=("ROOT",), voraussetzungen_ids=("B",))
    b = make_node("B")
    snapshot = build_kompetenz_graph_snapshot([root, a, b], [])

    focus_visible = compute_focus_visible_ids(snapshot, MODE_ABHAENGIGKEITEN, "A")

    assert focus_visible == frozenset({"ROOT", "A", "B"})
