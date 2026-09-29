"""Tests für den LZK-Kompetenzhorizont: Identitätsfälle, Speicherort, Link und Themenliste.

Arbeitet mit synthetischen Dateien in einem temporären Vault (``.obsidian``),
dem echten Markdown-Export samt Leser und einem PDF-Stub.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.yaml_registry import RawYamlBlock
from kursplaner.core.usecases.export_expected_horizon_usecase import (
    ExportExpectedHorizonResult,
    ExportExpectedHorizonUseCase,
)
from kursplaner.core.usecases.export_lzk_expected_horizon_usecase import ExportLzkExpectedHorizonUseCase
from kursplaner.infrastructure.export.expected_horizon_markdown_reader import ExpectedHorizonMarkdownReader
from kursplaner.infrastructure.export.expected_horizon_markdown_renderer import ExpectedHorizonMarkdownRenderer
from kursplaner.infrastructure.repositories.lesson_repository import FileSystemLessonRepository
from tests.day_column_factory import make_day_column

NOW = datetime(2026, 9, 29, 15, 30)


class _PdfExportStub:
    """Ersetzt den PDF-Export (reportlab-unabhängig) und protokolliert die Zielpfade."""

    def __init__(self):
        self.calls: list[Path] = []

    def execute(self, *, output_path: Path, oberthemen, **_kwargs) -> ExportExpectedHorizonResult:
        self.calls.append(output_path)
        output_path.write_text("pdf", encoding="utf-8")
        return ExportExpectedHorizonResult(output_path, "KH", 0, tuple(oberthemen))


class _Course:
    """Synthetischer Kurs im temporären Vault mit Unterrichtsstunden und einer LZK."""

    def __init__(self, tmp_path: Path, *, lzk_oberthema: object = None):
        self.vault = tmp_path / "Vault"
        (self.vault / ".obsidian").mkdir(parents=True)
        self.course_dir = self.vault / "Unterricht" / "M 11.1 26-2"
        self.lessons = self.course_dir / "Einheiten"
        self.lessons.mkdir(parents=True)
        self.table = PlanTableData(
            markdown_path=self.course_dir / "M 11.1 26-2.md",
            headers=["Datum", "Inhalt"],
            rows=[],
            start_line=0,
            end_line=0,
            source_lines=[],
            had_trailing_newline=True,
            metadata={"Kursfach": "Mathematik", "Lerngruppe": "[[11.1]]"},
        )
        self.days = []
        self._unit("01-09-26", "A", "Potenzen erkennen")
        self._unit("03-09-26", "B", "Wachstum beschreiben")
        self._unit("08-09-26", "A", "Graphen skizzieren")
        self.lzk_row = self._lzk("10-09-26", lzk_oberthema if lzk_oberthema is not None else [])
        self._unit("15-09-26", "C", "Nach der LZK")

    def _link(self, stem: str, frontmatter: str) -> Path:
        path = self.lessons / f"{stem}.md"
        path.write_text(f"---\n{frontmatter}---\n", encoding="utf-8")
        return path.resolve()

    def _unit(self, datum: str, topic: str, ziel: str) -> None:
        row = len(self.days)
        link = self._link(f"u{row}", "Stundentyp: Unterricht\nDauer: 2\nStundenthema: U\n")
        yaml = {"Stundentyp": "Unterricht", "Oberthema": f"[[11.1 {topic}]]", "Stundenziel": ziel}
        self.days.append(make_day_column(row_index=row, datum=datum, link=link, yaml=yaml, group_name="[[11.1]]"))

    def _lzk(self, datum: str, oberthema: object) -> int:
        row = len(self.days)
        lines = "Stundentyp: LZK\nDauer: 2\nStundenthema: LZK\n"
        if isinstance(oberthema, RawYamlBlock):
            lines += "Oberthema:\n" + "\n".join(oberthema.lines) + "\n"
        else:
            lines += "Oberthema:\n" + "".join(f'  - "{entry}"\n' for entry in oberthema)
        self.lzk_path = self._link("lzk", lines)
        self.days.append(self._lzk_column(row, datum))
        return row

    def _lzk_column(self, row: int, datum: str):
        yaml = FileSystemLessonRepository().load_lesson_yaml(self.lzk_path).data
        return make_day_column(row_index=row, datum=datum, link=self.lzk_path, yaml=yaml, group_name="[[11.1]]")

    def reload_lzk(self) -> None:
        """Übernimmt die gespeicherte LZK-YAML in die Tagesliste (wie ein Neuladen des Kurses)."""
        self.days[self.lzk_row] = self._lzk_column(self.lzk_row, self.days[self.lzk_row].datum)


def _usecase(pdf: _PdfExportStub | None = None) -> ExportLzkExpectedHorizonUseCase:
    return ExportLzkExpectedHorizonUseCase(
        lesson_repo=FileSystemLessonRepository(),
        export_markdown_usecase=ExportExpectedHorizonUseCase(
            renderer=ExpectedHorizonMarkdownRenderer(), existing_reader=ExpectedHorizonMarkdownReader()
        ),
        export_pdf_usecase=pdf or _PdfExportStub(),
    )


def _export(course: _Course, selection: list[str], markdown_path: Path | None = None, pdf=None):
    usecase = _usecase(pdf)
    proposal = usecase.build_proposal(table=course.table, raw_day_columns=course.days, anchor_row_index=course.lzk_row)
    target = markdown_path or proposal.default_markdown_path(selection, now=NOW)
    result = usecase.execute(
        table=course.table,
        raw_day_columns=course.days,
        proposal=proposal,
        selection=selection,
        markdown_path=target,
        export_date=date(2026, 9, 29),
        created_at=NOW,
    )
    course.reload_lzk()
    return proposal, result


def _raw_lzk(course: _Course) -> dict[str, object]:
    return FileSystemLessonRepository().load_raw_lesson_frontmatter(course.lzk_path)


def _grade_first_goal(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("**... Potenzen erkennen** |  |  |  |", "**... Potenzen erkennen** | II | 1a | 2 |"), "utf-8"
    )


def test_first_export_uses_readable_default_name_and_stores_chronological_topics(tmp_path):
    course = _Course(tmp_path)
    pdf = _PdfExportStub()

    _proposal, result = _export(course, ["B", "A", "B"], pdf=pdf)

    assert result.markdown_path.name == "KH LZK 2026-09-10 - A + B (2026-09-29 1530).md"
    assert result.markdown_path.parent == course.course_dir.resolve()
    assert pdf.calls == [result.pdf_path] and result.pdf_path.suffix == ".pdf"
    assert result.oberthemen == ("A", "B")
    raw = _raw_lzk(course)
    assert raw["Oberthema"] == ["[[11.1 A]]", "[[11.1 B]]"]
    assert raw["Kompetenzhorizont"] == f"[[{result.markdown_path.stem}]]"
    assert raw["created_at"].startswith("2026-09-29T15:30:00")


def test_only_lessons_before_the_lzk_are_included(tmp_path):
    course = _Course(tmp_path)

    _proposal, result = _export(course, ["A", "B"])

    text = result.markdown_path.read_text(encoding="utf-8")
    assert "### A" in text and "### B" in text
    assert "Nach der LZK" not in text
    assert result.title == "Kompetenzhorizont: A, B"


def test_same_topics_same_path_updates_existing_horizon_and_keeps_scores(tmp_path):
    course = _Course(tmp_path)
    _proposal, first = _export(course, ["A", "B"])
    _grade_first_goal(first.markdown_path)

    proposal, second = _export(course, ["A", "B"])

    assert proposal.default_markdown_path(["B", "A"], now=NOW) == first.markdown_path
    assert second.same_identity and second.markdown_path == first.markdown_path
    assert "| **... Potenzen erkennen** | II | 1a | 2 |" in second.markdown_path.read_text(encoding="utf-8")


def test_same_topics_new_path_moves_canonical_location_and_keeps_old_file(tmp_path):
    course = _Course(tmp_path)
    _proposal, first = _export(course, ["A", "B"])
    _grade_first_goal(first.markdown_path)
    new_path = course.vault / "Archiv" / "KH neu.md"
    new_path.parent.mkdir()

    _proposal, second = _export(course, ["A", "B"], markdown_path=new_path)

    assert second.same_identity
    assert first.markdown_path.is_file()
    assert "| **... Potenzen erkennen** | II | 1a | 2 |" in new_path.read_text(encoding="utf-8")
    assert _raw_lzk(course)["Kompetenzhorizont"] == "[[Archiv/KH neu]]"


def test_other_topic_selection_is_a_new_horizon(tmp_path):
    course = _Course(tmp_path)
    _proposal, first = _export(course, ["A", "B"])
    _grade_first_goal(first.markdown_path)
    before = first.markdown_path.read_text(encoding="utf-8")

    proposal, second = _export(course, ["A"])

    assert not second.same_identity
    assert proposal.default_markdown_path(["A"], now=NOW) != first.markdown_path
    assert second.markdown_path != first.markdown_path
    assert first.markdown_path.read_text(encoding="utf-8") == before
    assert "| II | 1a | 2 |" not in second.markdown_path.read_text(encoding="utf-8")
    assert _raw_lzk(course)["Oberthema"] == ["[[11.1 A]]"]


def test_unavailable_stored_topic_is_not_preselected_and_removed(tmp_path):
    course = _Course(tmp_path, lzk_oberthema=["[[11.1 A]]", "[[11.1 Umbenannt]]"])

    proposal, result = _export(course, ["A"])

    assert proposal.options.preselected == ("A",)
    assert proposal.options.unavailable_stored == ("Umbenannt",)
    assert result.removed_unavailable == ("Umbenannt",)
    assert _raw_lzk(course)["Oberthema"] == ["[[11.1 A]]"]


def test_file_outside_vault_gets_no_link(tmp_path):
    course = _Course(tmp_path)
    outside = tmp_path / "Extern" / "KH.md"
    outside.parent.mkdir()

    _proposal, result = _export(course, ["A"], markdown_path=outside)

    assert not result.link_written
    assert FileSystemLessonRepository().load_lesson_yaml(course.lzk_path).data["Kompetenzhorizont"] == ""


def test_lzk_with_invalid_topic_is_rejected_and_left_unchanged(tmp_path):
    course = _Course(tmp_path, lzk_oberthema=RawYamlBlock(("  foo: bar",)))
    before = course.lzk_path.read_text(encoding="utf-8")

    with pytest.raises(RuntimeError, match="ungültiges Format"):
        _usecase().build_proposal(table=course.table, raw_day_columns=course.days, anchor_row_index=course.lzk_row)

    assert course.lzk_path.read_text(encoding="utf-8") == before


def test_empty_selection_is_rejected(tmp_path):
    course = _Course(tmp_path)

    with pytest.raises(RuntimeError, match="kein Oberthema"):
        _export(course, [])
