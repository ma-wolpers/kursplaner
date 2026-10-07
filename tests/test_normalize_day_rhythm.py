"""`validators.normalize_day_rhythm` mit Wochenparitaet (`(weekday, parity)`-Schluessel)."""

from __future__ import annotations

from datetime import date

import pytest

from kursplaner.core.domain.course_rhythm import format_rhythm
from kursplaner.core.domain.validators import ValidationError, normalize_day_rhythm


def test_parity_keys_become_gkw_ukw_entries_sorted():
    rhythm = normalize_day_rhythm(
        {(3, 1): ("11:30", "1"), (3, 0): ("07:50", "2"), (0, None): ("08:00", "2")},
    )
    assert format_rhythm(rhythm) == ["Mo 08:00 2", "Do 07:50 2 gKW", "Do 11:30 1 uKW"]


def test_valid_from_is_applied_to_all_entries():
    rhythm = normalize_day_rhythm({(1, 1): ("10:00", "2")}, valid_from=date(2026, 4, 20))
    assert format_rhythm(rhythm) == ["ab 20-04-26 Di 10:00 2 uKW"]


def test_overlapping_week_modes_raise_validation_error():
    with pytest.raises(ValidationError, match="mehrfach"):
        normalize_day_rhythm({(0, None): ("08:00", "2"), (0, 0): ("10:00", "1")})


def test_empty_input_still_requires_one_day():
    with pytest.raises(ValidationError):
        normalize_day_rhythm({(0, 0): ("", "")})


def test_invalid_hours_and_start_time_keep_messages():
    with pytest.raises(ValidationError, match="Stundenzahl"):
        normalize_day_rhythm({(0, None): ("08:00", "5")})
    with pytest.raises(ValidationError, match="HH:MM"):
        normalize_day_rhythm({(0, 0): ("8 Uhr", "2")})
