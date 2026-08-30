from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.list_lessons_usecase import ListLessonsUseCase


class _FakePlanRepo:
    def __init__(self, tables: list[PlanTableData]):
        self._tables = tables

    def list_plan_markdown_files(self, base_dir: Path) -> list[Path]:
        del base_dir
        return [table.markdown_path for table in self._tables]

    def load_plan_table(self, markdown_path: Path) -> PlanTableData:
        return next(table for table in self._tables if table.markdown_path == markdown_path)


class _FakePlanOverviewQuery:
    def summarize_plan(self, table: PlanTableData):
        del table
        return ("—", 0, "—", "", "—", None, False, False)


def _table(markdown_path: Path, *, stufe: str | None) -> PlanTableData:
    metadata: dict[str, str] = {}
    if stufe is not None:
        metadata["Stufe"] = stufe
    return PlanTableData(
        markdown_path=markdown_path,
        headers=["Datum", "Inhalt"],
        rows=[],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata=metadata,
    )


def test_list_lessons_populates_grade_level_from_course_stufe(tmp_path):
    course_dir = tmp_path / "Mathe Kurs"
    course_dir.mkdir()
    markdown_path = course_dir / "Mathe Kurs.md"
    table = _table(markdown_path, stufe="7")

    usecase = ListLessonsUseCase(plan_repo=_FakePlanRepo([table]), plan_overview_query=_FakePlanOverviewQuery())
    result = usecase.execute(tmp_path)

    assert len(result.lessons) == 1
    assert result.lessons[0].grade_level == 7


def test_list_lessons_leaves_grade_level_none_for_missing_or_invalid_stufe(tmp_path):
    course_dir = tmp_path / "Ohne Stufe"
    course_dir.mkdir()
    markdown_path = course_dir / "Ohne Stufe.md"
    table = _table(markdown_path, stufe=None)

    usecase = ListLessonsUseCase(plan_repo=_FakePlanRepo([table]), plan_overview_query=_FakePlanOverviewQuery())
    result = usecase.execute(tmp_path)

    assert len(result.lessons) == 1
    assert result.lessons[0].grade_level is None
