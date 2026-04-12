from __future__ import annotations

from datetime import date

from kursplaner.core.usecases.create_plan_usecase import CreatePlanUseCase
from kursplaner.infrastructure.repositories.plan_repository import FileSystemPlanRepository
from kursplaner.infrastructure.repositories.plan_table_file_repository import load_last_plan_table


class _CalendarRepoStub:
    def load_calendar_data(self, calendar_dir, years):
        events = {}
        blocks = [
            ("Winterferien", date(2026, 1, 5), date(2026, 1, 9)),
            ("Sommerferien", date(2026, 7, 10), date(2026, 8, 20)),
            ("Winterferien", date(2027, 1, 4), date(2027, 1, 8)),
        ]
        return events, blocks, []


def test_write_plan_rows_creates_initial_table_when_missing(tmp_path):
    markdown = tmp_path / "M GK blau-1 26-1.md"
    markdown.write_text(
        '---\nLerngruppe: "[[GK blau-1]]"\nKursfach: "Mathematik"\nStufe: 11\n---\n\n',
        encoding="utf-8",
    )

    repo = FileSystemPlanRepository()
    repo.write_plan_rows(markdown, [(date(2026, 3, 12), 2, "")])

    text = markdown.read_text(encoding="utf-8")
    assert "| Datum | Stunden | Inhalt |" in text
    assert "| 12-03-26 | 2 |  |" in text

    table = load_last_plan_table(markdown)
    assert len(table.rows) == 1


def test_create_plan_usecase_replace_mode_writes_table_when_missing(tmp_path):
    markdown = tmp_path / "M GK blau-1 26-1.md"
    markdown.write_text(
        '---\nLerngruppe: "[[GK blau-1]]"\nKursfach: "Mathematik"\nStufe: 11\n---\n\n',
        encoding="utf-8",
    )

    usecase = CreatePlanUseCase(plan_repo=FileSystemPlanRepository(), calendar_repo=_CalendarRepoStub())

    result = usecase.execute(
        target_markdown=markdown,
        term="26-1",
        day_hours={0: 2},
        calendar_dir=tmp_path,
        write_mode="replace",
    )

    assert result.rows_count > 0
    table = load_last_plan_table(markdown)
    assert len(table.rows) == result.rows_count
