"""Tests für `tools/migrate_ub_development_frontmatter.py` (synthetische UB-Dateien)."""

from pathlib import Path

from kursplaner.core.domain.unterrichtsbesuch_policy import ub_development_lists
from kursplaner.core.usecases.ub_markdown_sections import parse_reflection
from kursplaner.infrastructure.repositories.ub_repository import FileSystemUbRepository
from tools.migrate_ub_development_frontmatter import main

FRONTMATTER = '---\nBereich:\n  - "Pädagogik"\nLangentwurf: false\nBeobachtungsschwerpunkt:\nEinheit: "[[ab12cd]]"\n---\n'


def _legacy(ub_dir: Path, name: str, steps: str, resources: str, before: str = "") -> Path:
    path = ub_dir / f"{name}.md"
    path.write_text(
        f"{FRONTMATTER}\n{before}# Reflexion\n\nGut gelaufen.\n\n"
        f"## Professionalisierungsschritte\n\n{steps}\n\n## Nutzbare Ressourcen\n\n{resources}\n",
        encoding="utf-8",
    )
    return path


def test_dry_run_writes_nothing(tmp_path):
    path = _legacy(tmp_path, "ub 26-02-06", "- Pause machen", "- Ritual")
    before = path.read_text(encoding="utf-8")

    assert main(["--dry-run", "--ub-dir", str(tmp_path)]) == 0

    assert path.read_text(encoding="utf-8") == before


def test_moves_lists_to_frontmatter_and_keeps_rest_of_body(tmp_path):
    path = _legacy(
        tmp_path,
        "ub 26-10-29",
        "- Lernhilfen nutzen\n- Ankern (mein Beispiel, *oder* ein eigenes)",
        "- ",
        before="# 1. Profil\n\nLangentwurf-Text.\n\n## 1.1 Lerngruppe\n\nMehr Text.\n\n",
    )

    assert main(["--ub-dir", str(tmp_path)]) == 0

    yaml_data, body = FileSystemUbRepository().load_ub_markdown(path)
    assert ub_development_lists(yaml_data) == (["Lernhilfen nutzen", "Ankern (mein Beispiel, *oder* ein eigenes)"], [])
    assert "Professionalisierungsschritte" not in body and "Nutzbare Ressourcen" not in body
    assert "Langentwurf-Text." in body and "## 1.1 Lerngruppe" in body
    assert parse_reflection(body) == "Gut gelaufen."


def test_second_run_finds_nothing(tmp_path, capsys):
    _legacy(tmp_path, "ub 26-02-06", "- Pause machen", "- Ritual")
    assert main(["--ub-dir", str(tmp_path)]) == 0
    capsys.readouterr()

    assert main(["--ub-dir", str(tmp_path)]) == 0
    assert "0 Datei(en) migriert" in capsys.readouterr().out


def test_other_notes_in_ub_folder_are_ignored(tmp_path):
    note = tmp_path / "Leitfaden.md"
    note.write_text("# Leitfaden\n\nKein Frontmatter.\n", encoding="utf-8")

    assert main(["--ub-dir", str(tmp_path)]) == 0
    assert note.read_text(encoding="utf-8") == "# Leitfaden\n\nKein Frontmatter.\n"


def test_invalid_entry_skips_file_and_reports(tmp_path):
    path = _legacy(tmp_path, "ub 26-02-06", "- ---", "- Ritual")
    before = path.read_text(encoding="utf-8")

    assert main(["--ub-dir", str(tmp_path)]) == 1

    assert path.read_text(encoding="utf-8") == before
