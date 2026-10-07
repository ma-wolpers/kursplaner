from __future__ import annotations

from datetime import date
from pathlib import Path

from kursplaner.core.domain.course_rhythm import WeekdayRhythm
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
    """Captures save_plan_table/update_plan_rhythm calls without touching the file system."""

    def __init__(self) -> None:
        self.saved: PlanTableData | None = None
        self.rhythm_calls: list[tuple[Path, tuple[WeekdayRhythm, ...]]] = []

    def save_plan_table(self, table: PlanTableData) -> None:
        self.saved = table

    def update_plan_rhythm(self, markdown_path: Path, rhythm: tuple[WeekdayRhythm, ...]) -> None:
        self.rhythm_calls.append((markdown_path, rhythm))


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


def test_rhythm_segment_is_appended_when_earlier_rows_exist():
    """Existiert eine Planzeile vor date_from, muss das alte Segment erhalten bleiben."""
    rows = [
        ["10-03-26", "[[before]]", ""],
        ["17-03-26", "[[abc]]", ""],
    ]
    uc, repo = _make_uc()
    table = _table(rows)
    table.metadata["Rhythmus"] = ["Di 08:00 2"]
    new_segment = (WeekdayRhythm(weekday=1, start_time="08:00", hours=1, valid_from=date(2026, 3, 17)),)
    draft = [_slot(date(2026, 3, 17), content="[[abc]]")]

    uc.execute(
        table, date_from=date(2026, 3, 17), date_to=date(2026, 3, 17), draft_slots=draft, rhythm_segment=new_segment
    )

    assert len(repo.rhythm_calls) == 1
    _path, combined = repo.rhythm_calls[0]
    assert len(combined) == 2
    assert combined[0].valid_from is None
    assert combined[1].valid_from == date(2026, 3, 17)


def test_rhythm_segment_replaces_instead_of_appending_when_no_earlier_row_exists():
    """Ohne Planzeile vor date_from ist die neue Startzeit faktisch der Kursbeginn -
    ein zusaetzliches 'ab'-Segment neben dem alten waere sinnlos; der Rhythmus wird
    stattdessen komplett ersetzt (und die neuen Eintraege verlieren ihr valid_from,
    da sie ab dem Kursbeginn gelten)."""
    rows = [["17-03-26", "[[abc]]", ""]]
    uc, repo = _make_uc()
    table = _table(rows)
    table.metadata["Rhythmus"] = ["Di 08:00 2"]
    new_segment = (WeekdayRhythm(weekday=1, start_time="11:30", hours=1, valid_from=date(2026, 3, 17)),)
    draft = [_slot(date(2026, 3, 17), content="[[abc]]")]

    uc.execute(
        table, date_from=date(2026, 3, 17), date_to=date(2026, 3, 17), draft_slots=draft, rhythm_segment=new_segment
    )

    assert len(repo.rhythm_calls) == 1
    _path, combined = repo.rhythm_calls[0]
    assert len(combined) == 1
    assert combined[0].start_time == "11:30"
    assert combined[0].valid_from is None


# ---------------------------------------------------------------------------
# Befristete Stundenplanaenderung (Bis vor Kursende) -> Rueckkehr-Segment
# ---------------------------------------------------------------------------


def _apply_rhythm_change(rows, *, existing, new, date_from, date_to):
    """Fuehrt eine Stundenplanaenderung mit neuem Rhythmus aus und liefert den persistierten Rhythmus."""
    from kursplaner.core.domain.course_rhythm import parse_rhythm

    uc, repo = _make_uc()
    table = _table(rows)
    table.metadata["Rhythmus"] = existing
    segment = tuple(
        WeekdayRhythm(
            weekday=e.weekday, start_time=e.start_time, hours=e.hours, valid_from=date_from, week_parity=e.week_parity
        )
        for e in parse_rhythm(new)
    )
    uc.execute(table, date_from=date_from, date_to=date_to, draft_slots=[], rhythm_segment=segment)
    assert len(repo.rhythm_calls) == 1
    return repo.rhythm_calls[0][1]


def test_temporary_change_before_course_end_restores_old_rhythm_afterwards():
    from kursplaner.core.domain.course_rhythm import format_rhythm, hours_for_date, start_time_for_date

    rows = [["02-03-26", "", ""], ["09-03-26", "", ""], ["16-03-26", "", ""], ["23-03-26", "", ""]]
    combined = _apply_rhythm_change(
        rows, existing=["Mo 08:00 2"], new=["Mo 11:30 1"], date_from=date(2026, 3, 9), date_to=date(2026, 3, 15)
    )
    assert format_rhythm(combined) == ["Mo 08:00 2", "ab 09-03-26 Mo 11:30 1", "ab 16-03-26 Mo 08:00 2"]
    assert hours_for_date(combined, date(2026, 3, 9)) == 1
    assert hours_for_date(combined, date(2026, 3, 16)) == 2
    assert start_time_for_date(combined, date(2026, 3, 23)) == "08:00"


def test_temporary_change_from_first_plan_day_restores_original_base():
    """Ersatz-Zweig (keine Zeile vor date_from): Rueckkehr nutzt trotzdem den urspruenglichen Rhythmus."""
    from kursplaner.core.domain.course_rhythm import format_rhythm, hours_for_date

    rows = [["02-03-26", "", ""], ["09-03-26", "", ""], ["16-03-26", "", ""]]
    combined = _apply_rhythm_change(
        rows, existing=["Mo 08:00 2"], new=["Mo 11:30 1"], date_from=date(2026, 3, 2), date_to=date(2026, 3, 8)
    )
    assert format_rhythm(combined) == ["Mo 11:30 1", "ab 09-03-26 Mo 08:00 2"]
    assert hours_for_date(combined, date(2026, 3, 16)) == 2


def test_only_ferien_row_after_date_to_still_triggers_return():
    from kursplaner.core.domain.course_rhythm import format_rhythm

    rows = [["02-03-26", "", ""], ["09-03-26", "", ""], ["16-03-26", "", "X Osterferien X"]]
    combined = _apply_rhythm_change(
        rows, existing=["Mo 08:00 2"], new=["Mo 11:30 1"], date_from=date(2026, 3, 9), date_to=date(2026, 3, 15)
    )
    assert format_rhythm(combined)[-1] == "ab 16-03-26 Mo 08:00 2"


def test_dateless_row_after_date_to_does_not_trigger_return():
    from kursplaner.core.domain.course_rhythm import format_rhythm

    rows = [["02-03-26", "", ""], ["09-03-26", "", ""], ["", "[[verdraengt]]", ""]]
    combined = _apply_rhythm_change(
        rows, existing=["Mo 08:00 2"], new=["Mo 11:30 1"], date_from=date(2026, 3, 9), date_to=date(2026, 3, 15)
    )
    assert format_rhythm(combined) == ["Mo 08:00 2", "ab 09-03-26 Mo 11:30 1"]


def test_preview_hours_match_persisted_rhythm_even_with_existing_segment_in_range():
    """Vorschau (TimetableChangeUseCase.compute) = Ergebnis nach dem Uebernehmen im Aenderungsbereich."""
    from kursplaner.core.domain.course_rhythm import hours_for_date, parse_rhythm
    from kursplaner.core.usecases.timetable_change_usecase import TimetableChangeUseCase

    class _NoCalendar:
        def load_calendar_data(self, calendar_dir, years):
            return {}, [], []

    date_from, date_to = date(2026, 9, 28), date(2026, 10, 25)
    new = tuple(
        WeekdayRhythm(
            weekday=e.weekday, start_time=e.start_time, hours=e.hours, valid_from=date_from, week_parity=e.week_parity
        )
        for e in parse_rhythm(["Mo 08:00 2 gKW", "Mo 11:30 1 uKW", "Do 07:50 3"])
    )
    preview = TimetableChangeUseCase(calendar_repo=_NoCalendar()).compute(
        day_columns=[], date_from=date_from, date_to=date_to, new_rhythm=new, calendar_dir=Path(".")
    )
    rows = [["21-09-26", "", ""], ["26-10-26", "", ""]]
    combined = _apply_rhythm_change(
        rows,
        existing=["Mo 08:00 2", "ab 05-10-26 Fr 10:00 1"],
        new=["Mo 08:00 2 gKW", "Mo 11:30 1 uKW", "Do 07:50 3"],
        date_from=date_from,
        date_to=date_to,
    )
    assert preview.draft_slots
    for slot in preview.draft_slots:
        assert hours_for_date(combined, slot.datum) == slot.stunden
