from __future__ import annotations

from datetime import date

from kursplaner.adapters.gui.school_wide_cancellation_dialog import parse_flexible_date, resolve_date_range

_TODAY = date(2026, 8, 16)


# ---------------------------------------------------------------------------
# parse_flexible_date
# ---------------------------------------------------------------------------


def test_parse_full_date():
    assert parse_flexible_date("14.09.2026", today=_TODAY) == date(2026, 9, 14)


def test_parse_two_digit_year():
    assert parse_flexible_date("14.09.26", today=_TODAY) == date(2026, 9, 14)


def test_parse_without_year_uses_today_year():
    assert parse_flexible_date("14.09.", today=_TODAY) == date(2026, 9, 14)


def test_parse_without_year_no_trailing_dot():
    assert parse_flexible_date("14.09", today=_TODAY) == date(2026, 9, 14)


def test_parse_empty_is_none():
    assert parse_flexible_date("", today=_TODAY) is None
    assert parse_flexible_date("   ", today=_TODAY) is None


def test_parse_garbage_is_none():
    assert parse_flexible_date("nicht ein datum", today=_TODAY) is None


def test_parse_feb_29_without_year_in_leap_target_year():
    """29.02. ohne Jahr muss im Zieljahr gültig sein, wenn dieses ein Schaltjahr ist (2028)."""
    assert parse_flexible_date("29.02.", today=date(2028, 1, 1)) == date(2028, 2, 29)


def test_parse_feb_29_without_year_in_non_leap_target_year_is_none():
    assert parse_flexible_date("29.02.", today=_TODAY) is None


# ---------------------------------------------------------------------------
# resolve_date_range
# ---------------------------------------------------------------------------


def test_resolve_range_with_explicit_bis():
    assert resolve_date_range("06.01.2026", "07.01.2026", today=_TODAY) == (date(2026, 1, 6), date(2026, 1, 7))


def test_resolve_range_empty_bis_is_single_day():
    assert resolve_date_range("06.01.2026", "", today=_TODAY) == (date(2026, 1, 6), date(2026, 1, 6))
    assert resolve_date_range("06.01.2026", "   ", today=_TODAY) == (date(2026, 1, 6), date(2026, 1, 6))


def test_resolve_range_invalid_von_is_none():
    assert resolve_date_range("", "07.01.2026", today=_TODAY) is None
    assert resolve_date_range("garbage", "07.01.2026", today=_TODAY) is None


def test_resolve_range_invalid_bis_is_none():
    assert resolve_date_range("06.01.2026", "garbage", today=_TODAY) is None


def test_resolve_range_bis_before_von_is_none():
    assert resolve_date_range("07.01.2026", "06.01.2026", today=_TODAY) is None


def test_resolve_range_bis_equal_von_is_valid():
    assert resolve_date_range("06.01.2026", "06.01.2026", today=_TODAY) == (date(2026, 1, 6), date(2026, 1, 6))


def test_resolve_range_year_optional_on_both_fields():
    assert resolve_date_range("06.01.", "07.01.", today=_TODAY) == (date(2026, 1, 6), date(2026, 1, 7))
