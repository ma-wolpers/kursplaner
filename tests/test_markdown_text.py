"""Tests für die Markdown-Ausgabe von Benutzerinhalten (`markdown_text`)."""

import html

import pytest

from kursplaner.infrastructure.export.markdown_text import (
    LINE_BREAK,
    markdown_inline_text,
    markdown_table_cell,
    markdown_table_lines,
)


def _gfm_split_row(row_line: str) -> list[str]:
    """Test-Orakel: zerlegt eine GFM-Tabellenzeile nur an *unmaskierten* ``|``.

    ``\\`` maskiert das Folgezeichen (bleibt im Zellinhalt erhalten); der
    projekteigene ``plan_table_markdown_io._split_row`` taugt hier nicht, weil
    er an jedem ``|`` teilt, auch an ``\\|``.
    """
    body = row_line.strip()
    assert body.startswith("|") and body.endswith("|")
    body = body[1:-1]
    cells: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(body):
        char = body[index]
        if char == "\\" and index + 1 < len(body):
            current.append(body[index : index + 2])
            index += 2
            continue
        if char == "|":
            cells.append("".join(current))
            current = []
        else:
            current.append(char)
        index += 1
    cells.append("".join(current))
    return [cell.strip() for cell in cells]


def _unescape_line(text: str) -> str:
    """Kehrt Backslash-Escapes und HTML-Entities einer Zellzeile um (Test-Orakel)."""
    result: list[str] = []
    index = 0
    while index < len(text):
        if text[index] == "\\" and index + 1 < len(text):
            result.append(text[index + 1])
            index += 2
            continue
        result.append(text[index])
        index += 1
    return html.unescape("".join(result))


TRICKY_LINES = [
    "\\",
    "|",
    "a\\|b",
    "\\\\|",
    "x\\\\\\|y",
    "a < b > c & d",
    "&amp; bereits Entity",
    "[[Material/AB.pdf|AB 1]]",
    "<br>",
    "Umlaute äöüß → ≤ α",
]


@pytest.mark.parametrize("line", TRICKY_LINES)
def test_table_cell_roundtrips_through_gfm_oracle(line):
    row = markdown_table_lines(["A", "B", "C"], [(("vorher",), (line, "zweite Zeile"), ("nachher",))])[2]

    cells = _gfm_split_row(row)

    assert len(cells) == 3  # Struktur bleibt intakt, kein Pipe zerreißt die Zeile
    lines = cells[1].split(LINE_BREAK)
    assert [_unescape_line(part) for part in lines] == [line, "zweite Zeile"]


def test_br_separator_is_never_escaped():
    cell = markdown_table_cell(("a & <b>", "c"))

    assert cell == "a &amp; &lt;b&gt;<br>c"
    assert "&lt;br&gt;" not in cell


def test_user_br_text_is_escaped_but_separator_is_not():
    assert markdown_table_cell(("<br>", "x")) == "&lt;br&gt;<br>x"


def test_backslash_is_doubled_before_pipe_escape():
    assert markdown_table_cell(("a\\|b",)) == "a\\\\\\|b"
    assert markdown_table_cell(("\\\\|",)) == "\\\\\\\\\\|"


def test_wiki_alias_becomes_obsidian_table_form():
    assert markdown_table_cell(("[[ziel|alias]]",)) == "[[ziel\\|alias]]"


def test_inline_text_does_not_escape_pipe():
    assert markdown_inline_text("a | b & c") == "a | b &amp; c"


def test_empty_cell_and_empty_rows():
    assert markdown_table_cell(()) == ""
    assert markdown_table_lines(["X"], []) == ["| X |", "| --- |"]


@pytest.mark.parametrize("bad", ["text", ["a"], ("a", 1)])
def test_non_tuple_cells_are_rejected(bad):
    """Ein String ist selbst eine Sequenz und würde sonst zeichenweise umgebrochen."""
    with pytest.raises(TypeError):
        markdown_table_cell(bad)
