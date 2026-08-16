from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.school_wide_cancellation import (
    CourseApplicationLedger,
    RowLocation,
    SchoolWideCancellationEntry,
    UnitMove,
    course_key_for_path,
)
from kursplaner.core.usecases.apply_school_wide_cancellations_to_new_rows_usecase import (
    ApplySchoolWideCancellationsToNewRowsUseCase,
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
    def __init__(self, table: PlanTableData, *, raise_on_save: bool = False) -> None:
        self._table = table
        self.saved: PlanTableData | None = None
        self._raise_on_save = raise_on_save

    def load_plan_table(self, markdown_path: Path) -> PlanTableData:
        return self._table

    def save_plan_table(self, table: PlanTableData) -> None:
        if self._raise_on_save:
            raise OSError("disk full")
        self.saved = table


def _entry(entry_id: str, *, reason: str, grades: frozenset[int], date_from: date, date_to: date, ledgers=None):
    return SchoolWideCancellationEntry(
        entry_id=entry_id,
        reason=reason,
        date_from=date_from,
        date_to=date_to,
        grade_levels=grades,
        created_at="",
        course_ledgers=dict(ledgers or {}),
    )


class _FakeStore:
    def __init__(self, entries: list[SchoolWideCancellationEntry]) -> None:
        self.entries = entries
        self.saved_entries: list[SchoolWideCancellationEntry] | None = None

    def load(self) -> list[SchoolWideCancellationEntry]:
        return self.entries

    def save(self, entries: list[SchoolWideCancellationEntry]) -> None:
        self.saved_entries = entries


def _make_uc(rows: list[list[str]], entries: list[SchoolWideCancellationEntry], *, raise_on_save: bool = False):
    repo = _FakePlanRepo(_table(rows), raise_on_save=raise_on_save)
    store = _FakeStore(entries)
    uc = ApplySchoolWideCancellationsToNewRowsUseCase(plan_repo=repo, store_load=store.load, store_save=store.save)
    return uc, repo, store


def test_rows_without_claim_are_untouched():
    entries = [_entry("a", reason="Wandertag", grades=frozenset({11}), date_from=date(2026, 1, 6), date_to=date(2026, 1, 6))]
    uc, repo, store = _make_uc([["06-01-26", "", ""]], entries)

    uc.execute(markdown_path=_PATH, grade_level=7, date_from=date(2026, 1, 1), date_to=date(2026, 1, 10))

    assert repo.saved is None
    assert store.saved_entries is None


def test_claimed_row_is_marked_and_creates_target_none_move():
    entries = [_entry("a", reason="Wandertag", grades=frozenset({7}), date_from=date(2026, 1, 6), date_to=date(2026, 1, 6))]
    uc, repo, store = _make_uc([["06-01-26", "", ""]], entries)

    uc.execute(markdown_path=_PATH, grade_level=7, date_from=date(2026, 1, 1), date_to=date(2026, 1, 10))

    assert repo.saved.rows[0][2] == "X Wandertag"
    ledger = store.saved_entries[0].course_ledgers[course_key_for_path(_PATH)]
    assert len(ledger.moves) == 1
    move = ledger.moves[0]
    assert move.reference is None
    assert move.target is None
    assert move.source == RowLocation(date="06-01-26", position_in_date=0)


def test_already_ferien_marked_row_is_not_overwritten():
    entries = [_entry("a", reason="Wandertag", grades=frozenset({7}), date_from=date(2026, 1, 6), date_to=date(2026, 1, 6))]
    uc, repo, store = _make_uc([["06-01-26", "", "X Winterferien X"]], entries)

    uc.execute(markdown_path=_PATH, grade_level=7, date_from=date(2026, 1, 1), date_to=date(2026, 1, 10))

    assert repo.saved is None
    assert store.saved_entries is None


def test_row_with_existing_content_is_not_overwritten():
    entries = [_entry("a", reason="Wandertag", grades=frozenset({7}), date_from=date(2026, 1, 6), date_to=date(2026, 1, 6))]
    uc, repo, store = _make_uc([["06-01-26", "[[abc]]", ""]], entries)

    uc.execute(markdown_path=_PATH, grade_level=7, date_from=date(2026, 1, 1), date_to=date(2026, 1, 10))

    assert repo.saved is None
    assert store.saved_entries is None


def test_extends_existing_ledger_instead_of_overwriting():
    existing_ledger = CourseApplicationLedger(
        moves=(UnitMove(source=RowLocation(date="01-01-26", position_in_date=0), reference=None, target=None),)
    )
    entries = [
        _entry(
            "a",
            reason="Wandertag",
            grades=frozenset({7}),
            date_from=date(2026, 1, 6),
            date_to=date(2026, 1, 6),
            ledgers={course_key_for_path(_PATH): existing_ledger},
        )
    ]
    uc, repo, store = _make_uc([["06-01-26", "", ""]], entries)

    uc.execute(markdown_path=_PATH, grade_level=7, date_from=date(2026, 1, 1), date_to=date(2026, 1, 10))

    ledger = store.saved_entries[0].course_ledgers[course_key_for_path(_PATH)]
    assert len(ledger.moves) == 2
    assert ledger.moves[0].source.date == "01-01-26"
    assert ledger.moves[1].source.date == "06-01-26"


def test_store_is_saved_before_plan_table_so_a_later_failure_is_diagnosable():
    """Store zuerst, Plantabelle danach - schlaegt Letzteres fehl, referenziert der Store bereits den Move."""
    entries = [_entry("a", reason="Wandertag", grades=frozenset({7}), date_from=date(2026, 1, 6), date_to=date(2026, 1, 6))]
    uc, repo, store = _make_uc([["06-01-26", "", ""]], entries, raise_on_save=True)

    with pytest.raises(OSError):
        uc.execute(markdown_path=_PATH, grade_level=7, date_from=date(2026, 1, 1), date_to=date(2026, 1, 10))

    assert store.saved_entries is not None
    ledger = store.saved_entries[0].course_ledgers[course_key_for_path(_PATH)]
    assert len(ledger.moves) == 1
    assert repo.saved is None
