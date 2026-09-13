import os
from dataclasses import replace

from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphFilter
from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from kursplaner.core.usecases.kompetenzgraph_load_body_usecase import LoadKompetenzNodeBodyUseCase
from kursplaner.core.usecases.kompetenzgraph_text_search_usecase import (
    KompetenzTextSearchIndex,
    compute_text_search_matches,
)
from kursplaner.infrastructure.repositories.kompetenzgraph_repository import FileSystemKompetenzGraphRepository
from tests.kompetenzgraph_test_support import make_kc_zuordnung, make_node, make_source_ref


class _CountingLoadBodyUseCase:
    """Zählt `execute()`-Aufrufe, um Cache-Hit/-Miss-Verhalten des Index zu verifizieren."""

    def __init__(self):
        self._delegate = LoadKompetenzNodeBodyUseCase(FileSystemKompetenzGraphRepository())
        self.calls = 0

    def execute(self, source_path):
        self.calls += 1
        return self._delegate.execute(source_path)


def _write(path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_get_sections_reads_and_splits_body(tmp_path):
    path = tmp_path / "AR-1.md"
    _write(path, "---\nprimarer_bereich: '[[I-Test]]'\n---\n# Titel\n\n## Beispiel\n\nErlaeuterung.")
    node = replace(make_node("AR-1"), source=replace(make_source_ref("AR-1"), path=path))

    index = KompetenzTextSearchIndex(_CountingLoadBodyUseCase())
    sections = index.get_sections(node)

    assert sections.beispiel_text == "Erlaeuterung."


def test_get_sections_does_not_reread_unchanged_file_on_second_call(tmp_path):
    path = tmp_path / "AR-1.md"
    _write(path, "---\nprimarer_bereich: '[[I-Test]]'\n---\n# Titel\n\n## Beispiel\n\nErste Version.")
    node = replace(make_node("AR-1"), source=replace(make_source_ref("AR-1"), path=path))
    load_body = _CountingLoadBodyUseCase()
    index = KompetenzTextSearchIndex(load_body)

    index.get_sections(node)
    index.get_sections(node)

    assert load_body.calls == 1


def test_get_sections_rereads_file_after_mtime_change(tmp_path):
    path = tmp_path / "AR-1.md"
    _write(path, "---\nprimarer_bereich: '[[I-Test]]'\n---\n# Titel\n\n## Beispiel\n\nErste Version.")
    node = replace(make_node("AR-1"), source=replace(make_source_ref("AR-1"), path=path))
    load_body = _CountingLoadBodyUseCase()
    index = KompetenzTextSearchIndex(load_body)
    first = index.get_sections(node)

    _write(path, "---\nprimarer_bereich: '[[I-Test]]'\n---\n# Titel\n\n## Beispiel\n\nZweite Version.")
    future = os.stat(path).st_mtime + 5
    os.utime(path, (future, future))

    second = index.get_sections(node)

    assert load_body.calls == 2
    assert first.beispiel_text == "Erste Version."
    assert second.beispiel_text == "Zweite Version."


def test_compute_text_search_matches_matches_titel_without_body_access():
    node_a = make_node("A", title="Vektoren addieren")
    node_b = make_node("B", title="Stochastik")
    snapshot = build_kompetenz_graph_snapshot([node_a, node_b], [])
    filter_ = KompetenzGraphFilter(
        text_query="Vektor",
        text_search_kc_verweis=False,
        text_search_titel=True,
        text_search_beispiel=False,
        text_search_rest=False,
    )
    load_body = _CountingLoadBodyUseCase()
    index = KompetenzTextSearchIndex(load_body)

    matches = compute_text_search_matches(snapshot, frozenset({"A", "B"}), filter_, index)

    assert matches == frozenset({"A"})
    assert load_body.calls == 0


def test_compute_text_search_matches_matches_kc_verweis():
    node = make_node("A", kc_zuordnung=(make_kc_zuordnung(kc_verweis="beschreibt Ableitungsregeln"),))
    snapshot = build_kompetenz_graph_snapshot([node], [])
    filter_ = KompetenzGraphFilter(
        text_query="Ableitung",
        text_search_kc_verweis=True,
        text_search_titel=False,
        text_search_beispiel=False,
        text_search_rest=False,
    )
    index = KompetenzTextSearchIndex(_CountingLoadBodyUseCase())

    matches = compute_text_search_matches(snapshot, frozenset({"A"}), filter_, index)

    assert matches == frozenset({"A"})


def test_compute_text_search_matches_only_reads_body_when_beispiel_or_rest_active(tmp_path):
    path = tmp_path / "AR-1.md"
    _write(path, "---\nprimarer_bereich: '[[I-Test]]'\n---\n# Titel\n\n## Beispiel\n\nEnthaelt Parabeln.")
    node = replace(make_node("AR-1", title="Unrelated"), source=replace(make_source_ref("AR-1"), path=path))
    snapshot = build_kompetenz_graph_snapshot([node], [])
    load_body = _CountingLoadBodyUseCase()
    index = KompetenzTextSearchIndex(load_body)

    structural_only_filter = KompetenzGraphFilter(
        text_query="Parabel",
        text_search_kc_verweis=False,
        text_search_titel=False,
        text_search_beispiel=False,
        text_search_rest=False,
    )
    no_matches = compute_text_search_matches(snapshot, frozenset({"AR-1"}), structural_only_filter, index)
    assert no_matches == frozenset()
    assert load_body.calls == 0

    beispiel_filter = KompetenzGraphFilter(
        text_query="Parabel",
        text_search_kc_verweis=False,
        text_search_titel=False,
        text_search_beispiel=True,
        text_search_rest=False,
    )
    matches = compute_text_search_matches(snapshot, frozenset({"AR-1"}), beispiel_filter, index)
    assert matches == frozenset({"AR-1"})
    assert load_body.calls == 1
