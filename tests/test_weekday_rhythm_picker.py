"""Rohzustand des `WeekdayRhythmPicker` (Checkbox, Wochenmodus, A/B-Zeilen).

Nutzt einen echten Tk-Parent (`tk_root`-Fixture, off-screen) in einem
eigenen `Toplevel`, damit kein Geometrie-Manager-Konflikt mit anderen
Testdateien entsteht; es werden keine sichtbaren Fenster geoeffnet.
"""

from __future__ import annotations

import tkinter as tk
from datetime import date

import pytest

from kursplaner.adapters.gui.weekday_rhythm_picker import (
    MODE_AB,
    MODE_EVEN,
    MODE_EVERY_WEEK,
    MODE_ODD,
    WeekdayRhythmPicker,
    mode_for_parities,
)
from kursplaner.core.domain.course_rhythm import format_rhythm, parse_rhythm
from kursplaner.core.domain.validators import normalize_day_rhythm

MONDAY = 0


def _picker(tk_root) -> WeekdayRhythmPicker:
    """Baut den Picker in einem off-screen positionierten `Toplevel`."""
    toplevel = tk.Toplevel(tk_root)
    toplevel.geometry("+3000+3000")
    picker = WeekdayRhythmPicker(toplevel)
    picker.pack()
    return picker


def _set_day(picker, weekday, *, enabled, mode, first=("08:00", "2"), second=("11:30", "1")):
    """Setzt Checkbox, Modus und beide Eingabezeilen eines Tages direkt ueber die Variablen."""
    day = picker._days[weekday]
    day.enabled_var.set(enabled)
    day.mode_var.set(mode)
    for line, (start, hours) in zip(day.lines, (first, second)):
        line.start_var.set(start)
        line.hours_var.set(hours)
    picker._refresh(weekday)


def test_disabled_day_yields_no_raw_entry_regardless_of_fields(tk_root):
    picker = _picker(tk_root)
    _set_day(picker, MONDAY, enabled=False, mode=MODE_AB)
    assert picker.collect_raw() == {}


@pytest.mark.parametrize(
    ("mode", "expected_keys"),
    [(MODE_EVERY_WEEK, [(0, None)]), (MODE_EVEN, [(0, 0)]), (MODE_ODD, [(0, 1)])],
)
def test_single_modes_yield_one_key_from_first_line(tk_root, mode, expected_keys):
    picker = _picker(tk_root)
    _set_day(picker, MONDAY, enabled=True, mode=mode)
    raw = picker.collect_raw()
    assert list(raw) == expected_keys
    assert raw[expected_keys[0]] == ("08:00", "2")


def test_hidden_second_line_is_never_read(tk_root):
    picker = _picker(tk_root)
    _set_day(picker, MONDAY, enabled=True, mode=MODE_EVEN, second=("13:00", "4"))
    assert ("13:00", "4") not in picker.collect_raw().values()


def test_ab_mode_yields_two_independent_keys(tk_root):
    picker = _picker(tk_root)
    _set_day(picker, MONDAY, enabled=True, mode=MODE_AB)
    assert picker.collect_raw() == {(0, 0): ("08:00", "2"), (0, 1): ("11:30", "1")}


@pytest.mark.parametrize(
    "rhythm_lines",
    [
        ["Mo 08:00 2"],
        ["Mo 08:00 2 gKW"],
        ["Mo 08:00 2 uKW"],
        ["Mo 08:00 2 gKW", "Mo 11:30 1 uKW"],
        ["Di 09:00 1"],  # Montag aus
    ],
)
def test_set_from_rhythm_roundtrip(tk_root, rhythm_lines):
    picker = _picker(tk_root)
    picker.set_from_rhythm(parse_rhythm(rhythm_lines))
    assert format_rhythm(normalize_day_rhythm(picker.collect_raw())) == rhythm_lines


def test_set_from_rhythm_uses_segment_valid_on_reference_date(tk_root):
    picker = _picker(tk_root)
    rhythm = parse_rhythm(["Mo 08:00 2", "Do 07:50 2", "ab 20-04-26 Di 10:00 2 uKW"])
    picker.set_from_rhythm(rhythm, on=date(2026, 5, 1))
    assert picker.collect_raw() == {(1, 1): ("10:00", "2")}


def test_mode_for_parities():
    assert mode_for_parities({None}) == MODE_EVERY_WEEK
    assert mode_for_parities({0, 1}) == MODE_AB
    with pytest.raises(ValueError):
        mode_for_parities({None, 0})
