from pathlib import Path

from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData
from kursplaner.core.usecases.lesson_context_query_usecase import LessonContextQueryUseCase


class _LessonRepoStub:
    def __init__(self, lessons_by_row: dict[int, LessonYamlData]):
        self._lessons_by_row = dict(lessons_by_row)

    def load_lessons_for_all_rows(self, _table: PlanTableData) -> dict[int, LessonYamlData]:
        return dict(self._lessons_by_row)


def _table() -> PlanTableData:
    return PlanTableData(
        markdown_path=Path("fach/plan.md"),
        headers=["datum", "stunden", "inhalt"],
        rows=[
            ["01-05-26", "2", "[[LZK scheinbar]]"],
            ["02-05-26", "2", "[[normal]]"],
        ],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={},
    )


def test_next_lzk_number_ignores_content_keyword_without_lzk_type():
    table = _table()
    lessons = {
        0: LessonYamlData(
            lesson_path=Path("a.md"),
            data={"Stundentyp": "Unterricht", "Stundenthema": "LZK Vorbereitung"},
        ),
        1: LessonYamlData(
            lesson_path=Path("b.md"),
            data={"Stundentyp": "Unterricht", "Stundenthema": "Regulaere Stunde"},
        ),
    }

    result = LessonContextQueryUseCase(lesson_repo=_LessonRepoStub(lessons)).next_lzk_number(table)

    assert result == 1


def test_next_lzk_number_counts_yaml_lzk_types_only():
    table = _table()
    lessons = {
        0: LessonYamlData(
            lesson_path=Path("a.md"),
            data={"Stundentyp": "LZK", "Stundenthema": "Leistungskontrolle"},
        ),
    }

    result = LessonContextQueryUseCase(lesson_repo=_LessonRepoStub(lessons)).next_lzk_number(table)

    assert result == 2
