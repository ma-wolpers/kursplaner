"""Tests fuer `course_rhythm.splice_segment` (Segment einer Stundenplanaenderung einfuegen)."""

from __future__ import annotations

from datetime import date

from kursplaner.core.domain.course_rhythm import format_rhythm, hours_for_date, parse_rhythm, splice_segment

FROM = date(2026, 3, 2)
TO = date(2026, 3, 13)


def _splice(existing: list[str], new: list[str], *, before: bool = True, after: bool = True) -> list[str]:
    """Fuehrt `splice_segment` auf md-Zeilen aus und liefert die kanonischen md-Zeilen."""
    result = splice_segment(
        parse_rhythm(existing),
        parse_rhythm(new),
        date_from=FROM,
        date_to=TO,
        has_row_before=before,
        has_row_after=after,
    )
    return format_rhythm(result)


def test_temporary_change_appends_return_segment():
    assert _splice(["Mo 08:00 2"], ["Di 10:00 1"]) == [
        "Mo 08:00 2",
        "ab 02-03-26 Di 10:00 1",
        "ab 14-03-26 Mo 08:00 2",
    ]


def test_no_return_segment_without_rows_after():
    assert _splice(["Mo 08:00 2"], ["Di 10:00 1"], after=False) == ["Mo 08:00 2", "ab 02-03-26 Di 10:00 1"]


def test_segments_inside_range_are_removed():
    existing = ["Mo 08:00 2", "ab 05-03-26 Do 07:50 2"]
    assert _splice(existing, ["Di 10:00 1"], after=False) == ["Mo 08:00 2", "ab 02-03-26 Di 10:00 1"]


def test_return_segment_restores_rhythm_valid_at_return_date_from_original():
    """Ein im Bereich beginnendes Segment gilt auch danach - die Rueckkehr nimmt es aus dem Original."""
    existing = ["Mo 08:00 2", "ab 05-03-26 Do 07:50 2"]
    assert _splice(existing, ["Di 10:00 1"]) == [
        "Mo 08:00 2",
        "ab 02-03-26 Di 10:00 1",
        "ab 14-03-26 Do 07:50 2",
    ]


def test_replace_branch_without_earlier_row_becomes_base():
    assert _splice(["Mo 08:00 2"], ["Di 10:00 1"], before=False, after=False) == ["Di 10:00 1"]


def test_replace_branch_return_segment_keeps_original_base():
    """Rote Falle: Die Basis wird ersetzt, die Rueckkehr enthaelt trotzdem die URSPRUENGLICHE Basis."""
    result = _splice(["Mo 08:00 2"], ["Di 10:00 1"], before=False)
    assert result == ["Di 10:00 1", "ab 14-03-26 Mo 08:00 2"]
    assert "Di" not in result[1]


def test_replace_branch_drops_older_ab_segment_before_date_from():
    """Ein altes ab-Segment vor date_from wuerde die neue Basis sonst ueberstimmen."""
    existing = ["Mo 08:00 2", "ab 01-03-26 Do 07:50 2"]
    result = splice_segment(
        parse_rhythm(existing),
        parse_rhythm(["Mi 09:00 1"]),
        date_from=FROM,
        date_to=TO,
        has_row_before=False,
        has_row_after=False,
    )
    assert format_rhythm(result) == ["Mi 09:00 1"]
    assert hours_for_date(result, date(2026, 3, 11)) == 1  # Mi im Bereich


def test_no_duplicate_when_segment_already_starts_after_date_to():
    existing = ["Mo 08:00 2", "ab 14-03-26 Fr 08:00 1"]
    assert _splice(existing, ["Di 10:00 1"]) == [
        "Mo 08:00 2",
        "ab 02-03-26 Di 10:00 1",
        "ab 14-03-26 Fr 08:00 1",
    ]


def test_later_segment_is_kept_and_takes_over_at_its_date():
    existing = ["Mo 08:00 2", "ab 20-04-26 Fr 08:00 1"]
    result = splice_segment(
        parse_rhythm(existing),
        parse_rhythm(["Di 10:00 1"]),
        date_from=FROM,
        date_to=TO,
        has_row_before=True,
        has_row_after=True,
    )
    assert format_rhythm(result) == [
        "Mo 08:00 2",
        "ab 02-03-26 Di 10:00 1",
        "ab 14-03-26 Mo 08:00 2",
        "ab 20-04-26 Fr 08:00 1",
    ]
    assert hours_for_date(result, date(2026, 3, 16)) == 2  # Mo nach Rueckkehr
    assert hours_for_date(result, date(2026, 4, 24)) == 1  # Fr im spaeteren Segment
    assert hours_for_date(result, date(2026, 4, 20)) == 0  # Mo dort entfallen


def test_splice_keeps_parity_entries():
    result = _splice(["Mo 08:00 2 gKW", "Mo 11:30 1 uKW"], ["Do 07:50 2 uKW"])
    assert result == [
        "Mo 08:00 2 gKW",
        "Mo 11:30 1 uKW",
        "ab 02-03-26 Do 07:50 2 uKW",
        "ab 14-03-26 Mo 08:00 2 gKW",
        "ab 14-03-26 Mo 11:30 1 uKW",
    ]
