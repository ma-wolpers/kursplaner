import pytest

from kursplaner.infrastructure.repositories import kompetenzgraph_repository as module
from kursplaner.infrastructure.repositories import kompetenzgraph_repository_cache as cache_module
from kursplaner.infrastructure.repositories.kompetenzgraph_repository import FileSystemKompetenzGraphRepository

_BEREICH_TEXT = "# Raum und Form (RF)\n\nKürzel: `RF`\n\nBeschreibung."


def _node_text(*, jahrgang: int = 8, titel: str = "Titel der Kompetenz") -> str:
    return (
        "---\n"
        "oberkompetenzen: []\n"
        'primarer_bereich: "[[I-Test]]"\n'
        "prozessbereiche: []\n"
        "voraussetzungen: []\n"
        "offene_voraussetzungen: []\n"
        "kc_zuordnung:\n"
        "  - bundesland: Niedersachsen\n"
        "    schulform: Gymnasium\n"
        "    niveau:\n"
        f"    jahrgang: {jahrgang}\n"
        "    anforderung: basis\n"
        '    kc_verweis: "Ein Zitat."\n'
        "status: entwurf\n"
        "---\n\n"
        f"# {titel}\n"
    )


def _build_vault(tmp_path, *, subjects=("Mathematik",)):
    fachinhalte_root = tmp_path / "34 Fachinhalte"
    for subject in subjects:
        subject_dir = fachinhalte_root / subject
        bereiche_dir = subject_dir / "Bereiche"
        bereiche_dir.mkdir(parents=True)
        (bereiche_dir / "I-Test.md").write_text(_BEREICH_TEXT, encoding="utf-8")
        (subject_dir / "AB-1.md").write_text(_node_text(), encoding="utf-8")
        (subject_dir / "AB-2.md").write_text(_node_text(jahrgang=11), encoding="utf-8")
    return fachinhalte_root


@pytest.fixture(autouse=True)
def _isolate_cache_file(tmp_path, monkeypatch):
    """Isoliert den persistenten Cache in einem Temp-Verzeichnis statt der echten Projekt-Config."""
    monkeypatch.setattr(cache_module, "cache_file_path", lambda: tmp_path / "_cache" / "kompetenzgraph_cache.json")


def _repo_with_fachinhalte_root(monkeypatch, fachinhalte_root):
    repo = FileSystemKompetenzGraphRepository()
    monkeypatch.setattr(module, "resolve_fachinhalte_root", lambda unterricht_dir: fachinhalte_root)
    return repo


def test_load_snapshot_reads_nodes_and_bereiche(tmp_path, monkeypatch):
    fachinhalte_root = _build_vault(tmp_path)
    repo = _repo_with_fachinhalte_root(monkeypatch, fachinhalte_root)

    snapshot, diagnostics, loaded_subjects = repo.load_snapshot(tmp_path / "Unterricht")

    assert loaded_subjects == ("Mathematik",)
    assert diagnostics == ()
    assert set(snapshot.nodes.keys()) == {"AB-1", "AB-2"}
    assert set(snapshot.bereiche.keys()) == {"I-Test"}
    assert snapshot.nodes["AB-1"].title == "Titel der Kompetenz"


def test_missing_fachinhalte_root_returns_empty_snapshot(tmp_path, monkeypatch):
    repo = _repo_with_fachinhalte_root(monkeypatch, None)

    snapshot, diagnostics, loaded_subjects = repo.load_snapshot(tmp_path / "Unterricht")

    assert dict(snapshot.nodes) == {}
    assert diagnostics == ()
    assert loaded_subjects == ()


def test_sync_conflict_files_are_ignored(tmp_path, monkeypatch):
    fachinhalte_root = _build_vault(tmp_path)
    conflict_path = fachinhalte_root / "Mathematik" / "AB-1.sync-conflict-20260101-120000.md"
    conflict_path.write_text(_node_text(), encoding="utf-8")
    repo = _repo_with_fachinhalte_root(monkeypatch, fachinhalte_root)

    snapshot, _diagnostics, _loaded_subjects = repo.load_snapshot(tmp_path / "Unterricht")

    assert set(snapshot.nodes.keys()) == {"AB-1", "AB-2"}


def test_cache_hit_on_unchanged_file_skips_reading_file_content(tmp_path, monkeypatch):
    """Zweiter `load_snapshot()`-Aufruf mit unveraendertem mtime+size darf die Datei nicht erneut lesen."""
    fachinhalte_root = _build_vault(tmp_path)
    repo = _repo_with_fachinhalte_root(monkeypatch, fachinhalte_root)
    unterricht_dir = tmp_path / "Unterricht"

    first_snapshot, first_diagnostics, _loaded_subjects = repo.load_snapshot(unterricht_dir)
    assert "AB-1" in first_snapshot.nodes
    assert first_diagnostics == ()

    node_path = fachinhalte_root / "Mathematik" / "AB-1.md"
    original_read_text = module.Path.read_text

    def _raise_if_target_read_again(self, *args, **kwargs):
        if self == node_path:
            raise AssertionError("Cache-Hit haette diese Datei nicht erneut lesen duerfen")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(module.Path, "read_text", _raise_if_target_read_again)

    second_snapshot, second_diagnostics, _loaded_subjects = repo.load_snapshot(unterricht_dir)

    assert second_diagnostics == ()
    assert second_snapshot.nodes["AB-1"].title == "Titel der Kompetenz"


def test_cache_miss_when_file_content_and_size_change(tmp_path, monkeypatch):
    fachinhalte_root = _build_vault(tmp_path)
    repo = _repo_with_fachinhalte_root(monkeypatch, fachinhalte_root)
    unterricht_dir = tmp_path / "Unterricht"
    repo.load_snapshot(unterricht_dir)

    node_path = fachinhalte_root / "Mathematik" / "AB-1.md"
    node_path.write_text(_node_text(titel="Neuer Titel Nach Aenderung"), encoding="utf-8")

    snapshot, diagnostics, _loaded_subjects = repo.load_snapshot(unterricht_dir)

    assert diagnostics == ()
    assert snapshot.nodes["AB-1"].title == "Neuer Titel Nach Aenderung"


def test_unreadable_file_yields_diagnostic_without_crashing(tmp_path, monkeypatch):
    fachinhalte_root = _build_vault(tmp_path)
    node_path = fachinhalte_root / "Mathematik" / "AB-1.md"
    repo = _repo_with_fachinhalte_root(monkeypatch, fachinhalte_root)

    original_read_text = module.Path.read_text

    def _raise_for_target(self, *args, **kwargs):
        if self == node_path:
            raise OSError("simulierter gleichzeitiger Schreibzugriff")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(module.Path, "read_text", _raise_for_target)

    snapshot, diagnostics, _loaded_subjects = repo.load_snapshot(tmp_path / "Unterricht")

    assert "AB-1" not in snapshot.nodes
    assert any(diag.node_id == "AB-1" for diag in diagnostics)

    monkeypatch.setattr(module.Path, "read_text", original_read_text)
    snapshot_retry, diagnostics_retry, _loaded_subjects = repo.load_snapshot(tmp_path / "Unterricht")

    assert "AB-1" in snapshot_retry.nodes
    assert diagnostics_retry == ()


def test_corrupted_cache_file_triggers_full_rebuild_instead_of_crash(tmp_path, monkeypatch):
    fachinhalte_root = _build_vault(tmp_path)
    repo = _repo_with_fachinhalte_root(monkeypatch, fachinhalte_root)

    cache_path = cache_module.cache_file_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("{ das ist kein gueltiges JSON", encoding="utf-8")

    snapshot, diagnostics, _loaded_subjects = repo.load_snapshot(tmp_path / "Unterricht")

    assert diagnostics == ()
    assert set(snapshot.nodes.keys()) == {"AB-1", "AB-2"}


def test_cache_version_mismatch_triggers_full_rebuild(tmp_path, monkeypatch):
    fachinhalte_root = _build_vault(tmp_path)
    repo = _repo_with_fachinhalte_root(monkeypatch, fachinhalte_root)

    cache_path = cache_module.cache_file_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text('{"cache_version": 999, "files": {}}', encoding="utf-8")

    snapshot, diagnostics, _loaded_subjects = repo.load_snapshot(tmp_path / "Unterricht")

    assert diagnostics == ()
    assert set(snapshot.nodes.keys()) == {"AB-1", "AB-2"}


def test_discover_structured_subjects_finds_valid_subject_and_ignores_fake_one(tmp_path, monkeypatch):
    fachinhalte_root = _build_vault(tmp_path, subjects=("Mathematik",))
    # Ein Ordner mit passend benannter Datei, aber OHNE Bereiche/-Unterordner --
    # darf NICHT als strukturiertes Fach erkannt werden (Plausibilitaetsschranke).
    fake_subject_dir = fachinhalte_root / "Zufallsordner"
    fake_subject_dir.mkdir()
    (fake_subject_dir / "AB-1.md").write_text(_node_text(), encoding="utf-8")

    repo = _repo_with_fachinhalte_root(monkeypatch, fachinhalte_root)

    subjects = repo.discover_structured_subjects(tmp_path / "Unterricht")

    assert subjects == ("Mathematik",)


def test_invalidate_cache_clears_persisted_state(tmp_path, monkeypatch):
    fachinhalte_root = _build_vault(tmp_path)
    repo = _repo_with_fachinhalte_root(monkeypatch, fachinhalte_root)
    repo.load_snapshot(tmp_path / "Unterricht")

    assert cache_module.cache_file_path().exists()
    repo.invalidate_cache()

    persisted = cache_module.load_cache_from_disk()
    assert persisted == {}


def test_rebuild_snapshot_invalidates_before_loading(tmp_path, monkeypatch):
    fachinhalte_root = _build_vault(tmp_path)
    repo = _repo_with_fachinhalte_root(monkeypatch, fachinhalte_root)
    repo.load_snapshot(tmp_path / "Unterricht")

    snapshot, diagnostics, loaded_subjects = repo.rebuild_snapshot(tmp_path / "Unterricht")

    assert loaded_subjects == ("Mathematik",)
    assert diagnostics == ()
    assert set(snapshot.nodes.keys()) == {"AB-1", "AB-2"}


def test_read_body_returns_body_after_frontmatter(tmp_path, monkeypatch):
    fachinhalte_root = _build_vault(tmp_path)
    repo = _repo_with_fachinhalte_root(monkeypatch, fachinhalte_root)
    node_path = fachinhalte_root / "Mathematik" / "AB-1.md"

    body = repo.read_body(node_path)

    assert body.strip() == "# Titel der Kompetenz"
