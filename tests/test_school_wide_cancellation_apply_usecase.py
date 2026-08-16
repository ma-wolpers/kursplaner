from __future__ import annotations

from datetime import date
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.school_wide_cancellation import RowLocation, UnitReference
from kursplaner.core.usecases.school_wide_cancellation_apply_usecase import SchoolWideCancellationApplyUseCase

_HEADERS = ["Datum", "Inhalt", "Thema/Ausfall"]
_PATH = Path("test.md")


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
    """Captures save_plan_table calls without touching the file system."""

    def __init__(self, table: PlanTableData) -> None:
        self._table = table
        self.saved: PlanTableData | None = None

    def load_plan_table(self, markdown_path: Path) -> PlanTableData:
        return self._table

    def save_plan_table(self, table: PlanTableData) -> None:
        self.saved = table


def _make_uc(rows: list[list[str]]) -> tuple[SchoolWideCancellationApplyUseCase, _FakePlanRepo]:
    repo = _FakePlanRepo(_table(rows))
    return SchoolWideCancellationApplyUseCase(plan_repo=repo), repo


def _execute(uc: SchoolWideCancellationApplyUseCase, *, date_from: date, date_to: date, reason: str = "Wandertag"):
    return uc.execute(markdown_path=_PATH, date_from=date_from, date_to=date_to, reason=reason)


def test_no_stattfindend_rows_returns_empty_ledger_and_no_save():
    uc, repo = _make_uc([["06-01-26", "", "X Ausfall"]])
    ledger = _execute(uc, date_from=date(2026, 1, 6), date_to=date(2026, 1, 6))
    assert ledger.moves == ()
    assert repo.saved is None


def test_cancels_content_less_row_without_move():
    uc, repo = _make_uc([["06-01-26", "", ""]])
    ledger = _execute(uc, date_from=date(2026, 1, 6), date_to=date(2026, 1, 6))

    assert len(ledger.moves) == 1
    move = ledger.moves[0]
    assert move.reference is None
    assert move.target is None
    assert repo.saved.rows[0][2] == "X Wandertag"


def test_displaces_content_into_existing_gap():
    rows = [
        ["06-01-26", "[[abc]]", ""],
        ["07-01-26", "", ""],
    ]
    uc, repo = _make_uc(rows)
    ledger = _execute(uc, date_from=date(2026, 1, 6), date_to=date(2026, 1, 6))

    saved = repo.saved.rows
    assert saved[0][1] == ""
    assert saved[0][2] == "X Wandertag"
    assert saved[1][1] == "[[abc]]"

    assert len(ledger.moves) == 1
    move = ledger.moves[0]
    assert move.source == RowLocation(date="06-01-26", position_in_date=0)
    assert move.target == RowLocation(date="07-01-26", position_in_date=0)
    assert move.reference == UnitReference(kind="link", value="abc")


def test_appends_dateless_row_when_no_gap_available():
    uc, repo = _make_uc([["06-01-26", "[[abc]]", ""]])
    ledger = _execute(uc, date_from=date(2026, 1, 6), date_to=date(2026, 1, 6))

    saved = repo.saved.rows
    assert len(saved) == 2
    assert saved[1][0] == ""
    assert saved[1][1] == "[[abc]]"
    assert ledger.moves[0].target == RowLocation(date=None, position_in_date=0)


def test_strips_preexisting_empty_dateless_row_after_apply():
    rows = [
        ["06-01-26", "[[abc]]", ""],
        ["", "", ""],
    ]
    uc, repo = _make_uc(rows)
    _execute(uc, date_from=date(2026, 1, 6), date_to=date(2026, 1, 6))

    dateless_rows = [r for r in repo.saved.rows if not r[0].strip()]
    assert len(dateless_rows) == 1
    assert dateless_rows[0][1] == "[[abc]]"


def test_multiple_cancelled_rows_placed_in_chronological_order():
    rows = [
        ["06-01-26", "[[first]]", ""],
        ["07-01-26", "[[second]]", ""],
    ]
    uc, repo = _make_uc(rows)
    _execute(uc, date_from=date(2026, 1, 6), date_to=date(2026, 1, 7))

    appended = [r for r in repo.saved.rows if not r[0].strip()]
    assert [row[1] for row in appended] == ["[[first]]", "[[second]]"]


def test_rows_outside_range_untouched():
    rows = [
        ["05-01-26", "[[before]]", ""],
        ["06-01-26", "[[target]]", ""],
        ["07-01-26", "[[after]]", ""],
    ]
    uc, repo = _make_uc(rows)
    _execute(uc, date_from=date(2026, 1, 6), date_to=date(2026, 1, 6))

    saved = repo.saved.rows
    assert saved[0][1] == "[[before]]"
    assert saved[2][1] == "[[after]]"
