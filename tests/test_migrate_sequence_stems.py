"""Tests für tools/migrate_sequence_stems.py.

Prüft das Umbenennen von Sequenz-Brainstorming-Dateien vom alten Schema
``<Sequenzname> <Gruppe> <HJ>`` auf das neue Schema ``<Gruppe> <Sequenzname>``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Repo-Root in den Suchpfad aufnehmen damit tools-Importe funktionieren.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.migrate_sequence_stems import (
    _parse_frontmatter_field,
    _replace_wiki_links_in_file,
    migrate_sequence_directory,
    _migrate_sequence_file,
)


def _make_sequence_file(path: Path, sequenzname: str, lerngruppe: str) -> None:
    """Legt eine minimale Sequenz-Markdown-Datei an."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\nKursplan: "[[M li2 26-2]]"\nSequenzname: "{sequenzname}"\n'
        f'Lerngruppe: "{lerngruppe}"\nHalbjahr: "26-2"\nSequenzziel: ""\n---\n\n'
        f"# {path.stem}\n\n## Brainstorming\n\n## Export\n",
        encoding="utf-8",
    )


class TestParseFrontmatterField:
    """Hilfsfunktion _parse_frontmatter_field."""

    def test_reads_sequenzname(self, tmp_path):
        f = tmp_path / "seq.md"
        _make_sequence_file(f, "Kodierung", "[[li2]]")
        text = f.read_text(encoding="utf-8")
        assert _parse_frontmatter_field(text, "Sequenzname") == "Kodierung"

    def test_reads_lerngruppe(self, tmp_path):
        f = tmp_path / "seq.md"
        _make_sequence_file(f, "Analysis", "[[GK blau-1]]")
        text = f.read_text(encoding="utf-8")
        assert _parse_frontmatter_field(text, "Lerngruppe") == "[[GK blau-1]]"

    def test_missing_field_returns_empty_string(self, tmp_path):
        f = tmp_path / "seq.md"
        f.write_text("---\nFoo: bar\n---\n", encoding="utf-8")
        assert _parse_frontmatter_field(f.read_text(encoding="utf-8"), "Sequenzname") == ""


class TestReplaceWikiLinksInFile:
    """Hilfsfunktion _replace_wiki_links_in_file."""

    def test_replaces_simple_link(self, tmp_path):
        f = tmp_path / "plan.md"
        f.write_text("Siehe [[Kodierung li2 26-2]] hier.", encoding="utf-8")
        changed = _replace_wiki_links_in_file(f, "Kodierung li2 26-2", "li2 Kodierung")
        assert changed is True
        assert "[[li2 Kodierung]]" in f.read_text(encoding="utf-8")

    def test_replaces_alias_link(self, tmp_path):
        f = tmp_path / "plan.md"
        f.write_text("Ref: [[Kodierung li2 26-2|Sequenz]].", encoding="utf-8")
        _replace_wiki_links_in_file(f, "Kodierung li2 26-2", "li2 Kodierung")
        assert "[[li2 Kodierung|Sequenz]]" in f.read_text(encoding="utf-8")

    def test_does_not_replace_different_stem(self, tmp_path):
        f = tmp_path / "plan.md"
        f.write_text("Ref: [[Analysis li2 26-2]].", encoding="utf-8")
        changed = _replace_wiki_links_in_file(f, "Kodierung li2 26-2", "li2 Kodierung")
        assert changed is False
        assert "[[Analysis li2 26-2]]" in f.read_text(encoding="utf-8")

    def test_partial_name_in_longer_stem_is_not_replaced(self, tmp_path):
        """Ein Stem der nur TEIL eines anderen Stems ist darf nicht ersetzt werden."""
        f = tmp_path / "plan.md"
        f.write_text("Ref: [[li2 Kodierung Extra]].", encoding="utf-8")
        changed = _replace_wiki_links_in_file(f, "li2 Kodierung", "li2 Neu")
        assert changed is False


class TestMigrateSequenceFile:
    """_migrate_sequence_file: einzelne Datei umbenennen."""

    def test_renames_old_format_file(self, tmp_path):
        seq_dir = tmp_path / "Sequenzen"
        old_file = seq_dir / "Kodierung li2 26-2.md"
        _make_sequence_file(old_file, "Kodierung", "[[li2]]")

        result = _migrate_sequence_file(old_file)

        assert result is not None
        old_stem, new_stem = result
        assert old_stem == "Kodierung li2 26-2"
        assert new_stem == "li2 Kodierung"
        assert not old_file.exists()
        assert (seq_dir / "li2 Kodierung.md").exists()

    def test_already_correct_format_returns_none(self, tmp_path):
        seq_dir = tmp_path / "Sequenzen"
        correct_file = seq_dir / "li2 Kodierung.md"
        _make_sequence_file(correct_file, "Kodierung", "[[li2]]")

        result = _migrate_sequence_file(correct_file)

        assert result is None
        assert correct_file.exists()

    def test_collision_raises_file_exists_error(self, tmp_path):
        seq_dir = tmp_path / "Sequenzen"
        old_file = seq_dir / "Kodierung li2 26-2.md"
        _make_sequence_file(old_file, "Kodierung", "[[li2]]")
        # Zieldatei existiert bereits
        (seq_dir / "li2 Kodierung.md").write_text("# existing\n", encoding="utf-8")

        with pytest.raises(FileExistsError, match="Kollision"):
            _migrate_sequence_file(old_file)

    def test_missing_frontmatter_field_raises(self, tmp_path):
        seq_dir = tmp_path / "Sequenzen"
        broken = seq_dir / "broken.md"
        broken.parent.mkdir(parents=True, exist_ok=True)
        broken.write_text("---\nFoo: bar\n---\n", encoding="utf-8")

        with pytest.raises(RuntimeError, match="Fehlendes"):
            _migrate_sequence_file(broken)


class TestMigrateSequenceDirectory:
    """migrate_sequence_directory: vollständiger Ordnerdurchlauf."""

    def test_renames_files_and_updates_plan_references(self, tmp_path):
        plan_dir = tmp_path / "Unterricht" / "M li2 26-2"
        seq_dir = plan_dir / "Sequenzen"

        old_file = seq_dir / "Kodierung li2 26-2.md"
        _make_sequence_file(old_file, "Kodierung", "[[li2]]")

        # Plan-Datei mit Link auf alten Stem
        plan_md = plan_dir / "M li2 26-2.md"
        plan_md.write_text(
            "# Plan\n\nSequenz: [[Kodierung li2 26-2]]\n", encoding="utf-8"
        )

        renamed, skipped, collisions = migrate_sequence_directory(seq_dir)

        assert renamed == 1
        assert skipped == 0
        assert collisions == 0
        assert not old_file.exists()
        assert (seq_dir / "li2 Kodierung.md").exists()
        assert "[[li2 Kodierung]]" in plan_md.read_text(encoding="utf-8")

    def test_skips_already_correct_files(self, tmp_path):
        plan_dir = tmp_path / "Unterricht" / "M li2 26-2"
        seq_dir = plan_dir / "Sequenzen"
        correct = seq_dir / "li2 Kodierung.md"
        _make_sequence_file(correct, "Kodierung", "[[li2]]")

        renamed, skipped, collisions = migrate_sequence_directory(seq_dir)

        assert renamed == 0
        assert skipped == 1
        assert collisions == 0

    def test_collision_counted_and_file_untouched(self, tmp_path):
        plan_dir = tmp_path / "Unterricht" / "M li2 26-2"
        seq_dir = plan_dir / "Sequenzen"
        old_file = seq_dir / "Kodierung li2 26-2.md"
        _make_sequence_file(old_file, "Kodierung", "[[li2]]")
        (seq_dir / "li2 Kodierung.md").write_text("# existing\n", encoding="utf-8")

        renamed, skipped, collisions = migrate_sequence_directory(seq_dir)

        assert renamed == 0
        assert collisions == 1
        assert old_file.exists()

    def test_multiple_files_all_renamed(self, tmp_path):
        plan_dir = tmp_path / "Unterricht" / "M li2 26-2"
        seq_dir = plan_dir / "Sequenzen"
        _make_sequence_file(seq_dir / "Kodierung li2 26-2.md", "Kodierung", "[[li2]]")
        _make_sequence_file(seq_dir / "Algorithmen li2 26-2.md", "Algorithmen", "[[li2]]")

        renamed, skipped, collisions = migrate_sequence_directory(seq_dir)

        assert renamed == 2
        assert (seq_dir / "li2 Kodierung.md").exists()
        assert (seq_dir / "li2 Algorithmen.md").exists()

    def test_other_md_files_with_unrelated_links_are_not_changed(self, tmp_path):
        """Links auf andere Dateien mit anderem Stem bleiben unberührt."""
        plan_dir = tmp_path / "Unterricht" / "M li2 26-2"
        seq_dir = plan_dir / "Sequenzen"
        _make_sequence_file(seq_dir / "Kodierung li2 26-2.md", "Kodierung", "[[li2]]")

        other_md = plan_dir / "other.md"
        other_md.write_text("Ref: [[Andere Datei]].\n", encoding="utf-8")

        migrate_sequence_directory(seq_dir)

        assert "[[Andere Datei]]" in other_md.read_text(encoding="utf-8")
