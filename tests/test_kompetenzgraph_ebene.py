"""Haupt-/Einzelkompetenzen: Einlesen, Kontextregel, Leiter-Sperre, Markieren, Titel-Ausnahme (synthetisch)."""

from __future__ import annotations

from kompetenzgraph_test_support import make_bereich, make_node

from kursplaner.adapters.gui.kompetenzgraph_marking import mark_visible, toggle_mark
from kursplaner.adapters.gui.kompetenzgraph_ui_state import KompetenzGraphUiState
from kursplaner.core.domain.course_kc_context import CourseKcContext
from kursplaner.core.domain.kompetenzgraph_ebene import is_hauptkompetenz
from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphFilter, KompetenzGraphVisibleSet
from kursplaner.core.domain.kompetenzgraph_kc_zuordnung_mapping import parse_kc_zuordnung_list
from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from kursplaner.core.domain.kompetenzgraph_title_check import check_kompetenz_graph_for_duplicate_titles
from kursplaner.core.domain.kompetenzgraph_types import EBENE_HAUPT, KcZuordnungEintrag
from kursplaner.core.domain.kompetenzgraph_view import KompetenzGraphView
from kursplaner.core.domain.sequence_ladder_import import competence_import_items, ladder_import_problem

IGS = CourseKcContext("Niedersachsen", "IGS")


def _entry(schulform="SekI", ebene=EBENE_HAUPT):
    return KcZuordnungEintrag("Niedersachsen", schulform, None, 10, "basis", "zitat", ebene)


def _snapshot(*, child_parent=("Inf-ID-1",)):
    bereiche = [
        make_bereich("I-Daten", subject="Informatik", kind="inhaltsbereich"),
        make_bereich("P-Modellieren", subject="Informatik", kind="prozessbereich"),
    ]
    nodes = [
        make_node("Inf-ID-1", subject="Informatik", primarer_bereich_id="I-Daten", kc_zuordnung=(_entry(),), title="T"),
        make_node(
            "Inf-ID-7",
            subject="Informatik",
            primarer_bereich_id="I-Daten",
            oberkompetenzen_ids=child_parent,
            kc_zuordnung=(_entry(ebene=None),),
            title="T",
        ),
        make_node(
            "Inf-SM-1", subject="Informatik", primarer_bereich_id="P-Modellieren", kc_zuordnung=(_entry(),), title="S"
        ),
    ]
    return build_kompetenz_graph_snapshot(nodes, bereiche)


def test_ebene_is_parsed_and_unknown_values_warn_but_keep_the_entry():
    raw = [
        {"bundesland": "Niedersachsen", "schulform": "SekI", "jahrgang": 10, "anforderung": "basis", "ebene": "haupt"},
        {"bundesland": "Niedersachsen", "schulform": "SekII", "jahrgang": 11, "anforderung": "basis", "ebene": "x"},
    ]
    entries, issues = parse_kc_zuordnung_list(raw, subject="Informatik")
    assert [e.ebene for e in entries] == [EBENE_HAUPT, None]
    assert len(issues) == 1 and "ebene" in issues[0].message


def test_haupt_status_follows_the_entries_of_the_course_context():
    mixed = make_node("Mat-X-1", kc_zuordnung=(_entry("IGS"), _entry("Gymnasium", ebene=None)))
    assert is_hauptkompetenz(mixed, IGS)
    assert not is_hauptkompetenz(mixed, CourseKcContext("Niedersachsen", "Gymnasium"))
    assert not is_hauptkompetenz(mixed)  # ohne Kontext zählen alle Einträge
    assert is_hauptkompetenz(mixed, CourseKcContext("Bayern", "IGS")) is False  # kein Treffer → alle zählen


def test_content_haupt_is_locked_but_process_haupt_stays_importable():
    snapshot = _snapshot()
    assert "Hauptkompetenz" in (ladder_import_problem(snapshot, "Inf-ID-1", IGS) or "")
    assert ladder_import_problem(snapshot, "Inf-SM-1", IGS) is None
    items, problems = competence_import_items(snapshot, ["Inf-ID-1", "Inf-ID-7", "Inf-SM-1"], IGS)
    assert [item.kompetenz_id for item in items] == ["Inf-ID-7", "Inf-SM-1"]
    assert len(problems) == 1


def test_marking_skips_locked_competences_but_always_allows_unmarking():
    snapshot = _snapshot()
    state = KompetenzGraphUiState(filter=KompetenzGraphFilter())

    def markable(node_id):
        return ladder_import_problem(snapshot, node_id, IGS) is None

    toggle_mark(state, snapshot, "Inf-ID-1", markable)
    assert state.marked_ids == frozenset()
    view = KompetenzGraphView(
        visible=KompetenzGraphVisibleSet(primary_ids=frozenset(snapshot.nodes)), visible_bereich_ids=frozenset()
    )
    mark_visible(state, snapshot, view, markable)
    assert state.marked_ids == {"Inf-ID-7", "Inf-SM-1"}
    state.marked_ids = state.marked_ids | {"Inf-ID-1"}
    toggle_mark(state, snapshot, "Inf-ID-1", markable)
    assert "Inf-ID-1" not in state.marked_ids


def test_haupt_and_its_direct_child_may_share_a_title():
    assert check_kompetenz_graph_for_duplicate_titles(_snapshot()) == ()


def test_same_titled_einzel_outside_the_haupt_gets_a_hint():
    (diagnostic,) = check_kompetenz_graph_for_duplicate_titles(_snapshot(child_parent=()))
    assert diagnostic.node_ids == ("Inf-ID-1", "Inf-ID-7")
    assert "direkte Teilkompetenz von Inf-ID-1" in diagnostic.hint
