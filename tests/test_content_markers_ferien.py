from __future__ import annotations

from kursplaner.core.domain.content_markers import (
    build_ausfall_marker,
    build_ferien_marker,
    classify_row_marker,
    is_ausfall_marker,
    is_ferien_marker,
    marker_reason_text,
    resolve_cancel_state,
    resolve_row_cancel_state,
    resolve_row_ferien_state,
)

_HEADERS = ["Datum", "Inhalt", "Thema/Ausfall"]


def test_is_ferien_marker_true_for_trailing_x():
    assert is_ferien_marker("X Sommerferien X") is True


def test_is_ferien_marker_false_for_word_ending_in_x():
    """Ein Grund, der zufaellig auf 'X'-aehnliches Wort endet, ist keine Ferien-Markierung."""
    assert is_ferien_marker("X XLAB") is False


def test_is_ferien_marker_true_without_reason():
    assert is_ferien_marker("X X") is True


def test_is_ferien_marker_false_for_plain_ausfall():
    assert is_ferien_marker("X Lehrer krank") is False


def test_is_ferien_marker_false_for_normal_content():
    assert is_ferien_marker("[[li2 Kodierung]]") is False


def test_build_ferien_marker_default_reason():
    assert build_ferien_marker("") == "X Ohne Angabe X"


def test_build_ferien_marker_with_reason():
    assert build_ferien_marker("Sommerferien") == "X Sommerferien X"


def test_build_ausfall_marker_strips_trailing_x_from_previous_ferien_marker():
    """Ein zuvor als Ferien markierter Grund darf beim Umwandeln in Ausfall kein Trailing-X behalten."""
    assert build_ausfall_marker("X Sommerferien X") == "X Sommerferien"


def test_marker_reason_text_strips_leading_and_trailing_marker():
    assert marker_reason_text("X Sommerferien X") == "Sommerferien"
    assert marker_reason_text("X Lehrer krank") == "Lehrer krank"
    assert marker_reason_text("") == ""


def test_resolve_row_cancel_state_true_for_ferien_and_ausfall():
    assert resolve_row_cancel_state(_HEADERS, ["05-01-26", "", "X Sommerferien X"]) is True
    assert resolve_row_cancel_state(_HEADERS, ["05-01-26", "", "X Lehrer krank"]) is True
    assert resolve_row_cancel_state(_HEADERS, ["05-01-26", "[[abc]]", ""]) is False


def test_resolve_row_ferien_state_distinguishes_from_manual_ausfall():
    assert resolve_row_ferien_state(_HEADERS, ["05-01-26", "", "X Sommerferien X"]) is True
    assert resolve_row_ferien_state(_HEADERS, ["05-01-26", "", "X Lehrer krank"]) is False


def test_classify_row_marker():
    assert classify_row_marker(_HEADERS, ["05-01-26", "", "X Sommerferien X"]) == "ferien"
    assert classify_row_marker(_HEADERS, ["05-01-26", "", "X Lehrer krank"]) == "ausfall"
    assert classify_row_marker(_HEADERS, ["05-01-26", "[[abc]]", ""]) == "none"


def test_resolve_cancel_state_yaml_override_without_text_marker():
    """Eine Zeile ohne Text-Marker gilt trotzdem als Ausfall, wenn die YAML Stundentyp=Ausfall traegt."""
    row = ["05-01-26", "[[abc]]", ""]
    assert resolve_cancel_state(_HEADERS, row, {"Stundentyp": "Ausfall"}) is True
    assert resolve_cancel_state(_HEADERS, row, {"Stundentyp": "Unterricht"}) is False
    assert resolve_cancel_state(_HEADERS, row, None) is False


def test_resolve_cancel_state_text_marker_alone_is_sufficient():
    row = ["05-01-26", "", "X Lehrer krank"]
    assert resolve_cancel_state(_HEADERS, row, None) is True


def test_is_ausfall_marker_covers_both_ferien_and_manual_ausfall():
    assert is_ausfall_marker("X Sommerferien X") is True
    assert is_ausfall_marker("X Lehrer krank") is True
    assert is_ausfall_marker("[[abc]]") is False
