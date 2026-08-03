"""Tests für tools/migrate_lesson_filenames_to_random_codes.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.migrate_lesson_filenames_to_random_codes import (
    _collect_all_existing_stems,
    _replace_wiki_links_in_file,
    is_legacy_lesson_stem,
    migrate_plan_file,
)

_PLAN_FRONTMATTER = (
    "---\n"
    'Lerngruppe: "[[grün-6]]"\n'
    'Kursfach: "Informatik"\n'
    "Stufe: 10\n"
    "---\n\n"
)


def _make_plan_file(plan_dir: Path, rows: list[list[str]]) -> Path:
    """Legt eine Kurs-MD mit 4-Spalten-Tabelle an."""
    plan_dir.mkdir(parents=True, exist_ok=True)
    body = (
        "| Datum | Stunden | Inhalt | Thema/Ausfall |\n"
        "| --- | --- | --- | --- |\n"
        + "".join(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |\n" for r in rows)
    )
    plan_path = plan_dir / f"{plan_dir.name}.md"
    plan_path.write_text(_PLAN_FRONTMATTER + body, encoding="utf-8")
    return plan_path


def _make_lesson(einheiten: Path, stem: str) -> Path:
    einheiten.mkdir(parents=True, exist_ok=True)
    p = einheiten / f"{stem}.md"
    p.write_text(
        "---\nStundentyp: Unterricht\nOberthema: Kodierung\n---\n",
        encoding="utf-8",
    )
    return p


class TestIsLegacyLessonStem:
    """is_legacy_lesson_stem: Erkennung des alten Benennungsschemas."""

    def test_old_style_stem_is_legacy(self):
        assert is_legacy_lesson_stem("grün-6 03-13 Binärdaten") is True

    def test_multiple_words_before_date_is_legacy(self):
        assert is_legacy_lesson_stem("GK blau-1 05-20 Analysis Einführung") is True

    def test_six_char_code_is_not_legacy(self):
        assert is_legacy_lesson_stem("ab12cd") is False

    def test_only_date_token_is_not_legacy(self):
        assert is_legacy_lesson_stem("03-13") is False

    def test_date_at_start_is_not_legacy(self):
        assert is_legacy_lesson_stem("03-13 Binärdaten") is False

    def test_empty_string_is_not_legacy(self):
        assert is_legacy_lesson_stem("") is False


class TestReplaceWikiLinksInFile:
    """_replace_wiki_links_in_file: Wiki-Link-Ersetzung in Markdown-Dateien."""

    def test_simple_link_replaced(self, tmp_path):
        f = tmp_path / "ref.md"
        f.write_text("Ref: [[grün-6 03-13 Kodierung]] hier.", encoding="utf-8")
        changed = _replace_wiki_links_in_file(f, "grün-6 03-13 Kodierung", "ab12cd")
        assert changed is True
        assert "[[ab12cd]]" in f.read_text(encoding="utf-8")

    def test_alias_link_replaced(self, tmp_path):
        f = tmp_path / "ref.md"
        f.write_text("Ref: [[grün-6 03-13 Kodierung|Kodierung]].", encoding="utf-8")
        _replace_wiki_links_in_file(f, "grün-6 03-13 Kodierung", "ab12cd")
        assert "[[ab12cd|Kodierung]]" in f.read_text(encoding="utf-8")

    def test_other_link_untouched(self, tmp_path):
        f = tmp_path / "ref.md"
        f.write_text("Ref: [[andere Datei]] und [[grün-6 05-10 Anderes]].", encoding="utf-8")
        changed = _replace_wiki_links_in_file(f, "grün-6 03-13 Kodierung", "ab12cd")
        assert changed is False
        assert "[[andere Datei]]" in f.read_text(encoding="utf-8")

    def test_partial_stem_not_replaced(self, tmp_path):
        """Ein Stem der Teilstring eines anderen ist darf nicht ersetzt werden."""
        f = tmp_path / "ref.md"
        f.write_text("Ref: [[grün-6 03-13 Kodierung Extra]].", encoding="utf-8")
        changed = _replace_wiki_links_in_file(f, "grün-6 03-13 Kodierung", "ab12cd")
        assert changed is False


class TestCollectAllExistingStems:
    """_collect_all_existing_stems: vault-weiter Stem-Index."""

    def test_collects_from_einheiten(self, tmp_path):
        plan_dir = tmp_path / "M li2 26-1"
        einheiten = plan_dir / "Einheiten"
        einheiten.mkdir(parents=True)
        (einheiten / "ab12cd.md").write_text("", encoding="utf-8")
        stems = _collect_all_existing_stems(tmp_path)
        assert "ab12cd" in stems

    def test_collects_from_alteinheiten(self, tmp_path):
        plan_dir = tmp_path / "M li2 26-1"
        alteinheiten = plan_dir / "Alteinheiten"
        alteinheiten.mkdir(parents=True)
        (alteinheiten / "zz99aa.md").write_text("", encoding="utf-8")
        stems = _collect_all_existing_stems(tmp_path)
        assert "zz99aa" in stems

    def test_ignores_non_md_files(self, tmp_path):
        plan_dir = tmp_path / "M li2 26-1"
        einheiten = plan_dir / "Einheiten"
        einheiten.mkdir(parents=True)
        (einheiten / "notes.txt").write_text("", encoding="utf-8")
        stems = _collect_all_existing_stems(tmp_path)
        assert "notes" not in stems


class TestMigratePlanFile:
    """migrate_plan_file: vollständige Datei-Migration."""

    def test_legacy_stem_renamed_to_six_char_code(self, tmp_path):
        plan_dir = tmp_path / "M li2 26-1"
        einheiten = plan_dir / "Einheiten"
        _make_lesson(einheiten, "grün-6 03-13 Kodierung")
        plan_path = _make_plan_file(
            plan_dir, [["10-03-26", "2", "[[grün-6 03-13 Kodierung]]", "[[grün-6 Kodierung]]"]]
        )
        global_stems: set[str] = {"grün-6 03-13 Kodierung"}

        renamed, _ = migrate_plan_file(plan_path, tmp_path, global_stems)

        assert renamed == 1
        new_files = list(einheiten.glob("*.md"))
        assert len(new_files) == 1
        new_stem = new_files[0].stem
        assert len(new_stem) == 6
        assert new_stem.isalnum() and new_stem == new_stem.lower()
        assert not (einheiten / "grün-6 03-13 Kodierung.md").exists()
        text = plan_path.read_text(encoding="utf-8")
        assert f"[[{new_stem}]]" in text

    def test_six_char_stem_skipped(self, tmp_path):
        """Zeilen mit bereits aktuellem Stem werden übersprungen."""
        plan_dir = tmp_path / "M li2 26-1"
        einheiten = plan_dir / "Einheiten"
        _make_lesson(einheiten, "ab12cd")
        plan_path = _make_plan_file(
            plan_dir, [["10-03-26", "2", "[[ab12cd]]", "[[grün-6 Kodierung]]"]]
        )
        global_stems: set[str] = {"ab12cd"}
        original = plan_path.read_text(encoding="utf-8")

        renamed, _ = migrate_plan_file(plan_path, tmp_path, global_stems)

        assert renamed == 0
        assert plan_path.read_text(encoding="utf-8") == original

    def test_other_md_files_in_vault_updated_globally(self, tmp_path):
        """Wiki-Links in anderen Markdown-Dateien werden ebenfalls aktualisiert."""
        plan_dir = tmp_path / "M li2 26-1"
        einheiten = plan_dir / "Einheiten"
        _make_lesson(einheiten, "grün-6 03-13 Kodierung")
        plan_path = _make_plan_file(
            plan_dir, [["10-03-26", "2", "[[grün-6 03-13 Kodierung]]", ""]]
        )
        other_md = tmp_path / "Materialien" / "ref.md"
        other_md.parent.mkdir(parents=True)
        other_md.write_text("Ref: [[grün-6 03-13 Kodierung]].\n", encoding="utf-8")

        migrate_plan_file(plan_path, tmp_path, set())

        new_stem = list(einheiten.glob("*.md"))[0].stem
        assert f"[[{new_stem}]]" in other_md.read_text(encoding="utf-8")
        assert "[[grün-6 03-13 Kodierung]]" not in other_md.read_text(encoding="utf-8")

    def test_unrelated_links_in_other_files_untouched(self, tmp_path):
        """Links auf andere Dateien bleiben unverändert."""
        plan_dir = tmp_path / "M li2 26-1"
        einheiten = plan_dir / "Einheiten"
        _make_lesson(einheiten, "grün-6 03-13 Kodierung")
        plan_path = _make_plan_file(
            plan_dir, [["10-03-26", "2", "[[grün-6 03-13 Kodierung]]", ""]]
        )
        other_md = tmp_path / "other.md"
        other_md.write_text("Ref: [[Andere Datei]].\n", encoding="utf-8")

        migrate_plan_file(plan_path, tmp_path, set())

        assert "[[Andere Datei]]" in other_md.read_text(encoding="utf-8")

    def test_missing_lesson_file_skipped_no_crash(self, tmp_path):
        """Fehlende Stundendatei führt zu keinem Absturz."""
        plan_dir = tmp_path / "M li2 26-1"
        plan_path = _make_plan_file(
            plan_dir, [["10-03-26", "2", "[[grün-6 03-13 NichtVorhanden]]", ""]]
        )
        renamed, _ = migrate_plan_file(plan_path, tmp_path, set())
        assert renamed == 0

    def test_duplicate_stem_in_two_rows_renamed_once(self, tmp_path):
        """Dasselbe Stem in zwei Zeilen führt zu genau einer Umbenennung."""
        plan_dir = tmp_path / "M li2 26-1"
        einheiten = plan_dir / "Einheiten"
        _make_lesson(einheiten, "grün-6 03-13 Kodierung")
        plan_path = _make_plan_file(
            plan_dir,
            [
                ["10-03-26", "2", "[[grün-6 03-13 Kodierung]]", ""],
                ["12-03-26", "2", "[[grün-6 03-13 Kodierung]]", ""],
            ],
        )
        renamed, _ = migrate_plan_file(plan_path, tmp_path, set())
        assert renamed == 1
        new_files = list(einheiten.glob("*.md"))
        assert len(new_files) == 1
        new_stem = new_files[0].stem
        text = plan_path.read_text(encoding="utf-8")
        assert text.count(f"[[{new_stem}]]") == 2

    def test_generated_stems_are_unique_across_files(self, tmp_path):
        """Zwei Kurs-MDs teilen denselben global_stems-Pool ohne Duplikate."""
        global_stems: set[str] = set()

        for i, course in enumerate(["M li2 26-1", "M li3 26-1"]):
            plan_dir = tmp_path / course
            einheiten = plan_dir / "Einheiten"
            _make_lesson(einheiten, f"grün-6 03-{i + 10:02d} Kodierung")
            _make_plan_file(
                plan_dir,
                [[f"{i + 10:02d}-03-26", "2", f"[[grün-6 03-{i + 10:02d} Kodierung]]", ""]],
            )

        for course in ["M li2 26-1", "M li3 26-1"]:
            plan_path = tmp_path / course / f"{course}.md"
            migrate_plan_file(plan_path, tmp_path, global_stems)

        all_new_stems = [
            p.stem
            for course in ["M li2 26-1", "M li3 26-1"]
            for p in (tmp_path / course / "Einheiten").glob("*.md")
        ]
        assert len(all_new_stems) == 2
        assert len(set(all_new_stems)) == 2
