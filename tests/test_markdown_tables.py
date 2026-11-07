"""Markdown-Tabellenregel: Zerlegen/Maskieren invers, Trennzeile, Blöcke; Nutzer lesen, was sie schreiben."""

from __future__ import annotations

from pathlib import Path

import pytest

from kursplaner.core.domain.markdown_tables import (
    escape_table_cell,
    is_separator_row,
    split_table_row,
    table_blocks,
)


@pytest.mark.parametrize(
    ("line", "cells"),
    [
        ("| a | b |", ["a", "b"]),
        ("| a | b", ["a", "b"]),
        ("| a |  | c |", ["a", "", "c"]),
        ("| [[a\\|b]] | x |", ["[[a|b]]", "x"]),
        ("| Pfad\\_mit | y |", ["Pfad\\_mit", "y"]),
        ("kein | Tabellenzeile", []),
    ],
)
def test_split_table_row(line, cells):
    assert split_table_row(line) == cells


@pytest.mark.parametrize("text", ["A | B", "[[a|b]]", "ohne", "Backslash \\_ bleibt", ""])
def test_escape_and_split_are_inverse(text):
    assert split_table_row(f"| {escape_table_cell(text)} | x |") == [text, "x"]


def test_separator_rows_and_blocks():
    lines = ["Text", "| A | B |", "| --- | :-: |", "| 1 | 2 |", "", "| einzeln |", "Ende"]
    assert is_separator_row(lines[2]) and not is_separator_row(lines[1])
    assert table_blocks(lines) == [(1, 3)]


def test_plan_table_round_trip_keeps_pipes_in_cells(tmp_path: Path):
    from kursplaner.infrastructure.repositories.plan_table_markdown_io import load_last_plan_table, save_plan_table

    path = tmp_path / "Kurs.md"
    path.write_text(
        '---\nLerngruppe: "[[gk]]"\nKursfach: "Mathematik"\nStufe: 7\nRhythmus:\n  - "Mo 08:00 2"\n---\n\n'
        "| Datum | Inhalt | Thema/Ausfall |\n| --- | --- | --- |\n| 02-11-26 | [[a\\|Alias]] | x |\n",
        encoding="utf-8",
    )
    before = path.read_text(encoding="utf-8")
    table = load_last_plan_table(path)
    assert table.rows[0][1] == "[[a|Alias]]"
    save_plan_table(table)
    assert path.read_text(encoding="utf-8") == before


def test_expected_horizon_reader_reads_back_a_goal_with_a_pipe(tmp_path: Path):
    from kursplaner.infrastructure.export.expected_horizon_markdown_reader import ExpectedHorizonMarkdownReader

    goal = escape_table_cell("... A | B vergleichen")
    path = tmp_path / "kh.md"
    path.write_text(
        "| Datum | Die SuS können ... | AFB | Aufg | Pkte |\n| --- | --- | --- | --- | --- |\n"
        f"| 02.11. | {goal} | II | 3 | 4 |\n",
        encoding="utf-8",
    )
    [row] = ExpectedHorizonMarkdownReader().read_existing_rows(path)
    assert (row.ich_kann, row.afb, row.aufg, row.pkte) == ("... A | B vergleichen", "II", "3", "4")
