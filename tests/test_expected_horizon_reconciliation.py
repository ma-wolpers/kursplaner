"""Tests für Reconciliation, Reader und Section-Rendering des Kompetenzhorizonts."""

from __future__ import annotations

import os
from pathlib import Path

from kursplaner.core.domain.expected_horizon import ExpectedHorizonLine, ExpectedHorizonSection, GoalKind
from kursplaner.core.domain.expected_horizon_reconciliation import (
    REMOVED_SECTION_TITLE,
    ExistingHorizonRow,
    reconcile,
)
from kursplaner.core.usecases.export_expected_horizon_usecase import ExpectedHorizonDocument
from kursplaner.infrastructure.export.expected_horizon_markdown_reader import ExpectedHorizonMarkdownReader
from kursplaner.infrastructure.export.expected_horizon_markdown_renderer import ExpectedHorizonMarkdownRenderer

_HEADER = "| Datum | Die SuS können ... | AFB | Aufg | Pkte |"
_SEP = "| --- | --- | --- | --- | --- |"


def _goal(datum: str, text: str, kind: GoalKind = GoalKind.STUNDENZIEL) -> ExpectedHorizonLine:
    return ExpectedHorizonLine(datum, text, kind)


def _old(datum: str, text: str, afb: str = "", section: str | None = None) -> ExistingHorizonRow:
    return ExistingHorizonRow(section=section, datum=datum, ich_kann=text, afb=afb, aufg="", pkte="")


def _topics(horizon) -> list[str]:
    return [section.oberthema for section in horizon.sections]


def _rows(horizon, topic: str) -> list[tuple[str, str, bool]]:
    section = next(section for section in horizon.sections if section.oberthema == topic)
    return [(row.ich_kann, row.afb, row.removed) for row in section.rows]


def test_scores_are_carried_across_sections():
    sections = [
        ExpectedHorizonSection("A", (_goal("01.09.26", "... a"),)),
        ExpectedHorizonSection("B", (_goal("03.09.26", "... b"),)),
    ]
    existing = [
        _old("**01.09.26**", "**... a**", "I", section="A"),
        _old("**03.09.26**", "**... b**", "II", section="B"),
    ]

    horizon = reconcile(sections, existing)

    assert _topics(horizon) == ["A", "B"]
    assert _rows(horizon, "A") == [("... a", "I", False)]
    assert _rows(horizon, "B") == [("... b", "II", False)]


def test_legacy_file_without_headings_merges_into_multiple_sections():
    sections = [
        ExpectedHorizonSection("A", (_goal("01.09.26", "... a"),)),
        ExpectedHorizonSection("B", (_goal("03.09.26", "... b"),)),
    ]
    existing = [_old("**01.09.26**", "**... a**", "I")]

    horizon = reconcile(sections, existing)

    assert _rows(horizon, "A") == [("... a", "I", False)]
    assert _rows(horizon, "B") == [("... b", "", False)]


def test_new_lesson_in_second_topic_is_anchored_before_next_matched_row():
    sections = [
        ExpectedHorizonSection("A", (_goal("01.09.26", "... a"),)),
        ExpectedHorizonSection("B", (_goal("03.09.26", "... b neu"), _goal("05.09.26", "... b alt"))),
    ]
    existing = [
        _old("**01.09.26**", "**... a**", "I", section="A"),
        _old("**05.09.26**", "**... b alt**", "III", section="B"),
    ]

    horizon = reconcile(sections, existing)

    assert _rows(horizon, "B") == [("... b neu", "", False), ("... b alt", "III", False)]


def test_removed_graded_goal_stays_in_its_section_struck_through():
    sections = [
        ExpectedHorizonSection("A", (_goal("01.09.26", "... a"),)),
        ExpectedHorizonSection("B", (_goal("03.09.26", "... b"),)),
    ]
    existing = [
        _old("**01.09.26**", "**... a**", "I", section="A"),
        _old("**03.09.26**", "**... b**", "II", section="B"),
        _old("", "... entfallen in B", "I", section="B"),
    ]

    horizon = reconcile(sections, existing)

    assert _rows(horizon, "B") == [("... b", "II", False), ("... entfallen in B", "I", True)]


def test_deselected_topic_moves_graded_rows_to_removed_section():
    sections = [ExpectedHorizonSection("A", (_goal("01.09.26", "... a"),))]
    existing = [
        _old("**01.09.26**", "**... a**", "I", section="A"),
        _old("**03.09.26**", "**... b**", "II", section="B"),
        _old("", "... b unbewertet", section="B"),
    ]

    horizon = reconcile(sections, existing)

    assert _topics(horizon) == ["A", REMOVED_SECTION_TITLE]
    assert _rows(horizon, REMOVED_SECTION_TITLE) == [("... b", "II", True)]


def test_reader_parses_sections_and_legacy_tables(tmp_path: Path):
    multi = tmp_path / "multi.md"
    multi.write_text(
        "\n".join(
            ["# KH", "", "Sub", "", "### A", "", _HEADER, _SEP, "| 01.09.26 | ... a | I |  |  |", ""]
            + ["### B", "", _HEADER, _SEP, "| 03.09.26 | ... b | II | 1 | 2 |"]
        ),
        encoding="utf-8",
    )
    legacy = tmp_path / "legacy.md"
    legacy.write_text("\n".join(["# KH", "", _HEADER, _SEP, "| 01.09.26 | ... a | I |  |  |"]), encoding="utf-8")
    reader = ExpectedHorizonMarkdownReader()

    assert [(row.section, row.ich_kann, row.afb) for row in reader.read_existing_rows(multi)] == [
        ("A", "... a", "I"),
        ("B", "... b", "II"),
    ]
    assert [(row.section, row.ich_kann) for row in reader.read_existing_rows(legacy)] == [(None, "... a")]
    assert reader.read_existing_rows(tmp_path / "fehlt.md") == []


def _document(*sections: ExpectedHorizonSection) -> ExpectedHorizonDocument:
    return ExpectedHorizonDocument("Kompetenzhorizont: A, B", "Mathematik 11.1 2026/27 Hj. 1", "29.09.2026", sections)


def test_multi_section_markdown_has_headings_and_round_trips_through_reader(tmp_path: Path):
    output = tmp_path / "KH.md"
    document = _document(
        ExpectedHorizonSection("A", (_goal("01.09.26", "... a"),)),
        ExpectedHorizonSection("B", (_goal("03.09.26", "... b"),)),
    )

    ExpectedHorizonMarkdownRenderer().render(document, output)

    text = output.read_text(encoding="utf-8")
    assert "### A\n\n" + _HEADER in text
    assert "### B\n\n" + _HEADER in text
    rows = ExpectedHorizonMarkdownReader().read_existing_rows(output)
    assert [(row.section, row.ich_kann) for row in rows] == [("A", "**... a**"), ("B", "**... b**")]


_GOLDEN_MERGED = (
    "# Kompetenzhorizont: Algorithmen\n\nInformatik lila-5 2025/26 Hj. 2\n\n"
    "| Datum | Die SuS können ... | AFB | Aufg | Pkte |\n| --- | --- | --- | --- | --- |\n"
    "| **01.09.25** | **... Sortierverfahren vergleichen** | II | 1a | 2 |\n"
    "|  | ~~... Bubble Sort erklären~~ | I | 1b | 1 |\n"
    "|  | ... Neues Teilziel |  |  |  |\n"
    "|  | **kursiv\\|pipe** |  |  |  |\n"
    "| **03.09.25** | **... Zweite Stunde** | III | 2 | 4 |\n"
)


def test_single_topic_output_is_byte_identical_to_previous_renderer(tmp_path: Path):
    """Regression: Mit einem Thema bleibt die Datei byte-gleich zum Stand vor der Section-Umstellung
    (Referenz mit dem alten Renderer erzeugt: Merge, durchgestrichene Zeile, Kursiv, Pipe-Escape)."""
    output = tmp_path / "KH.md"
    output.write_text(
        "\n".join(
            [
                "# Kompetenzhorizont: Algorithmen",
                "",
                "Informatik lila-5 2025/26 Hj. 2",
                "",
                _HEADER,
                _SEP,
                "| **01.09.25** | **... Sortierverfahren vergleichen** | II | 1a | 2 |",
                "|  | ... Bubble Sort erklären | I | 1b | 1 |",
                "|  | ... Unbewertet weg |  |  |  |",
                "| **03.09.25** | **... Zweite Stunde** | III | 2 | 4 |",
            ]
        ),
        encoding="utf-8",
    )
    section = ExpectedHorizonSection(
        "Algorithmen",
        (
            _goal("01.09.25", "... Sortierverfahren vergleichen"),
            _goal("", "... Neues Teilziel", GoalKind.TEILZIEL),
            _goal("", "*kursiv|pipe*", GoalKind.SONDERZIEL),
            _goal("03.09.25", "... Zweite Stunde"),
        ),
    )
    document = ExpectedHorizonDocument(
        "Kompetenzhorizont: Algorithmen", "Informatik lila-5 2025/26 Hj. 2", "02.04.2026", (section,)
    )

    reconciled = reconcile(document.sections, ExpectedHorizonMarkdownReader().read_existing_rows(output))
    ExpectedHorizonMarkdownRenderer().render(document, output, reconciled=reconciled)

    # write_text übersetzt Zeilenenden plattformabhängig — genau wie der alte Renderer.
    assert output.read_bytes() == _GOLDEN_MERGED.replace("\n", os.linesep).encode("utf-8")
