"""Regressionstests für `MainWindowOverviewController._next_lesson_column_index()`.

Deckt die Regression aus der dict->DayColumn-Migration (Commit c737e2c) ab:
`_next_lesson_column_index()` griff weiterhin per `.get(...)` auf die inzwischen
echten `DayColumn`-Instanzen zu und warf dadurch bei jedem Aufruf eine
`AttributeError`. Die bestehenden Tests in `test_selection_controller.py` und
`test_row_filter_navigation.py` stubben die Methode komplett weg und hätten
diese Regression nie erkannt — hier läuft die echte Implementierung gegen
echte `DayColumn`-Instanzen.

Der Kontrollfluss selbst (die `day_date >= today`-Bedingung und der Fallback
auf die erste nicht-abgesagte Spalte) ist bereits vor der Migration vorhanden
und unverändert; die Tests hier schützen also bestehendes Verhalten, ohne
neue Semantik festzuschreiben.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from kursplaner.adapters.gui.overview_controller import MainWindowOverviewController
from tests.day_column_factory import make_day_column

_TODAY = date.today()
_YESTERDAY = _TODAY - timedelta(days=1)
_TOMORROW = _TODAY + timedelta(days=1)


def _next_index(day_columns):
    controller = object.__new__(MainWindowOverviewController)
    controller.app = SimpleNamespace(day_columns=day_columns)
    return controller._next_lesson_column_index()


def test_returns_none_for_empty_day_columns():
    assert _next_index([]) is None


def test_returns_index_of_future_unit_without_attribute_error():
    columns = [
        make_day_column(row_index=0, datum=_YESTERDAY.isoformat()),
        make_day_column(row_index=1, datum=_TOMORROW.isoformat()),
    ]
    assert _next_index(columns) == 1


def test_todays_unit_counts_as_next():
    columns = [
        make_day_column(row_index=0, datum=_YESTERDAY.isoformat()),
        make_day_column(row_index=1, datum=_TODAY.isoformat()),
        make_day_column(row_index=2, datum=_TOMORROW.isoformat()),
    ]
    assert _next_index(columns) == 1


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
