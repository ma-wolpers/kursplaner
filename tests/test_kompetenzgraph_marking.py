"""Kompetenznetz: Markieren für die Übernahme und Titel-Duplikat-Diagnose (synthetische Netze)."""

from __future__ import annotations

from kompetenzgraph_test_support import make_bereich, make_node

from kursplaner.adapters.gui.kompetenzgraph_diagnostics_banner import duplicate_title_summary
from kursplaner.adapters.gui.kompetenzgraph_marking import clear_marks, mark_visible, toggle_mark
from kursplaner.adapters.gui.kompetenzgraph_ui_state import KompetenzGraphUiState
from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphFilter, KompetenzGraphVisibleSet
from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from kursplaner.core.domain.kompetenzgraph_title_check import check_kompetenz_graph_for_duplicate_titles
from kursplaner.core.domain.kompetenzgraph_view import KompetenzGraphView
from kursplaner.core.usecases.kompetenzgraph_load_usecase import KompetenzGraphLoadResult


def _snapshot(*nodes):
    return build_kompetenz_graph_snapshot(list(nodes) or [make_node("A"), make_node("B")], [make_bereich("I-Test")])


def test_toggle_and_clear_marks_ignore_area_hubs():
    state = KompetenzGraphUiState(filter=KompetenzGraphFilter())
    snapshot = _snapshot()
    toggle_mark(state, snapshot, "A")
    toggle_mark(state, snapshot, "I-Test")
    assert state.marked_ids == {"A"}
    toggle_mark(state, snapshot, "A")
    assert state.marked_ids == frozenset()
    toggle_mark(state, snapshot, "B")
    clear_marks(state)
    assert state.marked_ids == frozenset()


def test_mark_visible_takes_filter_hits_but_not_context_nodes():
    state = KompetenzGraphUiState(filter=KompetenzGraphFilter(), marked_ids=frozenset({"X"}))
    view = KompetenzGraphView(
        visible=KompetenzGraphVisibleSet(primary_ids=frozenset({"A"}), context_ids=frozenset({"B"})),
        visible_bereich_ids=frozenset({"I-Test"}),
    )
    mark_visible(state, _snapshot(), view)
    assert state.marked_ids == {"X", "A"}


def test_duplicate_titles_are_found_per_subject_ignoring_case_and_spaces():
    snapshot = _snapshot(
        make_node("Mat-1", title="Vergleichen  Lösungswege"),
        make_node("Mat-2", title="vergleichen Lösungswege"),
        make_node("Inf-1", subject="Informatik", title="Vergleichen Lösungswege"),
        make_node("Mat-3", title="Etwas anderes"),
    )
    diagnostics = check_kompetenz_graph_for_duplicate_titles(snapshot)
    assert [(d.subject, d.node_ids) for d in diagnostics] == [("Mathematik", ("Mat-1", "Mat-2"))]
    result = KompetenzGraphLoadResult(snapshot, (), (), ("Mathematik",), diagnostics)
    assert "Mat-1, Mat-2" in duplicate_title_summary(result)
    assert duplicate_title_summary(KompetenzGraphLoadResult(snapshot, (), (), ())) == ""
