from kursplaner.core.domain.kompetenzgraph_context import compute_context_node_ids
from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from kursplaner.core.domain.kompetenzgraph_view_mode import MODE_FORT_VORAUS, MODE_OBER_TEIL
from tests.kompetenzgraph_test_support import make_bereich, make_node


def _chain_snapshot():
    """A -> B -> C -> D (jeweils oberkompetenzen, A ist die allgemeinste Kompetenz)."""
    a = make_node("A")
    b = make_node("B", oberkompetenzen_ids=("A",))
    c = make_node("C", oberkompetenzen_ids=("B",))
    d = make_node("D", oberkompetenzen_ids=("C",))
    return build_kompetenz_graph_snapshot([a, b, c, d], [])


def test_kontexttiefe_zero_returns_empty_context():
    snapshot = _chain_snapshot()

    context = compute_context_node_ids(snapshot, MODE_OBER_TEIL, frozenset({"B"}), depth=0)

    assert context == frozenset()


def test_kontexttiefe_one_adds_direct_neighbors_only():
    snapshot = _chain_snapshot()

    context = compute_context_node_ids(snapshot, MODE_OBER_TEIL, frozenset({"B"}), depth=1)

    assert context == frozenset({"A", "C"})


def test_kontexttiefe_two_adds_second_order_neighbors():
    snapshot = _chain_snapshot()

    context = compute_context_node_ids(snapshot, MODE_OBER_TEIL, frozenset({"B"}), depth=2)

    assert context == frozenset({"A", "C", "D"})


def test_context_never_promotes_to_primary():
    """Kontextknoten bleiben disjunkt von primary_ids, auch bei Ueberschneidung der Startmenge."""
    snapshot = _chain_snapshot()
    primary_ids = frozenset({"B", "C"})

    context = compute_context_node_ids(snapshot, MODE_OBER_TEIL, primary_ids, depth=1)

    assert context.isdisjoint(primary_ids)
    assert context == frozenset({"A", "D"})


def test_context_no_duplicates_in_diamond_dag():
    """ROOT hat zwei Pfade zu LEAF (ueber A und ueber B) -- LEAF darf nur einmal im Ergebnis stehen."""
    root = make_node("ROOT")
    a = make_node("A", oberkompetenzen_ids=("ROOT",))
    b = make_node("B", oberkompetenzen_ids=("ROOT",))
    leaf = make_node("LEAF", oberkompetenzen_ids=("A", "B"))
    snapshot = build_kompetenz_graph_snapshot([root, a, b, leaf], [])

    context = compute_context_node_ids(snapshot, MODE_OBER_TEIL, frozenset({"LEAF"}), depth=2)

    assert context == frozenset({"A", "B", "ROOT"})


def test_cross_subject_neighbor_appears_as_context_not_primary():
    """Eine Mathematik-Kompetenz referenziert eine Informatik-Kompetenz als Oberkompetenz."""
    mathe_node = make_node("M-1", subject="Mathematik", oberkompetenzen_ids=("INF-1",))
    informatik_node = make_node("INF-1", subject="Informatik")
    snapshot = build_kompetenz_graph_snapshot([mathe_node, informatik_node], [])

    context = compute_context_node_ids(snapshot, MODE_OBER_TEIL, frozenset({"M-1"}), depth=1)

    assert context == frozenset({"INF-1"})


def test_classification_edges_never_extend_context():
    """primarer_bereich/prozessbereiche duerfen die Kontextmenge nicht erweitern."""
    bereich = make_bereich("I-Test", kind="inhaltsbereich")
    node = make_node("A", primarer_bereich_id="I-Test")
    snapshot = build_kompetenz_graph_snapshot([node], [bereich])

    context = compute_context_node_ids(snapshot, MODE_OBER_TEIL, frozenset({"A"}), depth=5)

    assert "I-Test" not in context
    assert context == frozenset()


def test_context_terminates_on_cyclic_data():
    node_a = make_node("A", oberkompetenzen_ids=("B",))
    node_b = make_node("B", oberkompetenzen_ids=("A",))
    snapshot = build_kompetenz_graph_snapshot([node_a, node_b], [])

    context = compute_context_node_ids(snapshot, MODE_OBER_TEIL, frozenset({"A"}), depth=10)

    assert context == frozenset({"B"})


def test_context_follows_active_view_mode():
    """Dieselbe Primaermenge liefert je nach View-Mode eine andere Kontextmenge."""
    hierarchy_parent = make_node("P-1")
    hierarchy_child = make_node("K-1", oberkompetenzen_ids=("P-1",))
    voraussetzung = make_node("V-1")
    with_prerequisite = make_node("K-1b", voraussetzungen_ids=("V-1",))
    snapshot = build_kompetenz_graph_snapshot(
        [hierarchy_parent, hierarchy_child, voraussetzung, with_prerequisite], []
    )

    ober_teil_context = compute_context_node_ids(snapshot, MODE_OBER_TEIL, frozenset({"K-1"}), depth=1)
    fort_voraus_context = compute_context_node_ids(snapshot, MODE_FORT_VORAUS, frozenset({"K-1b"}), depth=1)

    assert ober_teil_context == frozenset({"P-1"})
    assert fort_voraus_context == frozenset({"V-1"})
