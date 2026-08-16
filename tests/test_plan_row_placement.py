from __future__ import annotations

from datetime import date

from kursplaner.core.domain.plan_row_placement import (
    find_stattfindend_rows_in_range,
    plan_gap_placement,
    strip_empty_dateless_rows,
)

_HEADERS = ["Datum", "Inhalt", "Thema/Ausfall"]


# ---------------------------------------------------------------------------
# find_stattfindend_rows_in_range
# ---------------------------------------------------------------------------


def test_finds_dated_stattfindend_rows_in_range():
    rows = [
        ["05-01-26", "[[a]]", ""],
        ["06-01-26", "[[b]]", ""],
        ["07-01-26", "[[c]]", ""],
    ]
    result = find_stattfindend_rows_in_range(_HEADERS, rows, date(2026, 1, 6), date(2026, 1, 7))
    assert result == [1, 2]


def test_excludes_already_cancelled_rows():
    rows = [["06-01-26", "", "X Ausfall"]]
    result = find_stattfindend_rows_in_range(_HEADERS, rows, date(2026, 1, 6), date(2026, 1, 6))
    assert result == []


def test_excludes_ferien_rows():
    rows = [["06-01-26", "", "X Ferien X"]]
    result = find_stattfindend_rows_in_range(_HEADERS, rows, date(2026, 1, 6), date(2026, 1, 6))
    assert result == []


def test_excludes_dateless_rows():
    rows = [["", "[[a]]", ""]]
    result = find_stattfindend_rows_in_range(_HEADERS, rows, date(2026, 1, 1), date(2026, 12, 31))
    assert result == []


def test_missing_datum_column_returns_empty():
    result = find_stattfindend_rows_in_range(["Inhalt"], [["x"]], date(2026, 1, 1), date(2026, 1, 2))
    assert result == []


# ---------------------------------------------------------------------------
# plan_gap_placement
# ---------------------------------------------------------------------------


def test_gap_placement_finds_enough_gaps():
    available = {2, 4}
    plan = plan_gap_placement(
        is_available_gap=lambda i: i in available, slot_count=6, start_after_index=0, needed_count=2
    )
    assert plan.gap_indices == (2, 4)
    assert plan.append_count == 0


def test_gap_placement_reports_append_count_when_not_enough_gaps():
    available = {2}
    plan = plan_gap_placement(
        is_available_gap=lambda i: i in available, slot_count=6, start_after_index=0, needed_count=3
    )
    assert plan.gap_indices == (2,)
    assert plan.append_count == 2


def test_gap_placement_zero_gaps():
    plan = plan_gap_placement(is_available_gap=lambda i: False, slot_count=5, start_after_index=0, needed_count=2)
    assert plan.gap_indices == ()
    assert plan.append_count == 2


def test_gap_placement_respects_start_after_index():
    plan = plan_gap_placement(is_available_gap=lambda i: True, slot_count=5, start_after_index=3, needed_count=2)
    assert plan.gap_indices == (3, 4)


def test_gap_placement_start_after_index_at_end():
    plan = plan_gap_placement(is_available_gap=lambda i: True, slot_count=3, start_after_index=3, needed_count=1)
    assert plan.gap_indices == ()
    assert plan.append_count == 1


# ---------------------------------------------------------------------------
# strip_empty_dateless_rows
# ---------------------------------------------------------------------------


def test_strip_removes_only_empty_dateless_rows():
    rows = [
        ["06-01-26", "", ""],  # dated, empty -> kept (normal free slot)
        ["", "[[a]]", ""],  # dateless with content -> kept
        ["", "", ""],  # dateless, empty -> removed
        ["", "", "X Grund"],  # dateless, has thema -> kept
    ]
    result = strip_empty_dateless_rows(_HEADERS, rows)
    assert len(result) == 3
    assert result[0][0] == "06-01-26"
    assert result[1][1] == "[[a]]"
    assert result[2][2] == "X Grund"


def test_strip_removes_preexisting_empty_dateless_row_regardless_of_origin():
    rows = [["", "", ""]]
    assert strip_empty_dateless_rows(_HEADERS, rows) == []


def test_strip_missing_datum_column_returns_rows_unchanged():
    rows = [["a", "b"]]
    assert strip_empty_dateless_rows(["Inhalt", "Thema/Ausfall"], rows) == rows
