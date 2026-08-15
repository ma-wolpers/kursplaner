from __future__ import annotations

from datetime import date

import pytest

from kursplaner.core.domain.course_rhythm import (
    WeekdayRhythm,
    active_weekdays,
    current_segment,
    format_rhythm,
    hours_for_date,
    is_valid_rhythm_value,
    parse_lesson_hours,
    parse_rhythm,
    parse_rhythm_entry,
    start_time_for_date,
    weekday_from_token,
    weekday_token,
)


def test_weekday_token_roundtrip():
    assert weekday_token(3) == "Do"
    assert weekday_from_token("Do") == 3


def test_parse_rhythm_entry_basic():
    entry = parse_rhythm_entry("Mo 12:15 2")
    assert entry == WeekdayRhythm(weekday=0, start_time="12:15", hours=2, valid_from=None)


def test_parse_rhythm_entry_with_valid_from():
    entry = parse_rhythm_entry("ab 20-04-26 Di 08:00 1")
    assert entry.weekday == 1
    assert entry.valid_from == date(2026, 4, 20)


def test_parse_rhythm_entry_rejects_bad_format():
    with pytest.raises(ValueError):
        parse_rhythm_entry("Montags um 12 Uhr, 2 Stunden")


def test_parse_rhythm_entry_rejects_bad_time():
    with pytest.raises(ValueError):
        parse_rhythm_entry("Mo 25:99 2")


def test_parse_rhythm_entry_rejects_hours_out_of_range():
    with pytest.raises(ValueError):
        parse_rhythm_entry("Mo 08:00 5")


def test_parse_rhythm_accepts_list_and_single_string():
    assert parse_rhythm(["Mo 08:00 2", "Do 07:50 2"]) == (
        WeekdayRhythm(weekday=0, start_time="08:00", hours=2),
        WeekdayRhythm(weekday=3, start_time="07:50", hours=2),
    )
    assert parse_rhythm("Mo 08:00 2") == (WeekdayRhythm(weekday=0, start_time="08:00", hours=2),)
    assert parse_rhythm(None) == ()


def test_format_rhythm_sorts_by_segment_then_weekday():
    entries = (
        WeekdayRhythm(weekday=3, start_time="07:50", hours=2),
        WeekdayRhythm(weekday=0, start_time="12:15", hours=1, valid_from=date(2026, 4, 20)),
        WeekdayRhythm(weekday=0, start_time="12:15", hours=1),
    )
    assert format_rhythm(entries) == [
        "Mo 12:15 1",
        "Do 07:50 2",
        "ab 20-04-26 Mo 12:15 1",
    ]


def test_is_valid_rhythm_value():
    assert is_valid_rhythm_value(["Mo 08:00 2"]) is True
    assert is_valid_rhythm_value([]) is False
    assert is_valid_rhythm_value(["nicht geparst"]) is False


def test_current_segment_prefers_latest_valid_from_not_in_future():
    entries = parse_rhythm(
        ["Mo 08:00 2", "ab 20-04-26 Mo 14:00 1", "ab 01-06-26 Mo 09:00 3"]
    )
    active = current_segment(entries, date(2026, 5, 1))
    assert len(active) == 1
    assert active[0].start_time == "14:00"
    assert active[0].hours == 1


def test_current_segment_before_any_valid_from_uses_base():
    entries = parse_rhythm(["Mo 08:00 2", "ab 20-04-26 Mo 14:00 1"])
    active = current_segment(entries, date(2026, 1, 1))
    assert active[0].start_time == "08:00"


def test_hours_and_start_time_for_date_zero_for_non_teaching_day():
    entries = parse_rhythm(["Mo 08:00 2"])
    tuesday = date(2026, 1, 6)
    assert hours_for_date(entries, tuesday) == 0
    assert start_time_for_date(entries, tuesday) == ""


def test_hours_and_start_time_for_date_match_weekday():
    entries = parse_rhythm(["Do 07:50 2"])
    thursday = date(2026, 1, 8)
    assert hours_for_date(entries, thursday) == 2
    assert start_time_for_date(entries, thursday) == "07:50"


def test_active_weekdays_is_plain_set_of_entries():
    entries = parse_rhythm(["Mo 08:00 2", "Do 07:50 1"])
    assert active_weekdays(entries) == {0, 3}


def test_parse_lesson_hours_parses_valid_digit_string():
    assert parse_lesson_hours("3") == 3
    assert parse_lesson_hours("0") == 0


@pytest.mark.parametrize("raw", ["", None, "abc", "-1"])
def test_parse_lesson_hours_raises_on_invalid_value(raw):
    with pytest.raises(ValueError):
        parse_lesson_hours(raw)
