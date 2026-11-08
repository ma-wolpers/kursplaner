"""Kompetenznetz → Leiter-Bausteine: Spalte aus der Bereichsart, Meldungen statt Raten."""

from __future__ import annotations

from kompetenzgraph_test_support import make_bereich, make_node

from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from kursplaner.core.domain.sequence_ladder import LadderSide
from kursplaner.core.domain.sequence_ladder_import import competence_import_items, mixed_side_ids


def _snapshot():
    bereiche = [
        make_bereich("I-Zahlen", kind="inhaltsbereich"),
        make_bereich("I-Größen", kind="inhaltsbereich"),
        make_bereich("P-Darstellen", kind="prozessbereich"),
    ]
    nodes = [
        make_node("Mat-ZA-1", primarer_bereich_id="I-Zahlen", title="Zahlen ordnen"),
        make_node("Mat-DA-1", primarer_bereich_id="P-Darstellen", title="Darstellen [Tabelle]"),
        make_node("Mat-XX-1", primarer_bereich_id="I-Fehlt"),
        make_node("Mat-ZA-2", primarer_bereich_id="I-Zahlen", prozessbereich_ids=("P-Darstellen",), title="Beides"),
        make_node("Mat-ZA-3", primarer_bereich_id="I-Zahlen", prozessbereich_ids=("I-Größen",), title="Zweimal Inhalt"),
    ]
    return build_kompetenz_graph_snapshot(nodes, bereiche)


def test_only_competences_with_content_and_process_area_ask_for_the_column():
    ids = ["Mat-ZA-1", "Mat-ZA-2", "Mat-ZA-3", "Mat-DA-1", "Mat-XX-1", "Mat-ZA-2"]
    assert mixed_side_ids(_snapshot(), ids) == ("Mat-ZA-2",)


def test_chosen_column_applies_only_to_mixed_competences():
    ids = ["Mat-ZA-1", "Mat-ZA-2", "Mat-DA-1"]
    by_default, _ = competence_import_items(_snapshot(), ids)
    to_process, _ = competence_import_items(_snapshot(), ids, mixed_side=LadderSide.PROZESS)
    to_content, _ = competence_import_items(_snapshot(), ids, mixed_side=LadderSide.INHALT)
    assert [i.side for i in by_default] == [LadderSide.INHALT, LadderSide.INHALT, LadderSide.PROZESS]
    assert [i.side for i in to_process] == [LadderSide.INHALT, LadderSide.PROZESS, LadderSide.PROZESS]
    assert [i.side for i in to_content] == [LadderSide.INHALT, LadderSide.INHALT, LadderSide.PROZESS]


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
