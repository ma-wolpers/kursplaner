from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from tests.kompetenzgraph_test_support import make_bereich, make_node, make_source_ref


def test_build_snapshot_derives_teilkompetenzen_backlink():
    parent = make_node("P-1")
    child = make_node("K-1", oberkompetenzen_ids=("P-1",))

    snapshot = build_kompetenz_graph_snapshot([parent, child], [])

    assert snapshot.teilkompetenzen_by_id["P-1"] == ("K-1",)
    assert snapshot.teilkompetenzen_by_id["K-1"] == ()


def test_build_snapshot_derives_weiterfuehrung_backlink():
    voraussetzung = make_node("V-1")
    folge = make_node("F-1", voraussetzungen_ids=("V-1",))

    snapshot = build_kompetenz_graph_snapshot([voraussetzung, folge], [])

    assert snapshot.weiterfuehrung_by_id["V-1"] == ("F-1",)
    assert snapshot.weiterfuehrung_by_id["F-1"] == ()


def test_build_snapshot_detects_unresolved_hierarchy_link():
    bereich = make_bereich("I-Test", kind="inhaltsbereich")
    child = make_node("K-1", oberkompetenzen_ids=("NICHT-VORHANDEN",), primarer_bereich_id="I-Test")

    snapshot = build_kompetenz_graph_snapshot([child], [bereich])

    assert len(snapshot.unresolved_links) == 1
    link = snapshot.unresolved_links[0]
    assert (link.source_id, link.field, link.target_id) == ("K-1", "oberkompetenzen", "NICHT-VORHANDEN")


def test_build_snapshot_detects_unresolved_classification_link():
    node = make_node("K-1", primarer_bereich_id="I-Nicht-Vorhanden")

    snapshot = build_kompetenz_graph_snapshot([node], [])

    assert any(link.field == "primarer_bereich" for link in snapshot.unresolved_links)


def test_build_snapshot_resolves_duplicate_ids_deterministically():
    winner_source = make_source_ref("K-1", subject="Informatik")
    loser_source = make_source_ref("K-1", subject="Mathematik")
    node_a = make_node("K-1", source=winner_source)
    node_b = make_node("K-1", source=loser_source)

    snapshot = build_kompetenz_graph_snapshot([node_a, node_b], [])

    assert len(snapshot.nodes) == 1
    assert snapshot.nodes["K-1"].source.subject == "Informatik"  # "Informatik" < "Mathematik" lexikalisch
    assert len(snapshot.duplicate_ids) == 1
    diagnostic = snapshot.duplicate_ids[0]
    assert diagnostic.id == "K-1"
    assert diagnostic.winning_source == winner_source.path
    assert diagnostic.discarded_sources == (loser_source.path,)


def test_build_snapshot_no_diagnostics_for_unique_ids():
    snapshot = build_kompetenz_graph_snapshot([make_node("A"), make_node("B")], [make_bereich("I-Test")])

    assert snapshot.duplicate_ids == ()
    assert snapshot.unresolved_links == ()


def test_snapshot_nodes_mapping_is_read_only():
    snapshot = build_kompetenz_graph_snapshot([make_node("A")], [])

    try:
        snapshot.nodes["B"] = make_node("B")  # type: ignore[index]
        assert False, "MappingProxyType haette einen TypeError werfen muessen"
    except TypeError:
        pass
