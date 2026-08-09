from __future__ import annotations

from datetime import date
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.apply_timetable_change_usecase import ApplyTimetableChangeUseCase
from kursplaner.core.usecases.timetable_change_usecase import DraftSlot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_HEADERS = ["Datum", "Inhalt", "Thema/Ausfall"]


def _table(rows: list[list[str]]) -> PlanTableData:
    return PlanTableData(
        markdown_path=Path("test.md"),
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

    def __init__(self) -> None:
        self.saved: PlanTableData | None = None

    def save_plan_table(self, table: PlanTableData) -> None:
        self.saved = table


def _slot(
    d: date,
    *,
    stunden: int = 2,
    is_ferien: bool = False,
    is_user_ausfall: bool = False,
    ausfall_reason: str = "",
    content: str = "",
    was_recovered_week: bool = False,
    oberthema_cell: str = "",
) -> DraftSlot:
    return DraftSlot(
        datum=d,
        stunden=stunden,
        is_ferien=is_ferien,
        is_user_ausfall=is_user_ausfall,
        ausfall_reason=ausfall_reason,
        content=content,
        was_recovered_week=was_recovered_week,
        oberthema_cell=oberthema_cell,
    )


def _make_uc() -> tuple[ApplyTimetableChangeUseCase, _FakePlanRepo]:
    repo = _FakePlanRepo()
    return ApplyTimetableChangeUseCase(plan_repo=repo), repo


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_rows_outside_range_untouched():
    """Zeilen außerhalb des Datumsbereichs bleiben unverändert."""
    rows = [
        ["05-01-26", "[[before]]", ""],
        ["06-01-26", "[[target]]", ""],
        ["07-01-26", "[[after]]", ""],
    ]
    uc, repo = _make_uc()
    draft = [_slot(date(2026, 1, 6), content="[[new]]")]
    uc.execute(_table(rows), date_from=date(2026, 1, 6), date_to=date(2026, 1, 6), draft_slots=draft)

    saved_rows = repo.saved.rows
    assert len(saved_rows) == 3
    assert saved_rows[0][1] == "[[before]]"
    assert saved_rows[1][1] == "[[new]]"
    assert saved_rows[2][1] == "[[after]]"


def test_ferien_slot_written_with_ferien_marker():
    """Ferien-Slot erhält die Ausfallnotiz in der Thema/Ausfall-Spalte."""
    rows = [["06-01-26", "", ""]]
    uc, repo = _make_uc()
    draft = [_slot(date(2026, 1, 6), stunden=0, is_ferien=True, ausfall_reason="X Ferien X")]
    uc.execute(_table(rows), date_from=date(2026, 1, 6), date_to=date(2026, 1, 6), draft_slots=draft)

    row = repo.saved.rows[0]
    assert "Ferien" in row[2]


def test_user_ausfall_slot_written_with_marker():
    """User-Ausfall-Slot erhält Ausfall-Marker in Thema/Ausfall-Spalte."""
    rows = [["06-01-26", "[[abc123]]", ""]]
    uc, repo = _make_uc()
    draft = [_slot(date(2026, 1, 6), is_user_ausfall=True, ausfall_reason="Klausur", content="[[abc123]]")]
    uc.execute(_table(rows), date_from=date(2026, 1, 6), date_to=date(2026, 1, 6), draft_slots=draft)

    row = repo.saved.rows[0]
    assert "Klausur" in row[2]


def test_stattfindend_slot_written_with_content():
    """Stattfindender Slot schreibt den Wiki-Link in die Inhalt-Spalte."""
    rows = [["06-01-26", "", ""]]
    uc, repo = _make_uc()
    draft = [_slot(date(2026, 1, 6), content="[[abc123]]")]
    uc.execute(_table(rows), date_from=date(2026, 1, 6), date_to=date(2026, 1, 6), draft_slots=draft)

    row = repo.saved.rows[0]
    assert row[1] == "[[abc123]]"
    assert row[2] == ""


def test_empty_content_slot_has_empty_inhalt():
    """Slot ohne Inhalt erhält leere Inhalt- und Thema/Ausfall-Zellen."""
    rows = [["06-01-26", "[[abc123]]", ""]]
    uc, repo = _make_uc()
    draft = [_slot(date(2026, 1, 6), content="")]
    uc.execute(_table(rows), date_from=date(2026, 1, 6), date_to=date(2026, 1, 6), draft_slots=draft)

    row = repo.saved.rows[0]
    assert row[1] == ""
    assert row[2] == ""


def test_stattfindend_slot_with_oberthema_writes_thema_ausfall_cell():
    """Oberthema-Zellwert (noch nicht angelegte Einheit) wird in Thema/Ausfall geschrieben."""
    rows = [["06-01-26", "", "[[li2 Kodierung]]"]]
    uc, repo = _make_uc()
    draft = [_slot(date(2026, 1, 6), content="", oberthema_cell="[[li2 Kodierung]]")]
    uc.execute(_table(rows), date_from=date(2026, 1, 6), date_to=date(2026, 1, 6), draft_slots=draft)

    row = repo.saved.rows[0]
    assert row[1] == ""
    assert row[2] == "[[li2 Kodierung]]"


def test_dropped_contents_detected():
    """Wiki-Links aus dem alten Plan, die nicht im neuen Entwurf auftauchen, werden als dropped gemeldet."""
    rows = [
        ["06-01-26", "[[abc123]]", ""],
        ["07-01-26", "[[def456]]", ""],
    ]
    uc, repo = _make_uc()
    draft = [_slot(date(2026, 1, 6), content="[[abc123]]")]
    result = uc.execute(
        _table(rows), date_from=date(2026, 1, 6), date_to=date(2026, 1, 7), draft_slots=draft
    )
    assert "[[def456]]" in result.dropped_contents


def test_splice_adds_new_rows_for_new_dates():
    """Wenn der neue Entwurf mehr Dates als vorher enthält, werden alle eingefügt."""
    rows = [["06-01-26", "[[abc]]", ""]]
    uc, repo = _make_uc()
    draft = [
        _slot(date(2026, 1, 6), content="[[abc]]"),
        _slot(date(2026, 1, 7), content="[[def]]"),
    ]
    uc.execute(_table(rows), date_from=date(2026, 1, 6), date_to=date(2026, 1, 7), draft_slots=draft)

    assert len(repo.saved.rows) == 2
    assert repo.saved.rows[1][1] == "[[def]]"
