from kursplaner.core.config import path_store as module
from kursplaner.core.config.path_store import (
    BAUKASTEN_DIR_KEY,
    FACHINHALTE_DIR_KEY,
    resolve_fachinhalte_root,
)


def _patch_values(monkeypatch, values: dict[str, str]):
    monkeypatch.setattr(module, "load_path_values", lambda: values)


def test_uses_directly_configured_fachinhalte_path_if_it_exists(tmp_path, monkeypatch):
    configured = tmp_path / "Configured-Fachinhalte"
    configured.mkdir()
    _patch_values(monkeypatch, {FACHINHALTE_DIR_KEY: str(configured), BAUKASTEN_DIR_KEY: ""})

    result = resolve_fachinhalte_root(tmp_path / "Unterricht")

    assert result == configured.resolve()


def test_falls_back_to_named_child_search_under_baukasten(tmp_path, monkeypatch):
    baukasten = tmp_path / "Baukasten"
    fachinhalte = baukasten / "34 Fachinhalte"
    fachinhalte.mkdir(parents=True)
    _patch_values(monkeypatch, {FACHINHALTE_DIR_KEY: "", BAUKASTEN_DIR_KEY: str(baukasten)})

    result = resolve_fachinhalte_root(tmp_path / "Unterricht")

    assert result == fachinhalte.resolve()


def test_falls_back_to_historical_misspelling_fachenhalte(tmp_path, monkeypatch):
    baukasten = tmp_path / "Baukasten"
    fachinhalte = baukasten / "34 Fachenhalte"
    fachinhalte.mkdir(parents=True)
    _patch_values(monkeypatch, {FACHINHALTE_DIR_KEY: "", BAUKASTEN_DIR_KEY: str(baukasten)})

    result = resolve_fachinhalte_root(tmp_path / "Unterricht")

    assert result == fachinhalte.resolve()


def test_falls_back_to_baukasten_next_to_unterricht_dir_when_not_configured(tmp_path, monkeypatch):
    unterricht_dir = tmp_path / "Unterricht"
    unterricht_dir.mkdir()
    fachinhalte = tmp_path / "30 Baukasten" / "34 Fachinhalte"
    fachinhalte.mkdir(parents=True)
    _patch_values(monkeypatch, {FACHINHALTE_DIR_KEY: "", BAUKASTEN_DIR_KEY: ""})

    result = resolve_fachinhalte_root(unterricht_dir)

    assert result == fachinhalte.resolve()


def test_returns_none_when_nothing_resolves(tmp_path, monkeypatch):
    _patch_values(monkeypatch, {FACHINHALTE_DIR_KEY: "", BAUKASTEN_DIR_KEY: ""})

    result = resolve_fachinhalte_root(tmp_path / "Unterricht")

    assert result is None
