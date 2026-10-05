"""Stundendateien mit Blattwerk-Endung `.ebw` (Kurzentwurf) werden wie `.md` behandelt."""

from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.lesson_files import (
    is_lesson_file,
    lesson_stems,
    list_lesson_files,
    resolve_lesson_file,
    strip_lesson_suffix,
)
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.wiki_links import extract_wiki_link_target
from kursplaner.core.usecases.lesson_transfer_usecase import LessonTransferUseCase
from kursplaner.infrastructure.repositories.lesson_file_repository import FileSystemLessonFileRepository
from kursplaner.infrastructure.repositories.lesson_repository import FileSystemLessonRepository
from kursplaner.infrastructure.repositories.plan_table_file_repository import (
    get_row_link_path,
    load_linked_lesson_yaml,
    save_linked_lesson_yaml,
)

LESSON = "---\nStundentyp: Unterricht\nDauer: 2\nStundenthema: Brüche\ndocument_type: kurzentwurf\n---\n#einstieg\nS> Hallo\n"


def _table(plan_dir: Path, inhalt: str) -> PlanTableData:
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_md = plan_dir / f"{plan_dir.name}.md"
    plan_md.write_text("---\nKursfach: Mathematik\n---\n", encoding="utf-8")
    return PlanTableData(
        markdown_path=plan_md,
        headers=["Datum", "Stunden", "Inhalt"],
        rows=[["10-03-26", "2", inhalt]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=True,
        metadata={},
    )


def _lesson(directory: Path, name: str, text: str = LESSON) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


def test_suffix_helpers(tmp_path):
    ebw = _lesson(tmp_path, "ab12cd.ebw")
    _lesson(tmp_path, "cd34ef.md")
    _lesson(tmp_path, "notiz.txt")

    assert is_lesson_file(ebw) and not is_lesson_file(tmp_path / "notiz.txt")
    assert [p.name for p in list_lesson_files(tmp_path)] == ["ab12cd.ebw", "cd34ef.md"]
    assert lesson_stems(tmp_path) == {"ab12cd", "cd34ef"}
    assert (
        strip_lesson_suffix("x.EBW") == "x"
        and strip_lesson_suffix("x.md") == "x"
        and strip_lesson_suffix("x.pdf") == "x.pdf"
    )


def test_resolve_prefers_md_then_ebw(tmp_path):
    _lesson(tmp_path, "a.ebw")
    assert resolve_lesson_file(tmp_path, "a").name == "a.ebw"
    _lesson(tmp_path, "a.md")
    assert resolve_lesson_file(tmp_path, "a").name == "a.md"
    assert resolve_lesson_file(tmp_path, "a.ebw").name == "a.ebw"
    assert resolve_lesson_file(tmp_path, "fehlt") is None


def test_plan_row_link_resolves_ebw_in_einheiten_and_alteinheiten(tmp_path):
    plan_dir = tmp_path / "M 7a 26-2"
    _lesson(plan_dir / "Einheiten", "ab12cd.ebw")
    _lesson(plan_dir / "Alteinheiten", "zz99zz.ebw")

    assert get_row_link_path(_table(plan_dir, "[[ab12cd]]"), 0) == (plan_dir / "Einheiten" / "ab12cd.ebw").resolve()
    assert get_row_link_path(_table(plan_dir, '`= link("zz99zz", [[zz99zz]].Stundenthema)`'), 0).name == "zz99zz.ebw"
    assert get_row_link_path(_table(plan_dir, "[[Einheiten/ab12cd.ebw|Brüche]]"), 0).name == "ab12cd.ebw"


def test_ebw_lesson_yaml_loads_and_save_keeps_blattwerk_marker(tmp_path):
    path = _lesson(tmp_path / "Einheiten", "ab12cd.ebw")

    lesson = load_linked_lesson_yaml(path)
    assert lesson.data["Stundenthema"] == "Brüche"
    lesson.data["Stundenthema"] = "Brüche addieren"
    save_linked_lesson_yaml(lesson)

    text = path.read_text(encoding="utf-8")
    assert "document_type: kurzentwurf" in text
    assert "Stundenthema: Brüche addieren" in text
    assert text.endswith("#einstieg\nS> Hallo\n")


def test_save_without_marker_adds_none(tmp_path):
    path = _lesson(tmp_path, "cd34ef.md", LESSON.replace("document_type: kurzentwurf\n", ""))
    save_linked_lesson_yaml(load_linked_lesson_yaml(path))
    assert "document_type" not in path.read_text(encoding="utf-8")


def test_rename_and_unique_path_keep_ebw_suffix(tmp_path):
    link = _lesson(tmp_path, "ab12cd.ebw")
    _lesson(tmp_path, "Brüche.ebw")
    transfer = LessonTransferUseCase(FileSystemLessonRepository(), FileSystemLessonFileRepository())

    assert transfer.compute_rename_target(link, "Brüche").name == "Brüche 2.ebw"
    assert transfer.next_unique_stem_path(tmp_path, "Neu", ".ebw").name == "Neu.ebw"
    assert transfer.next_unique_stem_path(tmp_path, "Neu").name == "Neu.md"
    transfer.validate_lesson_markdown(link)


def test_wiki_link_target_strips_ebw():
    assert extract_wiki_link_target("[[Einheiten/ab12cd.ebw|Brüche]]") == "ab12cd"
    assert extract_wiki_link_target("[[ab12cd.md]]") == "ab12cd"
