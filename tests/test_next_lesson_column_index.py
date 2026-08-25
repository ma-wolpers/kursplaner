"""Tests für `MainWindowOverviewController._next_lesson_column_index()`.

Deckt zwei Dinge ab:

1. Die historische Regression aus der dict->DayColumn-Migration (Commit
   c737e2c): `_next_lesson_column_index()` griff per `.get(...)` auf die
   inzwischen echten `DayColumn`-Instanzen zu und warf dadurch bei jedem
   Aufruf eine `AttributeError`. Die bestehenden Tests in
   `test_selection_controller.py` und `test_row_filter_navigation.py`
   stubben die Methode komplett weg und hätten diese Regression nie erkannt
   — hier läuft die echte Implementierung gegen echte `DayColumn`-Instanzen.

2. Die Umstellung auf `next_unit_policy.unit_counts_as_upcoming` als
   einzigen Wahrheitsort: die Methode delegiert vollständig an die Policy
   (Startzeit-Vergleich per Default, optionaler globaler Cutoff), statt
   eigene Zeitvergleichslogik zu enthalten.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace

from kursplaner.adapters.gui import overview_controller as overview_controller_module
from kursplaner.adapters.gui.overview_controller import MainWindowOverviewController
from kursplaner.core.domain.course_rhythm import WeekdayRhythm
from tests.day_column_factory import make_day_column

_TODAY = date.today()
_YESTERDAY = _TODAY - timedelta(days=1)
_TOMORROW = _TODAY + timedelta(days=1)


def _next_index(day_columns, *, now: datetime | None = None):
    controller = object.__new__(MainWindowOverviewController)
    controller.app = SimpleNamespace(day_columns=day_columns)
    return controller._next_lesson_column_index(now=now)


def _rhythm_at(day: date, start_time: str) -> tuple[WeekdayRhythm, ...]:
    return (WeekdayRhythm(weekday=day.weekday(), start_time=start_time, hours=2),)


def test_returns_none_for_empty_day_columns():
    assert _next_index([]) is None


def test_returns_index_of_future_unit_without_attribute_error():
    columns = [
        make_day_column(row_index=0, datum=_YESTERDAY.isoformat()),
        make_day_column(row_index=1, datum=_TOMORROW.isoformat()),
    ]
    assert _next_index(columns) == 1


def test_todays_unit_without_rhythm_counts_as_next_by_conservative_fallback():
    """Ohne ermittelbare Startzeit (kein Rhythmus-Eintrag) gilt heute weiterhin als anstehend."""
    columns = [
        make_day_column(row_index=0, datum=_YESTERDAY.isoformat()),
        make_day_column(row_index=1, datum=_TODAY.isoformat()),
        make_day_column(row_index=2, datum=_TOMORROW.isoformat()),
    ]
    assert _next_index(columns) == 1


def test_todays_unit_before_start_time_counts_as_next():
    # DayColumn.startzeit() loest ueber parse_plan_row_date() strikt das
    # DD-MM-YY-Zeilenformat auf (nicht ISO) -- fuer diesen Test relevant, da
    # sonst keine Startzeit ermittelbar waere (konservativer Fallback wuerde
    # den eigentlichen Startzeit-Vergleich verdecken).
    now = datetime.combine(_TODAY, datetime.min.time().replace(hour=7))
    columns = [
        make_day_column(row_index=0, datum=_TODAY.strftime("%d-%m-%y"), rhythm=_rhythm_at(_TODAY, "08:00")),
        make_day_column(row_index=1, datum=_TOMORROW.strftime("%d-%m-%y")),
    ]
    assert _next_index(columns, now=now) == 0


def test_todays_unit_after_start_time_rolls_over_to_next_occurring_column():
    now = datetime.combine(_TODAY, datetime.min.time().replace(hour=9))
    columns = [
        make_day_column(row_index=0, datum=_TODAY.strftime("%d-%m-%y"), rhythm=_rhythm_at(_TODAY, "08:00")),
        make_day_column(row_index=1, datum=_TOMORROW.strftime("%d-%m-%y")),
    ]
    assert _next_index(columns, now=now) == 1


def test_cancelled_columns_are_skipped_for_date_match_and_fallback():
    columns = [
        make_day_column(row_index=0, datum=_TODAY.isoformat(), thema_ausfall="X Grund"),
        make_day_column(row_index=1, datum=_TOMORROW.isoformat(), thema_ausfall="X Grund"),
        make_day_column(row_index=2, datum=_TOMORROW.isoformat()),
    ]
    assert _next_index(columns) == 2


def test_falls_back_to_first_occurring_column_when_all_dates_are_past():
    columns = [
        make_day_column(row_index=0, datum=_YESTERDAY.isoformat(), thema_ausfall="X Grund"),
        make_day_column(row_index=1, datum=_YESTERDAY.isoformat()),
        make_day_column(row_index=2, datum=(_YESTERDAY - timedelta(days=1)).isoformat()),
    ]
    assert _next_index(columns) == 1


def test_columns_without_parsable_date_are_skipped_but_count_for_fallback():
    columns = [
        make_day_column(row_index=0, datum=""),
        make_day_column(row_index=1, datum="kein Datum"),
    ]
    assert _next_index(columns) == 0


def test_global_cutoff_mode_overrides_start_time(monkeypatch):
    """Aktivierter globaler Cutoff ersetzt die Startzeit-Pruefung vollstaendig."""
    monkeypatch.setattr(overview_controller_module, "load_next_unit_mode", lambda: overview_controller_module.NEXT_UNIT_MODE_FEST)
    monkeypatch.setattr(overview_controller_module, "load_next_unit_cutoff_time", lambda: datetime.min.time().replace(hour=15))

    columns = [
        # Startzeit 08:00 waere im Standardmodus um 09:00 bereits vorbei,
        # zaehlt im Cutoff-Modus (15:00) aber noch als anstehend.
        make_day_column(row_index=0, datum=_TODAY.strftime("%d-%m-%y"), rhythm=_rhythm_at(_TODAY, "08:00")),
        make_day_column(row_index=1, datum=_TOMORROW.strftime("%d-%m-%y")),
    ]
    now = datetime.combine(_TODAY, datetime.min.time().replace(hour=9))

    assert _next_index(columns, now=now) == 0
