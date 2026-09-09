from pathlib import Path

from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from kursplaner.core.usecases.kompetenzgraph_load_body_usecase import LoadKompetenzNodeBodyUseCase
from kursplaner.core.usecases.kompetenzgraph_load_usecase import LoadKompetenzGraphUseCase
from kursplaner.core.usecases.kompetenzgraph_rebuild_usecase import RebuildKompetenzGraphUseCase
from tests.kompetenzgraph_test_support import make_node


class _FakeKompetenzGraphRepo:
    def __init__(self, snapshot, *, loaded_subjects=("Mathematik",)):
        self.snapshot = snapshot
        self.loaded_subjects = loaded_subjects
        self.load_calls: list[tuple] = []
        self.invalidate_calls = 0
        self.read_body_calls: list[Path] = []
        self.body_to_return: str | Exception = "Body-Inhalt"

    def load_snapshot(self, unterricht_dir, subject_folders=None):
        self.load_calls.append((unterricht_dir, subject_folders))
        return self.snapshot, (), self.loaded_subjects

    def rebuild_snapshot(self, unterricht_dir, subject_folders=None):
        raise AssertionError("rebuild_snapshot sollte hier nicht direkt aufgerufen werden")

    def invalidate_cache(self, unterricht_dir=None, subject_folder=None):
        self.invalidate_calls += 1

    def read_body(self, source_path):
        self.read_body_calls.append(source_path)
        if isinstance(self.body_to_return, Exception):
            raise self.body_to_return
        return self.body_to_return

    def discover_structured_subjects(self, unterricht_dir):
        return self.loaded_subjects


def test_load_usecase_reports_cycle_diagnostics():
    node_a = make_node("A", oberkompetenzen_ids=("B",))
    node_b = make_node("B", oberkompetenzen_ids=("A",))
    snapshot = build_kompetenz_graph_snapshot([node_a, node_b], [])
    repo = _FakeKompetenzGraphRepo(snapshot)
    usecase = LoadKompetenzGraphUseCase(kompetenzgraph_repo=repo)

    result = usecase.execute(Path("Unterricht"))

    assert len(result.cycle_diagnostics) == 1
    assert result.cycle_diagnostics[0].edge_kind == "hierarchy"
    assert result.loaded_subjects == ("Mathematik",)
    assert repo.load_calls == [(Path("Unterricht"), None)]


def test_load_usecase_no_cycle_diagnostics_for_clean_snapshot():
    snapshot = build_kompetenz_graph_snapshot([make_node("A")], [])
    repo = _FakeKompetenzGraphRepo(snapshot)
    usecase = LoadKompetenzGraphUseCase(kompetenzgraph_repo=repo)

    result = usecase.execute(Path("Unterricht"), subject_folders=("Mathematik",))

    assert result.cycle_diagnostics == ()
    assert repo.load_calls == [(Path("Unterricht"), ("Mathematik",))]


def test_rebuild_usecase_invalidates_then_delegates_to_load_usecase():
    snapshot = build_kompetenz_graph_snapshot([make_node("A")], [])
    repo = _FakeKompetenzGraphRepo(snapshot)
    load_usecase = LoadKompetenzGraphUseCase(kompetenzgraph_repo=repo)
    rebuild_usecase = RebuildKompetenzGraphUseCase(kompetenzgraph_repo=repo, load_usecase=load_usecase)

    result = rebuild_usecase.execute(Path("Unterricht"))

    assert repo.invalidate_calls == 1
    assert repo.load_calls == [(Path("Unterricht"), None)]
    assert "A" in result.snapshot.nodes


def test_load_body_usecase_delegates_to_repository():
    snapshot = build_kompetenz_graph_snapshot([make_node("A")], [])
    repo = _FakeKompetenzGraphRepo(snapshot)
    repo.body_to_return = "# Titel\n\nInhalt."
    usecase = LoadKompetenzNodeBodyUseCase(kompetenzgraph_repo=repo)

    body = usecase.execute(Path("A.md"))

    assert body == "# Titel\n\nInhalt."
    assert repo.read_body_calls == [Path("A.md")]


def test_load_body_usecase_returns_placeholder_on_os_error():
    snapshot = build_kompetenz_graph_snapshot([make_node("A")], [])
    repo = _FakeKompetenzGraphRepo(snapshot)
    repo.body_to_return = OSError("Datei verschoben")
    usecase = LoadKompetenzNodeBodyUseCase(kompetenzgraph_repo=repo)

    body = usecase.execute(Path("A.md"))

    assert "nicht geladen werden" in body
