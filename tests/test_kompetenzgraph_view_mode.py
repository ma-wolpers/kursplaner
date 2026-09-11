import pytest

from kursplaner.core.domain.kompetenzgraph_layout import compute_layered_layout
from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from kursplaner.core.domain.kompetenzgraph_view_mode import (
    MODE_ABHAENGIGKEITEN,
    MODE_FORT_VORAUS,
    MODE_OBER_TEIL,
    ancestors_of,
    bidirectional_closure,
    descendants_of,
)
from tests.kompetenzgraph_test_support import make_bereich, make_node


def _build_hierarchy_snapshot():
    """Kind -> Eltern ueber oberkompetenzen: K-1 -> P-1 (P-1 ist die Oberkompetenz von K-1)."""
    parent = make_node("P-1", primarer_bereich_id="I-Test", prozessbereich_ids=("P-Prozess",))
    child = make_node("K-1", oberkompetenzen_ids=("P-1",), primarer_bereich_id="I-Test")
    bereich = make_bereich("I-Test", kind="inhaltsbereich")
    prozess_bereich = make_bereich("P-Prozess", kind="prozessbereich")
    return build_kompetenz_graph_snapshot([parent, child], [bereich, prozess_bereich])


def _build_prerequisite_snapshot():
    """Kind -> Vorbedingung ueber voraussetzungen: F-1 -> V-1 (V-1 ist Vorbedingung von F-1)."""
    voraussetzung = make_node("V-1")
    folge = make_node("F-1", voraussetzungen_ids=("V-1",))
    return build_kompetenz_graph_snapshot([voraussetzung, folge], [])


def test_ober_teil_mode_ancestors_uses_oberkompetenzen():
    snapshot = _build_hierarchy_snapshot()

    assert ancestors_of(snapshot, MODE_OBER_TEIL, "K-1") == ("P-1",)
    assert descendants_of(snapshot, MODE_OBER_TEIL, "P-1") == ("K-1",)


def test_ober_teil_mode_never_follows_classification_edges():
    snapshot = _build_hierarchy_snapshot()

    # P-1 referenziert "I-Test" (primarer_bereich) und "P-Prozess" (prozessbereiche) --
    # keins davon darf in ancestors_of/descendants_of auftauchen.
    assert "I-Test" not in ancestors_of(snapshot, MODE_OBER_TEIL, "P-1")
    assert "P-Prozess" not in ancestors_of(snapshot, MODE_OBER_TEIL, "P-1")
    assert "I-Test" not in descendants_of(snapshot, MODE_OBER_TEIL, "P-1")


def test_fort_voraus_mode_direction_is_inverted_relative_to_ober_teil():
    """voraussetzungen (Kind->Vorbedingung) zeigt nach UNTEN -- also descendants_of, nicht ancestors_of."""
    snapshot = _build_prerequisite_snapshot()

    assert descendants_of(snapshot, MODE_FORT_VORAUS, "F-1") == ("V-1",)
    assert ancestors_of(snapshot, MODE_FORT_VORAUS, "V-1") == ("F-1",)
    assert ancestors_of(snapshot, MODE_FORT_VORAUS, "F-1") == ()
    assert descendants_of(snapshot, MODE_FORT_VORAUS, "V-1") == ()


def test_unknown_mode_raises():
    snapshot = _build_hierarchy_snapshot()

    with pytest.raises(ValueError):
        ancestors_of(snapshot, "unbekannter-modus", "K-1")


def test_bidirectional_closure_includes_seed_and_both_directions():
    """A -> B (oberkompetenzen) -> C: Closure ab B in Ober/Teil-Ansicht erreicht A (Vorfahre) und C (Nachfahre)."""
    node_a = make_node("A")
    node_b = make_node("B", oberkompetenzen_ids=("A",))
    node_c = make_node("C", oberkompetenzen_ids=("B",))
    snapshot = build_kompetenz_graph_snapshot([node_a, node_b, node_c], [])

    closure = bidirectional_closure(snapshot, MODE_OBER_TEIL, frozenset({"B"}))

    assert closure == frozenset({"A", "B", "C"})


def test_bidirectional_closure_respects_max_depth():
    node_a = make_node("A")
    node_b = make_node("B", oberkompetenzen_ids=("A",))
    node_c = make_node("C", oberkompetenzen_ids=("B",))
    snapshot = build_kompetenz_graph_snapshot([node_a, node_b, node_c], [])

    depth_zero = bidirectional_closure(snapshot, MODE_OBER_TEIL, frozenset({"C"}), max_depth=0)
    depth_one = bidirectional_closure(snapshot, MODE_OBER_TEIL, frozenset({"C"}), max_depth=1)

    assert depth_zero == frozenset({"C"})
    assert depth_one == frozenset({"C", "B"})


def test_bidirectional_closure_terminates_on_cyclic_data():
    """A <-> B bilden einen Zyklus -- die Closure darf trotzdem nicht endlos laufen."""
    node_a = make_node("A", oberkompetenzen_ids=("B",))
    node_b = make_node("B", oberkompetenzen_ids=("A",))
    snapshot = build_kompetenz_graph_snapshot([node_a, node_b], [])

    closure = bidirectional_closure(snapshot, MODE_OBER_TEIL, frozenset({"A"}))

    assert closure == frozenset({"A", "B"})


def _build_mixed_edge_snapshot():
    """Ober/Teil-Pfad A -> B (B ist Teilkompetenz von A) UND Voraussetzungs-Pfad B -> C
    (C ist Voraussetzung von B) -- ein Knoten (B), der an beiden Kantentypen beteiligt ist,
    wie es in `MODE_ABHAENGIGKEITEN` gemeinsam gerendert wird."""
    node_a = make_node("A")
    node_b = make_node("B", oberkompetenzen_ids=("A",), voraussetzungen_ids=("C",))
    node_c = make_node("C")
    return build_kompetenz_graph_snapshot([node_a, node_b, node_c], [])


def test_abhaengigkeiten_mode_ancestors_union_teilkompetenz_and_weiterfuehrung():
    """ancestors_of(N, ABHAENGIGKEITEN) = N.oberkompetenzen_ids ∪ weiterfuehrung_by_id[N]."""
    snapshot = _build_mixed_edge_snapshot()

    assert ancestors_of(snapshot, MODE_ABHAENGIGKEITEN, "B") == ("A",)
    assert ancestors_of(snapshot, MODE_ABHAENGIGKEITEN, "C") == ("B",)
    assert ancestors_of(snapshot, MODE_ABHAENGIGKEITEN, "A") == ()


def test_abhaengigkeiten_mode_descendants_union_oberkompetenz_reversal_and_voraussetzung():
    """descendants_of(N, ABHAENGIGKEITEN) = teilkompetenzen_by_id[N] ∪ N.voraussetzungen_ids.

    Die Teilkompetenz-Richtung ist gegenüber dem gespeicherten `oberkompetenzen_ids`
    UMGEDREHT (A -> B statt B -> A), die Voraussetzungs-Richtung unverändert (B -> C)."""
    snapshot = _build_mixed_edge_snapshot()

    assert descendants_of(snapshot, MODE_ABHAENGIGKEITEN, "A") == ("B",)
    assert descendants_of(snapshot, MODE_ABHAENGIGKEITEN, "B") == ("C",)
    assert descendants_of(snapshot, MODE_ABHAENGIGKEITEN, "C") == ()


def test_abhaengigkeiten_mode_ancestors_descendants_are_algebraically_consistent():
    """Symmetrie-Invariante über beide Kantentypen gemischt: Z ∈ descendants_of(N) ⟺ N ∈ ancestors_of(Z)."""
    snapshot = _build_mixed_edge_snapshot()

    for node_id in snapshot.nodes:
        for descendant_id in descendants_of(snapshot, MODE_ABHAENGIGKEITEN, node_id):
            assert node_id in ancestors_of(snapshot, MODE_ABHAENGIGKEITEN, descendant_id)
        for ancestor_id in ancestors_of(snapshot, MODE_ABHAENGIGKEITEN, node_id):
            assert node_id in descendants_of(snapshot, MODE_ABHAENGIGKEITEN, ancestor_id)


def test_abhaengigkeiten_mode_bidirectional_closure_reaches_both_edge_kinds():
    """Fokus/Kontext (`bidirectional_closure`) muss ab B sowohl A (Teilkompetenz-Vorfahre)
    als auch C (Voraussetzungs-Nachfahre) transitiv erreichen -- ohne separaten Traversierungspfad."""
    snapshot = _build_mixed_edge_snapshot()

    closure = bidirectional_closure(snapshot, MODE_ABHAENGIGKEITEN, frozenset({"B"}))

    assert closure == frozenset({"A", "B", "C"})


def test_abhaengigkeiten_mode_mixed_cycle_terminates_in_closure_and_layout():
    """Künstlicher GEMISCHTER Zyklus: A ist Teilkompetenz von B (oberkompetenzen), UND B ist
    Voraussetzung von A -- keiner der beiden Kantentypen ist für sich genommen zyklisch, ihre
    Vereinigung in MODE_ABHAENGIGKEITEN aber schon. Weder `bidirectional_closure()` noch
    `compute_layered_layout()` dürfen daran hängen bleiben (Visited-Set- bzw.
    `find_back_edges()`-Konstruktion garantiert Terminierung strukturell, unabhängig von der
    Zyklenquelle) -- Regressionstest für die im Plan dokumentierte, technisch unkritische, aber
    fachlich beobachtenswerte Konstellation."""
    node_a = make_node("A", voraussetzungen_ids=("B",))
    node_b = make_node("B", oberkompetenzen_ids=("A",))
    snapshot = build_kompetenz_graph_snapshot([node_a, node_b], [])

    closure = bidirectional_closure(snapshot, MODE_ABHAENGIGKEITEN, frozenset({"A"}))
    assert closure == frozenset({"A", "B"})

    layout = compute_layered_layout(snapshot, MODE_ABHAENGIGKEITEN, frozenset({"A", "B"}), frozenset())
    assert set(layout.positions) == {"A", "B"}
