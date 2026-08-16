from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.row_identity import ResolutionStatus
from kursplaner.core.domain.school_wide_cancellation import (
    CourseApplicationLedger,
    RowLocation,
    UnitMove,
    UnitReference,
)
from kursplaner.core.usecases.school_wide_cancellation_revert_usecase import SchoolWideCancellationRevertUseCase

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
    def __init__(self, table: PlanTableData) -> None:
        self._table = table
        self.saved: PlanTableData | None = None

    def load_plan_table(self, markdown_path: Path) -> PlanTableData:
        return self._table

    def save_plan_table(self, table: PlanTableData) -> None:
        self.saved = table


def _make_uc(rows: list[list[str]]) -> tuple[SchoolWideCancellationRevertUseCase, _FakePlanRepo]:
    repo = _FakePlanRepo(_table(rows))
    return SchoolWideCancellationRevertUseCase(plan_repo=repo), repo


def test_revert_restores_content_from_gap_target():
    rows = [
        ["06-01-26", "", "X Wandertag"],
        ["07-01-26", "[[abc]]", ""],
    ]
    ledger = CourseApplicationLedger(
        moves=(
            UnitMove(
                source=RowLocation(date="06-01-26", position_in_date=0),
                reference=UnitReference(kind="link", value="abc"),
                target=RowLocation(date="07-01-26", position_in_date=0),
            ),
        )
    )
    uc, repo = _make_uc(rows)
    outcome = uc.execute(markdown_path=_PATH, ledger=ledger)

    assert outcome.reverted_move_count == 1
    assert outcome.is_complete
    assert repo.saved.rows[0][1] == "[[abc]]"
    assert repo.saved.rows[0][2] == ""
    assert repo.saved.rows[1][1] == ""


def test_revert_moves_live_content_not_a_snapshot():
    """Inhalt der verschobenen Einheit wurde nach dem Apply manuell bearbeitet - der AKTUELLE Wert wandert zurueck."""
    rows = [
        ["06-01-26", "", "X Wandertag"],
        ["07-01-26", "[[edited-since-apply]]", ""],
    ]
    ledger = CourseApplicationLedger(
        moves=(
            UnitMove(
                source=RowLocation(date="06-01-26", position_in_date=0),
                reference=UnitReference(kind="link", value="abc"),  # stale: original link before edit
                target=RowLocation(date="07-01-26", position_in_date=0),
            ),
        )
    )
    uc, repo = _make_uc(rows)
    outcome = uc.execute(markdown_path=_PATH, ledger=ledger)

    # Referenz stimmt nicht mehr ueberein -> WARNING, kein automatisches Handeln.
    assert outcome.reverted_move_count == 0
    assert outcome.issues[0].resolution.status is ResolutionStatus.WARNING


def test_revert_forced_warning_moves_current_content():
    rows = [
        ["06-01-26", "", "X Wandertag"],
        ["07-01-26", "[[edited-since-apply]]", ""],
    ]
    ledger = CourseApplicationLedger(
        moves=(
            UnitMove(
                source=RowLocation(date="06-01-26", position_in_date=0),
                reference=UnitReference(kind="link", value="abc"),
                target=RowLocation(date="07-01-26", position_in_date=0),
            ),
        )
    )
    uc, repo = _make_uc(rows)
    outcome = uc.execute(markdown_path=_PATH, ledger=ledger, force_warnings=True)

    assert outcome.reverted_move_count == 1
    assert repo.saved.rows[0][1] == "[[edited-since-apply]]"


def test_revert_without_target_only_clears_marker():
    rows = [["06-01-26", "", "X Wandertag"]]
    ledger = CourseApplicationLedger(
        moves=(UnitMove(source=RowLocation(date="06-01-26", position_in_date=0), reference=None, target=None),)
    )
    uc, repo = _make_uc(rows)
    outcome = uc.execute(markdown_path=_PATH, ledger=ledger)

    assert outcome.reverted_move_count == 1
    assert repo.saved.rows[0][2] == ""


def test_revert_error_when_source_marker_missing():
    """Zeile wurde ueber das bestehende Strg+B-Werkzeug bereits manuell wiederhergestellt."""
    rows = [["06-01-26", "[[abc]]", ""]]
    ledger = CourseApplicationLedger(
        moves=(UnitMove(source=RowLocation(date="06-01-26", position_in_date=0), reference=None, target=None),)
    )
    uc, repo = _make_uc(rows)
    outcome = uc.execute(markdown_path=_PATH, ledger=ledger)

    assert outcome.reverted_move_count == 0
    assert outcome.issues[0].resolution.status is ResolutionStatus.ERROR
    assert repo.saved is None


def test_revert_appended_dateless_row_is_stripped_after_restore():
    rows = [
        ["06-01-26", "", "X Wandertag"],
        ["", "[[abc]]", ""],
    ]
    ledger = CourseApplicationLedger(
        moves=(
            UnitMove(
                source=RowLocation(date="06-01-26", position_in_date=0),
                reference=UnitReference(kind="link", value="abc"),
                target=RowLocation(date=None, position_in_date=0),
            ),
        )
    )
    uc, repo = _make_uc(rows)
    outcome = uc.execute(markdown_path=_PATH, ledger=ledger)

    assert outcome.reverted_move_count == 1
    assert len(repo.saved.rows) == 1
    assert repo.saved.rows[0][1] == "[[abc]]"


def test_revert_does_not_touch_unrelated_dateless_rows_from_other_entries():
    """Eine spaetere, unabhaengige datumslose Zeile eines anderen Entries darf nicht geloescht werden."""
    rows = [
        ["06-01-26", "", "X Wandertag"],
        ["", "[[abc]]", ""],
        ["", "[[unrelated]]", ""],
    ]
    ledger = CourseApplicationLedger(
        moves=(
            UnitMove(
                source=RowLocation(date="06-01-26", position_in_date=0),
                reference=UnitReference(kind="link", value="abc"),
                target=RowLocation(date=None, position_in_date=0),
            ),
        )
    )
    uc, repo = _make_uc(rows)
    outcome = uc.execute(markdown_path=_PATH, ledger=ledger)

    assert outcome.reverted_move_count == 1
    remaining = [row for row in repo.saved.rows if row[1] == "[[unrelated]]"]
    assert len(remaining) == 1
