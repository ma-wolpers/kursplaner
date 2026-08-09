from __future__ import annotations

from datetime import date
from pathlib import Path

from kursplaner.core.domain.course_lifecycle import (
    course_archive_root,
    is_archived_course_path,
    is_former_course,
    last_plan_date,
)
from kursplaner.core.domain.plan_table import PlanTableData


def _table(rows: list[list[str]]) -> PlanTableData:
    return PlanTableData(
        markdown_path=Path("Kurs/Kurs.md"),
        headers=["Datum", "Inhalt", "Thema/Ausfall"],
        rows=rows,
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={},
    )


def test_last_plan_date_picks_maximum():
    table = _table([["05-01-26", "", ""], ["12-03-26", "", ""], ["20-02-26", "", ""]])
    assert last_plan_date(table) == date(2026, 3, 12)


def test_last_plan_date_none_for_empty_table():
    assert last_plan_date(_table([])) is None


def test_last_plan_date_ignores_invalid_rows():
    table = _table([["kein-datum", "", ""], ["05-01-26", "", ""]])
    assert last_plan_date(table) == date(2026, 1, 5)


def test_is_former_course_true_when_last_date_in_past():
    table = _table([["05-01-26", "", ""]])
    assert is_former_course(table, date(2026, 6, 1)) is True


def test_is_former_course_false_on_boundary_day():
    """Letztes Datum == heute gilt noch NICHT als ehemalig."""
    table = _table([["05-01-26", "", ""]])
    assert is_former_course(table, date(2026, 1, 5)) is False


def test_is_former_course_false_when_last_date_in_future():
    table = _table([["05-01-26", "", ""]])
    assert is_former_course(table, date(2025, 12, 1)) is False


def test_is_former_course_false_when_no_dated_rows():
    assert is_former_course(_table([]), date(2026, 1, 1)) is False


def test_course_archive_root_and_path_detection():
    unterricht_dir = Path("A:/Vault/10 Unterricht")
    archive_root = course_archive_root(unterricht_dir)
    assert archive_root == unterricht_dir / "-ALT"

    archived_plan = archive_root / "Mat 11.1 26-2" / "Mat 11.1 26-2.md"
    active_plan = unterricht_dir / "Mat 11.1 26-2" / "Mat 11.1 26-2.md"
    assert is_archived_course_path(archived_plan, unterricht_dir) is True
    assert is_archived_course_path(active_plan, unterricht_dir) is False
