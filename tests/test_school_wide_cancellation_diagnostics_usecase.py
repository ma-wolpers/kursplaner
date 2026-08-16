from __future__ import annotations

from datetime import date
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.school_wide_cancellation import (
    CourseApplicationLedger,
    RowLocation,
    SchoolWideCancellationEntry,
    UnitMove,
    UnitReference,
    course_key_for_path,
)
from kursplaner.core.usecases.school_wide_cancellation_diagnostics_usecase import (
    SchoolWideCancellationDiagnosticsUseCase,
)

_HEADERS = ["Datum", "Inhalt", "Thema/Ausfall"]
_PATH = Path("courses") / "7a" / "7a.md"


def _table(rows: list[list[str]]) -> PlanTableData:
    return PlanTableData(
        markdown_path=_PATH,
        headers=_HEADERS,
        rows=rows,
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={},
    )


class _FakePlanRepo:
    def __init__(self, table: PlanTableData | None) -> None:
        self._table = table

    def load_plan_table(self, markdown_path: Path) -> PlanTableData:
        if self._table is None:
            raise FileNotFoundError(markdown_path)
        return self._table


def _entry(ledger: CourseApplicationLedger) -> SchoolWideCancellationEntry:
    return SchoolWideCancellationEntry(
        entry_id="e1",
        reason="Wandertag",
        date_from=date(2026, 1, 6),
        date_to=date(2026, 1, 6),
        grade_levels=frozenset({7}),
        created_at="",
        course_ledgers={course_key_for_path(_PATH): ledger},
    )


def test_no_issues_when_ledger_matches_table():
    rows = [["06-01-26", "", "X Wandertag"]]
    ledger = CourseApplicationLedger(
        moves=(UnitMove(source=RowLocation(date="06-01-26", position_in_date=0), reference=None, target=None),)
    )
    uc = SchoolWideCancellationDiagnosticsUseCase(plan_repo=_FakePlanRepo(_table(rows)))
    assert uc.diagnose([_entry(ledger)]) == []


def test_reports_issue_when_marker_missing():
    rows = [["06-01-26", "[[abc]]", ""]]  # manuell wiederhergestellt
    ledger = CourseApplicationLedger(
        moves=(UnitMove(source=RowLocation(date="06-01-26", position_in_date=0), reference=None, target=None),)
    )
    uc = SchoolWideCancellationDiagnosticsUseCase(plan_repo=_FakePlanRepo(_table(rows)))
    issues = uc.diagnose([_entry(ledger)])
    assert len(issues) == 1
    assert issues[0].entry_id == "e1"


def test_reports_issue_when_course_file_missing():
    ledger = CourseApplicationLedger(
        moves=(UnitMove(source=RowLocation(date="06-01-26", position_in_date=0), reference=None, target=None),)
    )
    uc = SchoolWideCancellationDiagnosticsUseCase(plan_repo=_FakePlanRepo(None))
    issues = uc.diagnose([_entry(ledger)])
    assert len(issues) == 1
    assert "nicht ladbar" in issues[0].description


def test_reference_changed_on_dated_gap_target_is_reported_as_warning():
    """Position (dated gap) matcht noch, aber die Referenz an dieser Position hat sich geaendert."""
    rows = [
        ["06-01-26", "", "X Wandertag"],
        ["10-01-26", "[[different]]", ""],
    ]
    ledger = CourseApplicationLedger(
        moves=(
            UnitMove(
                source=RowLocation(date="06-01-26", position_in_date=0),
                reference=UnitReference(kind="link", value="abc"),
                target=RowLocation(date="10-01-26", position_in_date=0),
            ),
        )
    )
    uc = SchoolWideCancellationDiagnosticsUseCase(plan_repo=_FakePlanRepo(_table(rows)))
    issues = uc.diagnose([_entry(ledger)])
    assert len(issues) == 1
    assert "warning" in issues[0].description
