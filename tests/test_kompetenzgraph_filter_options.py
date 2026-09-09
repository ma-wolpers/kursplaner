from kursplaner.core.domain.kompetenzgraph_filter_options import compute_filter_options
from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from tests.kompetenzgraph_test_support import make_bereich, make_kc_zuordnung, make_node


def test_filter_options_are_derived_from_snapshot_not_hardcoded():
    mathe_node = make_node(
        "M-1",
        subject="Mathematik",
        status="entwurf",
        kc_zuordnung=(make_kc_zuordnung(bundesland="Niedersachsen", schulform="Gymnasium", jahrgang=11),),
    )
    informatik_node = make_node(
        "I-1",
        subject="Informatik",
        status="geprüft",
        kc_zuordnung=(make_kc_zuordnung(bundesland="Bayern", schulform="IGS", niveau="eA", jahrgang=8),),
    )
    inhaltsbereich = make_bereich("I-Test", kind="inhaltsbereich")
    prozessbereich = make_bereich("P-Test", kind="prozessbereich")
    snapshot = build_kompetenz_graph_snapshot([mathe_node, informatik_node], [inhaltsbereich, prozessbereich])

    options = compute_filter_options(snapshot)

    assert options.subjects == ("Informatik", "Mathematik")
    assert options.jahrgaenge == (8, 11)
    assert options.schulformen == ("Gymnasium", "IGS")
    assert options.bundeslaender == ("Bayern", "Niedersachsen")
    assert options.niveaus == ("eA",)
    assert options.status_werte == ("entwurf", "geprüft")
    assert options.anforderungen == ("basis",)
    assert options.inhaltsbereich_ids == ("I-Test",)
    assert options.prozessbereich_ids == ("P-Test",)


def test_filter_options_empty_snapshot_returns_empty_tuples():
    snapshot = build_kompetenz_graph_snapshot([], [])

    options = compute_filter_options(snapshot)

    assert options.subjects == ()
    assert options.jahrgaenge == ()
