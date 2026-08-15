from __future__ import annotations

from datetime import date
from pathlib import Path

from kursplaner.core.domain.course_rhythm import WeekdayRhythm
from kursplaner.core.usecases.timetable_change_usecase import (
    TimetableChangeUseCase,
    column_is_ferien,
    column_is_manual_ausfall,
    column_is_stattfindend,
)
from tests.day_column_factory import make_day_column

# ---------------------------------------------------------------------------
# Predicate wrapper tests
# ---------------------------------------------------------------------------


def _day(*, is_ferien: bool = False, is_cancel: bool = False):
    if is_ferien:
        thema_ausfall = "X Ferien X"
    elif is_cancel:
        thema_ausfall = "X Ausfall"
    else:
        thema_ausfall = ""
    return make_day_column(thema_ausfall=thema_ausfall)


def test_column_is_ferien_true():
    assert column_is_ferien(_day(is_ferien=True, is_cancel=True)) is True


def test_column_is_ferien_false():
    assert column_is_ferien(_day(is_ferien=False)) is False


def test_column_is_manual_ausfall():
    assert column_is_manual_ausfall(_day(is_cancel=True)) is True


def test_column_is_manual_ausfall_rejects_ferien():
    assert column_is_manual_ausfall(_day(is_ferien=True, is_cancel=True)) is False


def test_column_is_stattfindend():
    assert column_is_stattfindend(_day(is_cancel=False)) is True


def test_column_is_stattfindend_rejects_cancel():
    assert column_is_stattfindend(_day(is_cancel=True)) is False


def test_column_is_stattfindend_rejects_ferien():
    assert column_is_stattfindend(_day(is_ferien=True, is_cancel=True)) is False


# ---------------------------------------------------------------------------
# TimetableChangeUseCase.compute() tests
# ---------------------------------------------------------------------------


class _FakeCalendarRepo:
    """Stub: keine Ferien, keine Ereignisse."""

    def load_calendar_data(self, calendar_dir, years):
        return {}, [], []


class _FakeCalendarRepoWithEvents:
    """Stub: ein bestimmtes Datum ist Ferientag."""

    def __init__(self, ferien_dates: set[date]) -> None:
        self._dates = ferien_dates

    def load_calendar_data(self, calendar_dir, years):
        events = {d: "X Ferien" for d in self._dates}
        return events, [], []


def _make_uc(repo=None) -> TimetableChangeUseCase:
    return TimetableChangeUseCase(calendar_repo=repo or _FakeCalendarRepo())


def _rhythm(hours_by_weekday: dict[int, int]) -> tuple[WeekdayRhythm, ...]:
    return tuple(
        WeekdayRhythm(weekday=weekday, start_time="00:00", hours=hours)
        for weekday, hours in sorted(hours_by_weekday.items())
    )


def _stattfindend_day(datum_str: str, inhalt: str = "[[abc123]]", thema_ausfall: str = ""):
    return make_day_column(datum=datum_str, inhalt=inhalt, thema_ausfall=thema_ausfall)


def _ausfall_day(datum_str: str):
    return make_day_column(datum=datum_str, thema_ausfall="X Klausur")


def _ferien_day(datum_str: str):
    return make_day_column(datum=datum_str, thema_ausfall="X Ferien X")


def test_compute_empty_range():
    """Kein Wochentag im Bereich passend → leere draft_slots."""
    uc = _make_uc()
    # Jan 6, 2026 = Tuesday (weekday 1). new_rhythm has only Monday (0) → no slot generated.
    result = uc.compute(
        day_columns=[],
        date_from=date(2026, 1, 6),
        date_to=date(2026, 1, 6),
        new_rhythm=_rhythm({0: 2}),
        calendar_dir=Path("."),
    )
    assert result.old_units == []
    assert result.draft_slots == []


def test_compute_same_timetable_one_to_one():
    """Einheiten werden 1:1 auf neue Slots verteilt, wenn der Plan identisch bleibt."""
    # Jan 5, 2026 = Monday (weekday 0); Jan 7 = Wednesday (weekday 2)
    day_columns = [
        _stattfindend_day("05-01-26", "[[abc123]]"),
        _stattfindend_day("07-01-26", "[[def456]]"),
    ]
    uc = _make_uc()
    result = uc.compute(
        day_columns=day_columns,
        date_from=date(2026, 1, 5),
        date_to=date(2026, 1, 7),
        new_rhythm=_rhythm({0: 2, 2: 2}),
        calendar_dir=Path("."),
    )
    assert len(result.old_units) == 2
    stattfindend_slots = [s for s in result.draft_slots if not s.is_ferien]
    assert len(stattfindend_slots) == 2
    assert stattfindend_slots[0].content == "[[abc123]]"
    assert stattfindend_slots[1].content == "[[def456]]"


def test_compute_ferien_dates_get_ferien_slots():
    """Kalendertage mit Ferien-Event ergeben is_ferien=True-Slots."""
    ferien_date = date(2026, 1, 7)
    repo = _FakeCalendarRepoWithEvents({ferien_date})
    uc = _make_uc(repo)
    day_columns = [_stattfindend_day("07-01-26", "[[abc123]]")]
    result = uc.compute(
        day_columns=day_columns,
        date_from=date(2026, 1, 7),
        date_to=date(2026, 1, 7),
        new_rhythm=_rhythm({2: 2}),
        calendar_dir=Path("."),
    )
    assert len(result.draft_slots) == 1
    assert result.draft_slots[0].is_ferien is True
    assert result.draft_slots[0].content == ""


def test_compute_old_ferien_not_counted_as_manual_ausfall_for_recovered_week():
    """Ferien-Tage im alten Plan lösen keine recovered-Markierung aus."""
    day_columns = [
        _ferien_day("06-01-26"),  # Monday, KW2
        _stattfindend_day("07-01-26", "[[abc123]]"),  # Tuesday, KW2
    ]
    uc = _make_uc()
    result = uc.compute(
        day_columns=day_columns,
        date_from=date(2026, 1, 6),
        date_to=date(2026, 1, 7),
        new_rhythm=_rhythm({1: 2}),
        calendar_dir=Path("."),
    )
    # Only Tuesday is in new plan (Tuesday = weekday 1)
    assert len(result.draft_slots) == 1
    assert result.draft_slots[0].was_recovered_week is False


def test_compute_manual_ausfall_marks_recovered_week():
    """Manueller Ausfall im alten Plan → stattfindende neue Slots in gleicher Woche = recovered."""
    day_columns = [
        _ausfall_day("06-01-26"),  # Monday KW2 — manual ausfall
        _stattfindend_day("08-01-26", "[[abc123]]"),  # Wednesday KW2 — stattfindend
    ]
    uc = _make_uc()
    result = uc.compute(
        day_columns=day_columns,
        date_from=date(2026, 1, 6),
        date_to=date(2026, 1, 8),
        new_rhythm=_rhythm({1: 2}),  # new plan: Tuesday only (KW2)
        calendar_dir=Path("."),
    )
    stattfindend = [s for s in result.draft_slots if not s.is_ferien]
    assert len(stattfindend) == 1
    assert stattfindend[0].was_recovered_week is True


def test_compute_more_old_than_new_truncates():
    """Mehr alte Einheiten als neue Slots: überschüssige Inhalte werden nicht platziert."""
    # Jan 5 Mon, Jan 7 Wed, Jan 9 Fri — 3 old stattfindend units in range Jan 5-9
    # New plan: Monday only → 1 slot (Jan 5). Only first content is placed.
    day_columns = [
        _stattfindend_day("05-01-26", "[[abc]]"),
        _stattfindend_day("07-01-26", "[[def]]"),
        _stattfindend_day("09-01-26", "[[ghi]]"),
    ]
    uc = _make_uc()
    result = uc.compute(
        day_columns=day_columns,
        date_from=date(2026, 1, 5),
        date_to=date(2026, 1, 9),
        new_rhythm=_rhythm({0: 2}),  # only Monday → Jan 5 only
        calendar_dir=Path("."),
    )
    stattfindend = [s for s in result.draft_slots if not s.is_ferien]
    assert len(stattfindend) == 1
    assert stattfindend[0].content == "[[abc]]"


def test_compute_carries_oberthema_of_not_yet_created_unit():
    """Eine alte Einheit ohne Inhalt, aber mit Oberthema in Thema/Ausfall, wird nicht verworfen."""
    day_columns = [_stattfindend_day("05-01-26", inhalt="", thema_ausfall="[[li2 Kodierung]]")]
    uc = _make_uc()
    result = uc.compute(
        day_columns=day_columns,
        date_from=date(2026, 1, 5),
        date_to=date(2026, 1, 5),
        new_rhythm=_rhythm({0: 2}),
        calendar_dir=Path("."),
    )
    stattfindend = [s for s in result.draft_slots if not s.is_ferien]
    assert len(stattfindend) == 1
    assert stattfindend[0].content == ""
    assert stattfindend[0].oberthema_cell == "[[li2 Kodierung]]"


def test_compute_more_new_than_old_leaves_empty_slots():
    """Weniger alte Einheiten als neue Slots: überschüssige neue Slots bleiben leer."""
    # Old: 1 stattfindend unit on Jan 5 (Mon). New plan: Mon + Wed (Jan 5 + Jan 7). Second slot empty.
    day_columns = [_stattfindend_day("05-01-26", "[[abc]]")]
    uc = _make_uc()
    result = uc.compute(
        day_columns=day_columns,
        date_from=date(2026, 1, 5),
        date_to=date(2026, 1, 7),
        new_rhythm=_rhythm({0: 2, 2: 2}),  # Monday (Jan 5) + Wednesday (Jan 7)
        calendar_dir=Path("."),
    )
    stattfindend = [s for s in result.draft_slots if not s.is_ferien]
    assert len(stattfindend) == 2
    assert stattfindend[0].content == "[[abc]]"
    assert stattfindend[1].content == ""
