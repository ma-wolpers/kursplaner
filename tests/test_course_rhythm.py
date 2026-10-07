from __future__ import annotations

from datetime import date

import pytest

from kursplaner.core.domain.course_rhythm import (
    WeekdayRhythm,
    active_weekdays,
    current_segment,
    entry_applies_on,
    format_rhythm,
    hours_for_date,
    is_teaching_day,
    is_valid_rhythm_value,
    parity_from_token,
    parity_token,
    parse_lesson_hours,
    parse_rhythm,
    parse_rhythm_entry,
    segment_start,
    start_time_for_date,
    validate_rhythm,
    weekday_from_token,
    weekday_token,
)
from kursplaner.core.domain.yaml_registry import PLAN_METADATA_SCHEMA, parse_yaml_frontmatter


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
    entries = parse_rhythm(["Mo 08:00 2", "ab 20-04-26 Mo 14:00 1", "ab 01-06-26 Mo 09:00 3"])
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


# --- Ganz-Segment-Regel und Invarianten -------------------------------------


def test_current_segment_replaces_whole_rhythm_dropped_weekdays_end():
    """Ein ab-Segment ersetzt den ganzen Rhythmus: weggefallene Tage bleiben nicht aktiv."""
    entries = parse_rhythm(["Mo 08:00 2", "Do 07:50 2", "ab 20-04-26 Di 10:00 2"])
    before = current_segment(entries, date(2026, 4, 19))
    after = current_segment(entries, date(2026, 4, 20))
    assert [entry.weekday for entry in before] == [0, 3]
    assert [entry.weekday for entry in after] == [1]
    assert hours_for_date(entries, date(2026, 4, 23)) == 0  # Do nach dem Wechsel
    assert hours_for_date(entries, date(2026, 4, 21)) == 2  # Di nach dem Wechsel


def test_segment_start_treats_base_as_date_min():
    entries = parse_rhythm(["Mo 08:00 2", "ab 20-04-26 Mo 14:00 1"])
    assert segment_start(entries, date(2026, 1, 1)) == date.min
    assert segment_start(entries, date(2026, 4, 20)) == date(2026, 4, 20)


def test_validate_rhythm_requires_base_segment():
    with pytest.raises(ValueError, match="ohne 'ab"):
        parse_rhythm(["ab 20-04-26 Mo 08:00 2"])


def test_validate_rhythm_rejects_duplicate_weekday_in_segment():
    with pytest.raises(ValueError, match="mehrfach"):
        parse_rhythm(["Mo 08:00 2", "Mo 10:00 1"])
    with pytest.raises(ValueError, match="mehrfach"):
        validate_rhythm(parse_rhythm(["Mo 08:00 2"]) + parse_rhythm(["Mo 08:00 2"]))


def test_same_weekday_in_different_segments_is_valid():
    validate_rhythm(parse_rhythm(["Mo 08:00 2", "ab 20-04-26 Mo 14:00 1"]))


def test_legacy_rhythm_with_several_historic_segments_keeps_meaning():
    """Alte Dateien (Basis + mehrere ab-Segmente, ohne Kuerzel) bleiben ohne Migration gueltig."""
    raw = ["Mo 08:00 2", "ab 20-04-26 Mo 14:00 1", "ab 01-06-26 Mo 09:00 3"]
    assert is_valid_rhythm_value(raw) is True
    entries = parse_rhythm(raw)
    assert hours_for_date(entries, date(2026, 4, 13)) == 2
    assert start_time_for_date(entries, date(2026, 4, 27)) == "14:00"
    assert hours_for_date(entries, date(2026, 6, 1)) == 3
    assert format_rhythm(entries) == raw


def _plan_frontmatter(rhythm_lines: list[str]) -> str:
    """Baut eine minimal gueltige Plan-Frontmatter mit den gegebenen Rhythmus-Zeilen."""
    items = "".join(f'  - "{line}"\n' for line in rhythm_lines)
    return f'---\nLerngruppe: "[[GK blau-1]]"\nKursfach: "Mathematik"\nStufe: 11\nRhythmus:\n{items}---\n'


def test_plan_schema_accepts_valid_rhythm():
    data, _ = parse_yaml_frontmatter(_plan_frontmatter(["Mo 08:00 2", "ab 20-04-26 Di 10:00 2"]), PLAN_METADATA_SCHEMA)
    assert data["Rhythmus"] == ["Mo 08:00 2", "ab 20-04-26 Di 10:00 2"]


def test_plan_schema_rejects_rhythm_violating_invariants():
    """Hand-Dateien mit verletzter Invariante werden ueber den echten Ladepfad abgelehnt."""
    with pytest.raises(RuntimeError, match="Rhythmus"):
        parse_yaml_frontmatter(_plan_frontmatter(["Mo 08:00 2", "Mo 10:00 1"]), PLAN_METADATA_SCHEMA)
    with pytest.raises(RuntimeError, match="Rhythmus"):
        parse_yaml_frontmatter(_plan_frontmatter(["ab 20-04-26 Mo 08:00 2"]), PLAN_METADATA_SCHEMA)


# --- Wochenparitaet (gKW/uKW) -------------------------------------------------


def test_parse_and_format_roundtrip_with_parity():
    raw = ["Mo 08:00 2", "Do 07:50 2 gKW", "Do 11:30 1 uKW", "ab 20-04-26 Di 10:00 2 uKW"]
    entries = parse_rhythm(raw)
    assert [entry.week_parity for entry in entries] == [None, 0, 1, 1]
    assert format_rhythm(entries) == raw


def test_format_sorts_every_week_before_even_before_odd():
    entries = (
        WeekdayRhythm(weekday=3, start_time="11:30", hours=1, week_parity=1),
        WeekdayRhythm(weekday=3, start_time="07:50", hours=2, week_parity=0),
        WeekdayRhythm(weekday=0, start_time="08:00", hours=2),
    )
    assert format_rhythm(entries) == ["Mo 08:00 2", "Do 07:50 2 gKW", "Do 11:30 1 uKW"]


def test_parse_rejects_unknown_parity_token():
    with pytest.raises(ValueError):
        parse_rhythm_entry("Mo 08:00 2 aKW")


def test_validate_rejects_parity_overlaps():
    with pytest.raises(ValueError, match="mehrfach"):
        parse_rhythm(["Mo 08:00 2", "Mo 10:00 1 gKW"])
    with pytest.raises(ValueError, match="mehrfach"):
        parse_rhythm(["Mo 08:00 2 gKW", "Mo 10:00 1 gKW"])


def test_weekday_rhythm_constructor_enforces_invariants():
    with pytest.raises(ValueError):
        WeekdayRhythm(weekday=0, start_time="08:00", hours=2, week_parity=2)
    with pytest.raises(ValueError):
        WeekdayRhythm(weekday=7, start_time="08:00", hours=2)


def test_parity_tokens_roundtrip():
    assert parity_token(0) == "gKW"
    assert parity_from_token("uKW") == 1


def test_entry_applies_on_checks_weekday_and_iso_week_parity():
    entry = parse_rhythm_entry("Mo 08:00 2 gKW")
    assert entry_applies_on(entry, date(2026, 10, 12)) is True  # Mo, KW 42
    assert entry_applies_on(entry, date(2026, 10, 5)) is False  # Mo, KW 41
    assert entry_applies_on(entry, date(2026, 10, 13)) is False  # Di


def test_ab_day_has_independent_hours_and_start_times():
    entries = parse_rhythm(["Mo 08:00 2 gKW", "Mo 11:30 1 uKW"])
    assert hours_for_date(entries, date(2026, 10, 12)) == 2
    assert start_time_for_date(entries, date(2026, 10, 12)) == "08:00"
    assert hours_for_date(entries, date(2026, 10, 5)) == 1
    assert start_time_for_date(entries, date(2026, 10, 5)) == "11:30"


def test_biweekly_day_has_no_lesson_in_other_week():
    entries = parse_rhythm(["Do 07:50 2 uKW"])
    assert is_teaching_day(entries, date(2026, 10, 8)) is True  # KW 41
    assert is_teaching_day(entries, date(2026, 10, 15)) is False  # KW 42
    assert hours_for_date(entries, date(2026, 10, 15)) == 0


def test_iso_week_53_and_week_1_are_both_odd():
    """Kalendertechnisch: 2026 hat KW 53, danach folgt KW 1 - zwei ungerade Wochen hintereinander."""
    entries = parse_rhythm(["Do 07:50 2 uKW"])
    assert date(2026, 12, 31).isocalendar().week == 53
    assert date(2027, 1, 7).isocalendar().week == 1
    assert is_teaching_day(entries, date(2026, 12, 31)) is True
    assert is_teaching_day(entries, date(2027, 1, 7)) is True
