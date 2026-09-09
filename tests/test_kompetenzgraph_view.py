from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphFilter
from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from kursplaner.core.domain.kompetenzgraph_view import compute_kompetenz_graph_view
from kursplaner.core.domain.kompetenzgraph_view_mode import MODE_FORT_VORAUS, MODE_OBER_TEIL
from tests.kompetenzgraph_test_support import make_kc_zuordnung, make_node


def _five_node_chain():
    """A-B-C-D-E via oberkompetenzen (Kind->Eltern): A ist die allgemeinste Kompetenz.

    A, B, C sind Jahrgang 8; D, E sind Jahrgang 99 -- so lassen sich
    Filter-/Matchingtiefe-/Fokus-Grenzen gezielt gegeneinander testen.
    """
    a = make_node("A", kc_zuordnung=(make_kc_zuordnung(jahrgang=8),))
    b = make_node("B", oberkompetenzen_ids=("A",), kc_zuordnung=(make_kc_zuordnung(jahrgang=8),))
    c = make_node("C", oberkompetenzen_ids=("B",), kc_zuordnung=(make_kc_zuordnung(jahrgang=8),))
    d = make_node("D", oberkompetenzen_ids=("C",), kc_zuordnung=(make_kc_zuordnung(jahrgang=99),))
    e = make_node("E", oberkompetenzen_ids=("D",), kc_zuordnung=(make_kc_zuordnung(jahrgang=99),))
    return build_kompetenz_graph_snapshot([a, b, c, d, e], [])


def test_pipeline_without_focus_combines_filter_and_matchingtiefe():
    snapshot = _five_node_chain()
    filter_ = KompetenzGraphFilter(jahrgang=8, kontexttiefe=1)

    view = compute_kompetenz_graph_view(snapshot, filter_, MODE_OBER_TEIL, focus_id=None)

    assert view.visible.primary_ids == frozenset({"A", "B", "C"})
    assert view.visible.context_ids == frozenset({"D"})
    assert view.visible.all_ids == frozenset({"A", "B", "C", "D"})


def test_focus_cannot_escape_filter_and_matchingtiefe():
    """C's volle transitive Fokus-Huelle enthaelt E -- E darf trotzdem nicht in der finalen Ansicht auftauchen,
    da E weder Filtertreffer noch innerhalb der Matchingtiefe erreichbarer Kontextknoten ist."""
    snapshot = _five_node_chain()
    filter_ = KompetenzGraphFilter(jahrgang=8, kontexttiefe=1)

    view = compute_kompetenz_graph_view(snapshot, filter_, MODE_OBER_TEIL, focus_id="C")

    assert view.visible.all_ids == frozenset({"A", "B", "C", "D"})
    assert "E" not in view.visible.all_ids
    assert view.visible.primary_ids == frozenset({"A", "B", "C"})
    assert view.visible.context_ids == frozenset({"D"})


def test_focus_outside_allowed_set_is_treated_as_no_focus():
    snapshot = _five_node_chain()
    filter_ = KompetenzGraphFilter(jahrgang=8, kontexttiefe=0)

    view = compute_kompetenz_graph_view(snapshot, filter_, MODE_OBER_TEIL, focus_id="E")

    assert view.visible.all_ids == frozenset({"A", "B", "C"})


def test_subject_multiselect_with_cross_subject_context_neighbor():
    mathe = make_node("M-1", subject="Mathematik", oberkompetenzen_ids=("INF-1",))
    informatik = make_node("INF-1", subject="Informatik")
    snapshot = build_kompetenz_graph_snapshot([mathe, informatik], [])
    filter_ = KompetenzGraphFilter(subjects=frozenset({"Mathematik"}), kontexttiefe=1)

    view = compute_kompetenz_graph_view(snapshot, filter_, MODE_OBER_TEIL, focus_id=None)

    assert view.visible.primary_ids == frozenset({"M-1"})
    assert view.visible.context_ids == frozenset({"INF-1"})
    assert "INF-1" not in view.visible.primary_ids


def test_view_mode_switch_changes_relevant_edges():
    """K-1 hat sowohl eine oberkompetenzen- als auch eine voraussetzungen-Kante.

    Ein Fokus auf K-1 darf in der Ober/Teil-Ansicht nur P-1 zeigen (die
    Fokus-Huelle folgt dort ausschliesslich hierarchy-Kanten) und in der
    Fort/Voraus-Ansicht nur V-1 (dort ausschliesslich prerequisite-Kanten)
    -- der Fokus ist damit der Ort, an dem sich der Ansichtswechsel
    tatsaechlich bemerkbar macht (ohne aktiven Fokus wuerden beide
    Ansichten hier dieselbe, ungefilterte Primaermenge zeigen).
    """
    hierarchy_parent = make_node("P-1")
    voraussetzung = make_node("V-1")
    node_with_both_edge_kinds = make_node("K-1", oberkompetenzen_ids=("P-1",), voraussetzungen_ids=("V-1",))
    snapshot = build_kompetenz_graph_snapshot([hierarchy_parent, voraussetzung, node_with_both_edge_kinds], [])
    filter_ = KompetenzGraphFilter()

    ober_teil_view = compute_kompetenz_graph_view(snapshot, filter_, MODE_OBER_TEIL, focus_id="K-1")
    fort_voraus_view = compute_kompetenz_graph_view(snapshot, filter_, MODE_FORT_VORAUS, focus_id="K-1")

    assert ober_teil_view.visible.all_ids == frozenset({"P-1", "K-1"})
    assert "V-1" not in ober_teil_view.visible.all_ids
    assert fort_voraus_view.visible.all_ids == frozenset({"V-1", "K-1"})
    assert "P-1" not in fort_voraus_view.visible.all_ids


def test_cyclic_data_terminates_in_full_pipeline():
    node_a = make_node("A", oberkompetenzen_ids=("B",))
    node_b = make_node("B", oberkompetenzen_ids=("A",))
    snapshot = build_kompetenz_graph_snapshot([node_a, node_b], [])
    filter_ = KompetenzGraphFilter(kontexttiefe=5)

    view = compute_kompetenz_graph_view(snapshot, filter_, MODE_OBER_TEIL, focus_id="A")

    assert view.visible.all_ids == frozenset({"A", "B"})
