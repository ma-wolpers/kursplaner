"""Tests für `next_unit_policy.unit_counts_as_upcoming` — der einzige Wahrheitsort
für "gilt diese Einheit noch als anstehend?" im gesamten Codebase.
"""

from __future__ import annotations

from datetime import date, datetime, time

from kursplaner.core.domain.next_unit_policy import unit_counts_as_upcoming

_TODAY = date(2026, 3, 10)
_YESTERDAY = date(2026, 3, 9)
_TOMORROW = date(2026, 3, 11)


def _now(hour: int, minute: int = 0) -> datetime:
    return datetime(_TODAY.year, _TODAY.month, _TODAY.day, hour, minute)


def test_none_row_date_is_never_upcoming():
    assert unit_counts_as_upcoming(
        None, "10:00", now=_now(9), global_cutoff_enabled=False, global_cutoff_time=time(15, 0)
    ) is False


def test_past_date_is_not_upcoming():
    assert unit_counts_as_upcoming(
        _YESTERDAY, "10:00", now=_now(9), global_cutoff_enabled=False, global_cutoff_time=time(15, 0)
    ) is False


def test_future_date_is_upcoming_regardless_of_time():
    assert unit_counts_as_upcoming(
        _TOMORROW, "10:00", now=_now(23), global_cutoff_enabled=False, global_cutoff_time=time(15, 0)
    ) is True


def test_today_before_start_time_is_upcoming():
    assert unit_counts_as_upcoming(
        _TODAY, "10:00", now=_now(9, 59), global_cutoff_enabled=False, global_cutoff_time=time(15, 0)
    ) is True


def test_today_exactly_at_start_time_is_not_upcoming():
    assert unit_counts_as_upcoming(
        _TODAY, "10:00", now=_now(10, 0), global_cutoff_enabled=False, global_cutoff_time=time(15, 0)
    ) is False


def test_today_after_start_time_is_not_upcoming():
    assert unit_counts_as_upcoming(
        _TODAY, "10:00", now=_now(10, 1), global_cutoff_enabled=False, global_cutoff_time=time(15, 0)
    ) is False


def test_missing_start_time_defaults_conservatively_to_upcoming():
    assert unit_counts_as_upcoming(
        _TODAY, "", now=_now(23, 59), global_cutoff_enabled=False, global_cutoff_time=time(15, 0)
    ) is True


def test_unparsable_start_time_defaults_conservatively_to_upcoming():
    assert unit_counts_as_upcoming(
        _TODAY, "not-a-time", now=_now(23, 59), global_cutoff_enabled=False, global_cutoff_time=time(15, 0)
    ) is True


def test_global_cutoff_enabled_ignores_start_time_before_cutoff():
    assert unit_counts_as_upcoming(
        _TODAY, "08:00", now=_now(14, 59), global_cutoff_enabled=True, global_cutoff_time=time(15, 0)
    ) is True


def test_global_cutoff_enabled_ignores_start_time_at_cutoff():
    assert unit_counts_as_upcoming(
        _TODAY, "08:00", now=_now(15, 0), global_cutoff_enabled=True, global_cutoff_time=time(15, 0)
    ) is False


def test_global_cutoff_enabled_ignores_start_time_after_cutoff():
    assert unit_counts_as_upcoming(
        _TODAY, "23:00", now=_now(15, 1), global_cutoff_enabled=True, global_cutoff_time=time(15, 0)
    ) is False
