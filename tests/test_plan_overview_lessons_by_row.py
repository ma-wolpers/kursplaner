"""`summarize_plan(lessons_by_row=…)`: Daten aus den Tagesspalten liefern dasselbe wie das Lesen von der Platte."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.load_plan_detail_usecase import LoadPlanDetailUseCase
from kursplaner.core.usecases.plan_overview_query_usecase import PlanOverviewQueryUseCase
from kursplaner.infrastructure.repositories.markdown_repositories import FileSystemLessonRepository

NOW = datetime(2026, 11, 10, 7, 0)


def _lesson(path: Path, frontmatter: str) -> None:
    path.write_text(f"---\n{frontmatter}---\n\n# Inhalt\n", encoding="utf-8")


def _table(tmp_path: Path) -> PlanTableData:
    course = tmp_path / "Unterricht" / "Mat 11 26-2"
    lessons = course / "Einheiten"
    lessons.mkdir(parents=True)
    _lesson(
        lessons / "aaaaaa.md",
        'Stundentyp: Unterricht\nDauer: 2\nStundenthema: "Brüche"\nOberthema:\n  - "[[Zahlen]]"\n',
    )
    _lesson(lessons / "bbbbbb.md", 'Stundentyp: LZK\nDauer: 2\nStundenthema: "LZK 1"\n')
    _lesson(
        lessons / "cccccc.md",
        'Stundentyp: Unterricht\nDauer: 2\nStundenthema: "Besuch"\nUnterrichtsbesuch: "[[UB 26-11-30 Fach]]"\n',
    )
    _lesson(lessons / "dddddd.md", 'Stundentyp: Unterricht\nDauer: 2\nStundenthema: "Danach"\n')
    dates = [(NOW + timedelta(days=7 * idx)).strftime("%d-%m-%y") for idx in range(6)]
    rows = [
        [dates[0], "", "X Konferenz"],
        [dates[1], "[[aaaaaa]]", ""],
        [dates[2], "[[bbbbbb]]", ""],
        [dates[3], "", ""],
        [dates[4], "[[cccccc]]", ""],
        [dates[5], "[[dddddd]]", ""],
    ]
    return PlanTableData(
        markdown_path=course / "Mat 11 26-2.md",
        headers=["Datum", "Inhalt", "Thema/Ausfall"],
        rows=rows,
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={"Lerngruppe": "[[GK blau-1]]", "Rhythmus": ["Di 08:00 2"]},
    )


def test_day_column_data_gives_identical_summary_to_disk_read(tmp_path):
    table = _table(tmp_path)
    lesson_repo = FileSystemLessonRepository()
    usecase = PlanOverviewQueryUseCase(lesson_repo=lesson_repo, now_provider=lambda: NOW)
    day_columns = LoadPlanDetailUseCase(plan_repo=None, lesson_repo=lesson_repo).build_day_columns(table)

    from_disk = usecase.summarize_plan(table)
    from_columns = usecase.summarize_plan(table, lessons_by_row={day.row_index: day.yaml for day in day_columns})

    assert from_columns == from_disk
    assert from_disk[0] == "Brüche"  # nächstes Thema
    assert from_disk[2] != "—"  # nächste LZK erkannt


def test_lessons_by_row_avoids_reading_lesson_files(tmp_path):
    table = _table(tmp_path)

    class _NoDiskRepo:
        def load_lessons_for_rows(self, *_args, **_kwargs):
            raise AssertionError("darf mit lessons_by_row nicht von der Platte lesen")

    usecase = PlanOverviewQueryUseCase(lesson_repo=_NoDiskRepo(), now_provider=lambda: NOW)

    theme, *_rest = usecase.summarize_plan(table, lessons_by_row={1: {"Stundenthema": "Aus dem Speicher"}})

    assert theme == "Aus dem Speicher"
