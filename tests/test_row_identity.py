from __future__ import annotations

from kursplaner.core.domain.row_identity import (
    ResolutionStatus,
    extract_row_reference,
    resolve_move,
    resolve_source,
    resolve_target,
)
from kursplaner.core.domain.school_wide_cancellation import RowLocation, UnitMove, UnitReference

_HEADERS = ["Datum", "Inhalt", "Thema/Ausfall"]


# ---------------------------------------------------------------------------
# extract_row_reference
# ---------------------------------------------------------------------------


def test_extract_reference_link():
    ref = extract_row_reference(_HEADERS, ["06-01-26", "[[ab12cd]]", ""])
    assert ref == UnitReference(kind="link", value="ab12cd")


def test_extract_reference_raw_text():
    ref = extract_row_reference(_HEADERS, ["06-01-26", "Freitext", ""])
    assert ref == UnitReference(kind="raw_text", value="Freitext")


# ---------------------------------------------------------------------------
# resolve_source
# ---------------------------------------------------------------------------


def test_resolve_source_match():
    rows = [["06-01-26", "", "X Wandertag"]]
    result = resolve_source(_HEADERS, rows, RowLocation(date="06-01-26", position_in_date=0))
    assert result.status is ResolutionStatus.MATCH
    assert result.row_index == 0


def test_resolve_source_error_when_marker_missing():
    """Zeile wurde manuell wiederhergestellt (z. B. via Strg+B) - kein Ausfall-Marker mehr."""
    rows = [["06-01-26", "[[abc]]", ""]]
    result = resolve_source(_HEADERS, rows, RowLocation(date="06-01-26", position_in_date=0))
    assert result.status is ResolutionStatus.ERROR


def test_resolve_source_error_when_row_missing():
    rows = [["06-01-26", "", "X Wandertag"]]
    result = resolve_source(_HEADERS, rows, RowLocation(date="07-01-26", position_in_date=0))
    assert result.status is ResolutionStatus.ERROR


def test_resolve_source_error_when_position_out_of_range():
    """Zwei Zeilen mit gleichem Datum erwartet, aber nur eine vorhanden (z. B. geloescht)."""
    rows = [["06-01-26", "", "X Wandertag"]]
    result = resolve_source(_HEADERS, rows, RowLocation(date="06-01-26", position_in_date=1))
    assert result.status is ResolutionStatus.ERROR


def test_resolve_source_uses_position_for_duplicate_dates():
    rows = [
        ["06-01-26", "", "X Wandertag"],
        ["06-01-26", "", "X Wandertag"],
    ]
    result = resolve_source(_HEADERS, rows, RowLocation(date="06-01-26", position_in_date=1))
    assert result.status is ResolutionStatus.MATCH
    assert result.row_index == 1


# ---------------------------------------------------------------------------
# resolve_target
# ---------------------------------------------------------------------------


def test_resolve_target_none_is_always_match():
    result = resolve_target(_HEADERS, [], None, None)
    assert result.status is ResolutionStatus.MATCH
    assert result.row_index is None


def test_resolve_target_dated_match():
    rows = [["10-01-26", "[[abc]]", ""]]
    reference = UnitReference(kind="link", value="abc")
    result = resolve_target(_HEADERS, rows, RowLocation(date="10-01-26", position_in_date=0), reference)
    assert result.status is ResolutionStatus.MATCH
    assert result.row_index == 0


def test_resolve_target_dated_reference_changed_is_warning():
    """Reference geaendert (Zeile zeigt jetzt auf eine andere Datei) -> struktureller Konflikt."""
    rows = [["10-01-26", "[[different]]", ""]]
    reference = UnitReference(kind="link", value="abc")
    result = resolve_target(_HEADERS, rows, RowLocation(date="10-01-26", position_in_date=0), reference)
    assert result.status is ResolutionStatus.WARNING


def test_resolve_target_content_of_linked_file_may_change_without_conflict():
    """Aendert sich nur der Inhalt der verlinkten Datei (nicht die Referenz selbst), bleibt die Referenz identisch."""
    rows = [["10-01-26", "[[abc]]", ""]]
    reference = UnitReference(kind="link", value="abc")
    result = resolve_target(_HEADERS, rows, RowLocation(date="10-01-26", position_in_date=0), reference)
    assert result.status is ResolutionStatus.MATCH


def test_resolve_target_dateless_finds_unique_match():
    rows = [
        ["", "[[other]]", ""],
        ["", "[[abc]]", ""],
    ]
    reference = UnitReference(kind="link", value="abc")
    result = resolve_target(_HEADERS, rows, RowLocation(date=None, position_in_date=0), reference)
    assert result.status is ResolutionStatus.MATCH
    assert result.row_index == 1


def test_resolve_target_dateless_no_match_is_error():
    rows = [["", "[[other]]", ""]]
    reference = UnitReference(kind="link", value="abc")
    result = resolve_target(_HEADERS, rows, RowLocation(date=None, position_in_date=0), reference)
    assert result.status is ResolutionStatus.ERROR


def test_resolve_target_dateless_ambiguous_match_is_error():
    rows = [
        ["", "[[abc]]", ""],
        ["", "[[abc]]", ""],
    ]
    reference = UnitReference(kind="link", value="abc")
    result = resolve_target(_HEADERS, rows, RowLocation(date=None, position_in_date=0), reference)
    assert result.status is ResolutionStatus.ERROR


# ---------------------------------------------------------------------------
# resolve_move
# ---------------------------------------------------------------------------


def test_resolve_move_full_match():
    rows = [
        ["06-01-26", "", "X Wandertag"],
        ["10-01-26", "[[abc]]", ""],
    ]
    move = UnitMove(
        source=RowLocation(date="06-01-26", position_in_date=0),
        reference=UnitReference(kind="link", value="abc"),
        target=RowLocation(date="10-01-26", position_in_date=0),
    )
    result = resolve_move(_HEADERS, rows, move)
    assert result.status is ResolutionStatus.MATCH


def test_resolve_move_source_error_short_circuits():
    rows = [["10-01-26", "[[abc]]", ""]]
    move = UnitMove(
        source=RowLocation(date="06-01-26", position_in_date=0),
        reference=UnitReference(kind="link", value="abc"),
        target=RowLocation(date="10-01-26", position_in_date=0),
    )
    result = resolve_move(_HEADERS, rows, move)
    assert result.status is ResolutionStatus.ERROR


def test_resolve_move_without_content_needs_no_target():
    rows = [["06-01-26", "", "X Wandertag"]]
    move = UnitMove(source=RowLocation(date="06-01-26", position_in_date=0), reference=None, target=None)
    result = resolve_move(_HEADERS, rows, move)
    assert result.status is ResolutionStatus.MATCH
    assert result.target.row_index is None
