"""Tests für den verlustfreien Listenzellen-Vertrag (`list_cell_text`)."""

import pytest

from kursplaner.core.domain.lesson_yaml_policy import canonicalize_lesson_yaml
from kursplaner.core.domain.list_cell_text import (
    ListFieldViolationError,
    format_list_cell,
    list_entry_violation,
    list_field_violations,
    parse_list_cell,
    raise_on_violation,
)

_VALID_ENTRY_SETS = [
    ["Modellieren"],
    ["Modellieren", "Argumentieren"],
    ["[[Material/AB Brüche.pdf|AB 1]]", "Tafelbild"],
    ["a -- b", "-", "x-y"],
    ["2. Binomische Formel", "[1] Aufgabe", "1) Einstieg"],
    ["Größen ändern ß", "a  b mit doppeltem Leerzeichen"],
    ["A | B ist kein Trenner"],
    ["---x", "x---"],
]


@pytest.mark.parametrize("entries", _VALID_ENTRY_SETS)
def test_roundtrip_is_lossless_for_valid_entries(entries):
    assert parse_list_cell(format_list_cell(entries)) == entries


def test_format_uses_double_dash_separator_lines():
    assert format_list_cell(["K1", "K2"]) == "K1\n--\nK2"
    assert format_list_cell([]) == ""


@pytest.mark.parametrize("separator", ["--", "---", "-----", "  --  ", "\t---"])
def test_lines_of_two_or_more_dashes_separate(separator):
    assert parse_list_cell(f"K1\n{separator}\nK2") == ["K1", "K2"]


def test_semicolon_is_quick_separator():
    assert parse_list_cell("K1; K2;K3") == ["K1", "K2", "K3"]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("K1\n-\nK2", ["K1 - K2"]),
        ("K1\n\nK2", ["K1 K2"]),
        ("[[a|b]] | c", ["[[a|b]] | c"]),
    ],
)
def test_single_dash_blank_line_and_pipe_do_not_separate(text, expected):
    assert parse_list_cell(text) == expected


def test_crlf_input_is_normalized():
    assert parse_list_cell("K1\r\n--\r\nK2") == ["K1", "K2"]


def test_parse_drops_empty_chunks_and_trims_edges_only():
    assert parse_list_cell("  K1  \n--\n\n--\n;  ;\nK2") == ["K1", "K2"]


def test_parse_output_always_satisfies_invariant():
    text = "  a ;b\n--\n\n-\n c d \n---\n;;\n--\n"
    for entry in parse_list_cell(text):
        assert list_entry_violation(entry) is None


@pytest.mark.parametrize(
    "entry, fragment",
    [
        ("", "leer"),
        ("   ", "Leerzeichen"),
        (" x", "Rand"),
        ("x ", "Rand"),
        ("a\nb", "Zeilenumbruch"),
        ("a\rb", "Zeilenumbruch"),
        ("K1; K2", "';'"),
        ("--", "Strichen"),
        ("----", "Strichen"),
        (42, "kein Text"),
        (None, "kein Text"),
    ],
)
def test_entry_violations_explain_the_cause(entry, fragment):
    reason = list_entry_violation(entry)
    assert reason is not None
    assert fragment in reason


@pytest.mark.parametrize("entry", ["", "a;b", "a\nb", "--", " x"])
def test_format_refuses_entries_that_would_not_roundtrip(entry):
    with pytest.raises(ValueError):
        format_list_cell(["ok", entry])


def test_field_violations_reports_all_in_order():
    violations = list_field_violations(["ok", "a;b", "", "gut", " x"])
    assert [entry for entry, _ in violations] == ["a;b", "", " x"]


def test_field_violations_accepts_empty_forms():
    assert list_field_violations(None) == []
    assert list_field_violations("") == []
    assert list_field_violations([]) == []


def test_field_violations_rejects_non_list_shapes():
    violations = list_field_violations({"a": 1})
    assert len(violations) == 1
    assert "keine Liste" in violations[0][1]


def test_raise_on_violation_reports_first_violation_with_context():
    with pytest.raises(ListFieldViolationError) as info:
        raise_on_violation("Material", ["ok", "a;b", ""], source_label="x/Stunde.md")
    message = str(info.value)
    assert "x/Stunde.md" in message
    assert "Material" in message
    assert "'a;b'" in message
    assert info.value.reason == list_field_violations(["a;b"])[0][1]


def test_raise_on_violation_returns_entries_unchanged():
    assert raise_on_violation("Material", ["A", "B"]) == ["A", "B"]
    assert raise_on_violation("Material", "einzeln") == ["einzeln"]
    assert raise_on_violation("Material", "") == []


@pytest.mark.parametrize("bad", ["", "  ", " x", "x "])
def test_lesson_load_rejects_instead_of_trimming_or_dropping(bad):
    """Ladegrenze: erst prüfen, dann übernehmen — nichts verschwindet still."""
    data = {"Stundentyp": "Unterricht", "Dauer": "2", "Stundenthema": "X", "Material": ["ok", bad]}
    with pytest.raises(ListFieldViolationError) as info:
        canonicalize_lesson_yaml(data, source_label="Stunde.md")
    assert "Stunde.md" in str(info.value)
    assert info.value.field == "Material"
    assert info.value.entry == bad


def test_lesson_load_rejects_non_string_entry():
    data = {"Stundentyp": "Unterricht", "Dauer": "2", "Stundenthema": "X", "Kompetenzen": ["ok", 7]}
    with pytest.raises(ListFieldViolationError):
        canonicalize_lesson_yaml(data)


def test_lesson_load_keeps_valid_entries_verbatim():
    data = {"Stundentyp": "Unterricht", "Dauer": "2", "Stundenthema": "X", "Material": ["[[AB.pdf|AB 1]]", "a  b"]}
    assert canonicalize_lesson_yaml(data)["Material"] == ["[[AB.pdf|AB 1]]", "a  b"]
