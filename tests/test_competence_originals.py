"""Originaltitel-Puffer der Sequenzleiter: lädt nur auf Anforderung, schlägt sonst nur nach (synthetische Daten)."""

from __future__ import annotations

from pathlib import Path

from kompetenzgraph_test_support import make_node
from sequence_ladder_test_support import make_ladder_env

from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from kursplaner.core.domain.sequence_ladder_entries import network_block_text
from kursplaner.core.usecases.competence_originals import CompetenceOriginalsBuffer
from kursplaner.core.usecases.kompetenzgraph_load_usecase import LoadKompetenzGraphUseCase


class _CountingRepo:
    """Fake-Repository: zählt Ladevorgänge, kann einen Lesefehler simulieren."""

    def __init__(self, title: str = "stellen Brüche dar") -> None:
        self.calls = 0
        self.fail = False
        self.title = title

    def load_snapshot(self, unterricht_dir, subject_folders=None):
        self.calls += 1
        if self.fail:
            raise OSError("Netzlaufwerk weg")
        snapshot = build_kompetenz_graph_snapshot([make_node("K-31", title=self.title)], [])
        return snapshot, (), ("Mathematik",)


def _buffer(repo: _CountingRepo) -> tuple[CompetenceOriginalsBuffer, LoadKompetenzGraphUseCase]:
    load = LoadKompetenzGraphUseCase(kompetenzgraph_repo=repo)
    return CompetenceOriginalsBuffer(load), load


def test_lookups_never_load_and_ensure_loaded_loads_only_once():
    repo = _CountingRepo()
    buffer, _load = _buffer(repo)
    assert buffer.original("K-31") is None and repo.calls == 0
    for _ in range(3):  # Leiter dreimal eingeblendet
        buffer.ensure_loaded(Path("unterricht"))
    for _ in range(5):
        assert buffer.original("K-31") == "stellen Brüche dar"
    assert buffer.original("K-99") is None
    assert repo.calls == 1


def test_any_load_of_the_network_updates_the_buffer():
    repo = _CountingRepo()
    buffer, load = _buffer(repo)
    load.execute(Path("unterricht"))  # z. B. Kompetenznetz-Dialog geöffnet
    assert buffer.original("K-31") == "stellen Brüche dar"
    repo.title = "stellen Brüche ikonisch dar"
    load.execute(Path("unterricht"))  # Neuaufbau
    assert buffer.original("K-31") == "stellen Brüche ikonisch dar"


def test_original_is_normalized_like_an_imported_alias():
    repo = _CountingRepo(title="Titel [mit] Klammern")
    buffer, _load = _buffer(repo)
    buffer.ensure_loaded(Path("unterricht"))
    assert buffer.original("K-31") == network_block_text("K-31", "Titel [mit] Klammern")


def test_read_error_is_swallowed_and_retried_missing_yaml_is_harmless():
    repo = _CountingRepo()
    repo.fail = True
    buffer, _load = _buffer(repo)
    buffer.ensure_loaded(Path("unterricht"))
    assert buffer.original("K-31") is None
    repo.fail = False
    buffer.ensure_loaded(Path("unterricht"))
    assert buffer.original("K-31") == "stellen Brüche dar" and repo.calls == 2
    without_yaml = CompetenceOriginalsBuffer(None)
    without_yaml.ensure_loaded(Path("unterricht"))
    assert without_yaml.original("K-31") is None


def test_ladder_view_carries_originals_of_its_network_blocks(tmp_path):
    repo = _CountingRepo()
    buffer, _load = _buffer(repo)
    buffer.ensure_loaded(Path("unterricht"))
    env = make_ladder_env(tmp_path, "U", originals=buffer, u0={"ziel": "[[K-31|Brüche zeigen]]"})
    assert dict(env.view().originals) == {"K-31": "stellen Brüche dar"}
    assert repo.calls == 1
