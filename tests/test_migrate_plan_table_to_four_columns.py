"""Tests für tools/migrate_plan_table_to_four_columns.py.

Prüft die Migration der Planungstabelle vom alten 3-Spalten-Format
(Datum | Stunden | Inhalt) auf das neue 4-Spalten-Format
(Datum | Stunden | Inhalt | Thema/Ausfall).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.migrate_plan_table_to_four_columns import (
    _build_thema_ausfall,
    _migrate_row,
    _parse_three_column_table,
    _read_yaml_scalar,
    migrate_plan_file,
)

_PLAN_FRONTMATTER = (
    "---\n"
    'Lerngruppe: "[[li2]]"\n'
    'Kursfach: "Informatik"\n'
    "Stufe: 10\n"
    "---\n\n"
)


def _make_lesson_file(einheiten_dir: Path, stem: str, stundentyp: str, oberthema: str) -> Path:
    """Legt eine minimale Stunden-YAML-Datei im Einheiten-Ordner an."""
    einheiten_dir.mkdir(parents=True, exist_ok=True)
    path = einheiten_dir / f"{stem}.md"
    path.write_text(
        f"---\nStundentyp: {stundentyp}\nOberthema: {oberthema}\n---\n",
        encoding="utf-8",
    )
    return path


def _make_plan_file(plan_dir: Path, rows: list[str]) -> Path:
    """Legt eine Kurs-Markdown-Datei mit 3-Spalten-Tabelle an."""
    plan_dir.mkdir(parents=True, exist_ok=True)
    body = (
        "| Datum | Stunden | Inhalt |\n"
        "| --- | --- | --- |\n"
        + "".join(rows)
    )
    plan_path = plan_dir / f"{plan_dir.name}.md"
    plan_path.write_text(_PLAN_FRONTMATTER + body, encoding="utf-8")
    return plan_path


class TestReadYamlScalar:
    """_read_yaml_scalar: Hilfsfunktion für einfaches YAML-Lesen."""

    def test_reads_simple_field(self):
        text = "---\nStundentyp: LZK\n---\n"
        assert _read_yaml_scalar(text, "Stundentyp") == "LZK"

    def test_strips_quotes(self):
        text = '---\nOberthema: "Kodierung"\n---\n'
        assert _read_yaml_scalar(text, "Oberthema") == "Kodierung"

    def test_missing_field_returns_empty(self):
        text = "---\nFoo: bar\n---\n"
        assert _read_yaml_scalar(text, "Stundentyp") == ""

    def test_no_frontmatter_returns_empty(self):
        assert _read_yaml_scalar("# Kein Frontmatter\n", "Stundentyp") == ""


class TestBuildThemaAusfall:
    """_build_thema_ausfall: Spalteninhalt aus Stundentyp + Oberthema."""

    def test_unterricht_with_oberthema(self):
        assert _build_thema_ausfall("Unterricht", "Kodierung", "li2") == "[[li2 Kodierung]]"

    def test_lzk_with_oberthema(self):
        assert _build_thema_ausfall("LZK", "Kodierung", "li2") == "LZK [[li2 Kodierung]]"

    def test_hospitation_with_oberthema(self):
        assert _build_thema_ausfall("Hospitation", "Sortierung", "li2") == "[[li2 Sortierung]]"

    def test_empty_oberthema_returns_empty(self):
        assert _build_thema_ausfall("Unterricht", "", "li2") == ""

    def test_lzk_empty_oberthema_returns_empty(self):
        assert _build_thema_ausfall("LZK", "", "li2") == ""


class TestMigrateRow:
    """_migrate_row: Einzelzeilen-Konvertierung von 3 auf 4 Spalten."""

    def test_empty_inhalt_produces_two_empty_cols(self, tmp_path):
        row = _migrate_row(["10-03-26", "2", ""], tmp_path, "li2")
        assert row == ["10-03-26", "2", "", ""]

    def test_ausfall_with_x_prefix_moves_to_col3(self, tmp_path):
        row = _migrate_row(["10-03-26", "0", "X Ferien"], tmp_path, "li2")
        assert row == ["10-03-26", "0", "", "X Ferien"]

    def test_ausfall_without_x_prefix_gets_normalized(self, tmp_path):
        row = _migrate_row(["10-03-26", "0", "Ferien"], tmp_path, "li2")
        assert row == ["10-03-26", "0", "", "X Ferien"]

    def test_lone_x_is_preserved(self, tmp_path):
        row = _migrate_row(["10-03-26", "0", "X"], tmp_path, "li2")
        assert row == ["10-03-26", "0", "", "X"]

    def test_wiki_link_stays_in_col2(self, tmp_path):
        einheiten = tmp_path / "Einheiten"
        _make_lesson_file(einheiten, "li2 03-10 Kodierung", "Unterricht", "Kodierung")
        row = _migrate_row(["10-03-26", "2", "[[li2 03-10 Kodierung]]"], tmp_path, "li2")
        assert row[2] == "[[li2 03-10 Kodierung]]"
        assert row[3] == "[[li2 Kodierung]]"

    def test_wiki_link_lzk_builds_lzk_prefix(self, tmp_path):
        einheiten = tmp_path / "Einheiten"
        _make_lesson_file(einheiten, "li2 03-10 LZK", "LZK", "Kodierung")
        row = _migrate_row(["10-03-26", "2", "[[li2 03-10 LZK]]"], tmp_path, "li2")
        assert row[3] == "LZK [[li2 Kodierung]]"

    def test_missing_lesson_file_leaves_col3_empty(self, tmp_path):
        row = _migrate_row(["10-03-26", "2", "[[li2 03-10 NichtVorhanden]]"], tmp_path, "li2")
        assert row[2] == "[[li2 03-10 NichtVorhanden]]"
        assert row[3] == ""

    def test_empty_oberthema_in_yaml_leaves_col3_empty(self, tmp_path):
        einheiten = tmp_path / "Einheiten"
        _make_lesson_file(einheiten, "li2 03-10 OhneThema", "Unterricht", "")
        row = _migrate_row(["10-03-26", "2", "[[li2 03-10 OhneThema]]"], tmp_path, "li2")
        assert row[3] == ""


class TestParseThreeColumnTable:
    """_parse_three_column_table: eigener toleranter 3-Spalten-Parser."""

    def test_finds_table_and_returns_rows(self, tmp_path):
        plan_dir = tmp_path / "M li2 26-1"
        plan_path = _make_plan_file(plan_dir, ["| 10-03-26 | 2 | [[abc]] |\n"])
        result = _parse_three_column_table(plan_path)
        assert result is not None
        rows, _, start, end, _ = result
        assert len(rows) == 1
        assert rows[0][2] == "[[abc]]"
        assert start < end

    def test_returns_none_for_four_column_table(self, tmp_path):
        plan_dir = tmp_path / "M li2 26-1"
        plan_dir.mkdir(parents=True)
        path = plan_dir / f"{plan_dir.name}.md"
        path.write_text(
            _PLAN_FRONTMATTER
            + "| Datum | Stunden | Inhalt | Thema/Ausfall |\n"
            + "| --- | --- | --- | --- |\n"
            + "| 10-03-26 | 2 | [[abc]] |  |\n",
            encoding="utf-8",
        )
        assert _parse_three_column_table(path) is None

    def test_returns_none_when_no_table(self, tmp_path):
        plan_dir = tmp_path / "M li2 26-1"
        plan_dir.mkdir(parents=True)
        path = plan_dir / f"{plan_dir.name}.md"
        path.write_text(_PLAN_FRONTMATTER + "Kein Tabelleninhalt.\n", encoding="utf-8")
        assert _parse_three_column_table(path) is None


class TestMigratePlanFile:
    """migrate_plan_file: vollständige Datei-Migration."""

    def test_unterricht_row_migrated_correctly(self, tmp_path):
        """Wiki-Link in col 2 → Oberthema-Link in col 3."""
        plan_dir = tmp_path / "M li2 26-1"
        einheiten = plan_dir / "Einheiten"
        _make_lesson_file(einheiten, "li2 03-10 Kodierung", "Unterricht", "Kodierung")
        plan_path = _make_plan_file(plan_dir, ["| 10-03-26 | 2 | [[li2 03-10 Kodierung]] |\n"])

        status = migrate_plan_file(plan_path)
        assert status == "migrated"
        text = plan_path.read_text(encoding="utf-8")
        assert "Thema/Ausfall" in text
        assert "[[li2 Kodierung]]" in text
        assert "[[li2 03-10 Kodierung]]" in text

    def test_lzk_row_builds_lzk_prefix(self, tmp_path):
        plan_dir = tmp_path / "M li2 26-1"
        einheiten = plan_dir / "Einheiten"
        _make_lesson_file(einheiten, "li2 03-10 LZK1", "LZK", "Kodierung")
        plan_path = _make_plan_file(plan_dir, ["| 10-03-26 | 2 | [[li2 03-10 LZK1]] |\n"])

        migrate_plan_file(plan_path)
        text = plan_path.read_text(encoding="utf-8")
        assert "LZK [[li2 Kodierung]]" in text

    def test_ausfall_row_without_x_prefix_gets_normalized(self, tmp_path):
        plan_dir = tmp_path / "M li2 26-1"
        plan_path = _make_plan_file(plan_dir, ["| 10-03-26 | 0 | Ferien |\n"])

        migrate_plan_file(plan_path)
        text = plan_path.read_text(encoding="utf-8")
        assert "X Ferien" in text

    def test_ausfall_row_with_x_prefix_preserved(self, tmp_path):
        plan_dir = tmp_path / "M li2 26-1"
        plan_path = _make_plan_file(plan_dir, ["| 10-03-26 | 0 | X Krankheit |\n"])

        migrate_plan_file(plan_path)
        text = plan_path.read_text(encoding="utf-8")
        assert "X Krankheit" in text

    def test_empty_row_stays_empty(self, tmp_path):
        plan_dir = tmp_path / "M li2 26-1"
        plan_path = _make_plan_file(plan_dir, ["| 10-03-26 | 0 |  |\n"])

        migrate_plan_file(plan_path)
        text = plan_path.read_text(encoding="utf-8")
        assert "| 10-03-26 | 0 |  |  |" in text

    def test_missing_lesson_file_leaves_col3_empty(self, tmp_path):
        plan_dir = tmp_path / "M li2 26-1"
        plan_path = _make_plan_file(plan_dir, ["| 10-03-26 | 2 | [[li2 03-10 NichtVorhanden]] |\n"])

        migrate_plan_file(plan_path)
        text = plan_path.read_text(encoding="utf-8")
        assert "[[li2 03-10 NichtVorhanden]]" in text
        assert "| [[li2 03-10 NichtVorhanden]] |  |" in text

    def test_already_four_columns_skipped(self, tmp_path):
        plan_dir = tmp_path / "M li2 26-1"
        plan_dir.mkdir(parents=True)
        plan_path = plan_dir / f"{plan_dir.name}.md"
        plan_path.write_text(
            _PLAN_FRONTMATTER
            + "| Datum | Stunden | Inhalt | Thema/Ausfall |\n"
            + "| --- | --- | --- | --- |\n"
            + "| 10-03-26 | 2 | [[abc]] | [[li2 Kodierung]] |\n",
            encoding="utf-8",
        )
        original = plan_path.read_text(encoding="utf-8")

        status = migrate_plan_file(plan_path)
        assert status == "skipped"
        assert plan_path.read_text(encoding="utf-8") == original

    def test_multiple_rows_all_migrated(self, tmp_path):
        plan_dir = tmp_path / "M li2 26-1"
        einheiten = plan_dir / "Einheiten"
        _make_lesson_file(einheiten, "li2 03-10 A", "Unterricht", "Thema A")
        _make_lesson_file(einheiten, "li2 03-12 B", "LZK", "Thema A")
        plan_path = _make_plan_file(
            plan_dir,
            [
                "| 10-03-26 | 2 | [[li2 03-10 A]] |\n",
                "| 12-03-26 | 2 | [[li2 03-12 B]] |\n",
                "| 14-03-26 | 0 | X Krankheit |\n",
            ],
        )

        migrate_plan_file(plan_path)
        text = plan_path.read_text(encoding="utf-8")
        assert "[[li2 Thema A]]" in text
        assert "LZK [[li2 Thema A]]" in text
        assert "X Krankheit" in text
        table_separator_lines = [l for l in text.splitlines() if l.strip().startswith("| ---")]
        assert len(table_separator_lines) == 1
