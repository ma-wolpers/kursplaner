"""Kompetenznetz → Leiter-Bausteine: Spalte aus der Bereichsart, Meldungen statt Raten."""

from __future__ import annotations

from kompetenzgraph_test_support import make_bereich, make_node

from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from kursplaner.core.domain.sequence_ladder import LadderSide
from kursplaner.core.domain.sequence_ladder_import import competence_import_items


def _snapshot():
    bereiche = [make_bereich("I-Zahlen", kind="inhaltsbereich"), make_bereich("P-Darstellen", kind="prozessbereich")]
    nodes = [
        make_node("Mat-ZA-1", primarer_bereich_id="I-Zahlen", title="Zahlen ordnen"),
        make_node("Mat-DA-1", primarer_bereich_id="P-Darstellen", title="Darstellen [Tabelle]"),
        make_node("Mat-XX-1", primarer_bereich_id="I-Fehlt"),
    ]
    return build_kompetenz_graph_snapshot(nodes, bereiche)


def test_side_follows_primary_area_kind_and_titles_are_normalized():
    items, problems = competence_import_items(_snapshot(), ["Mat-DA-1", "Mat-ZA-1", "Mat-ZA-1"])
    assert [(i.kompetenz_id, i.side) for i in items] == [
        ("Mat-DA-1", LadderSide.PROZESS),
        ("Mat-ZA-1", LadderSide.INHALT),
    ]
    assert items[0].text == "Darstellen Tabelle"
    assert problems == ()


def test_unknown_ids_and_unresolvable_areas_are_reported():
    items, problems = competence_import_items(_snapshot(), ["Mat-XX-1", "Nope-1"])
    assert items == ()
    assert any("Primärbereich" in p for p in problems)
    assert any("nicht im Kompetenznetz" in p for p in problems)
