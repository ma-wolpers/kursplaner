from __future__ import annotations

from datetime import date

from kursplaner.core.domain.school_wide_cancellation import SchoolWideCancellationEntry, claims_for_grade


def _entry(entry_id: str, *, grades: frozenset[int], date_from: date, date_to: date) -> SchoolWideCancellationEntry:
    return SchoolWideCancellationEntry(
        entry_id=entry_id,
        reason=f"Grund-{entry_id}",
        date_from=date_from,
        date_to=date_to,
        grade_levels=grades,
        created_at="",
    )


def test_no_matching_grade_yields_no_claims():
    entries = [_entry("a", grades=frozenset({5}), date_from=date(2026, 1, 6), date_to=date(2026, 1, 6))]
    result = claims_for_grade(entries, grade_level=7, date_from=date(2026, 1, 1), date_to=date(2026, 1, 10))
    assert result == {}


def test_date_outside_entry_range_is_not_claimed():
    entries = [_entry("a", grades=frozenset({7}), date_from=date(2026, 1, 6), date_to=date(2026, 1, 6))]
    result = claims_for_grade(entries, grade_level=7, date_from=date(2026, 2, 1), date_to=date(2026, 2, 10))
    assert result == {}


def test_matching_grade_and_date_is_claimed():
    entries = [_entry("a", grades=frozenset({7}), date_from=date(2026, 1, 6), date_to=date(2026, 1, 8))]
    result = claims_for_grade(entries, grade_level=7, date_from=date(2026, 1, 1), date_to=date(2026, 1, 10))
    assert set(result.keys()) == {date(2026, 1, 6), date(2026, 1, 7), date(2026, 1, 8)}
    assert result[date(2026, 1, 6)].entry_id == "a"


def test_earlier_entry_in_list_order_wins_on_overlap():
    """Zwei aktive Entries, gleiche Stufe, gleiches Datum -> der zuerst erstellte (weiter vorne stehende) gewinnt."""
    older = _entry("older", grades=frozenset({7}), date_from=date(2026, 1, 6), date_to=date(2026, 1, 6))
    newer = _entry("newer", grades=frozenset({7}), date_from=date(2026, 1, 6), date_to=date(2026, 1, 6))

    result = claims_for_grade(
        [older, newer], grade_level=7, date_from=date(2026, 1, 6), date_to=date(2026, 1, 6)
    )
    assert result[date(2026, 1, 6)].entry_id == "older"

    result_reversed = claims_for_grade(
        [newer, older], grade_level=7, date_from=date(2026, 1, 6), date_to=date(2026, 1, 6)
    )
    assert result_reversed[date(2026, 1, 6)].entry_id == "newer"
