"""Dateiformat der Sequenzleiter: Rundweg, strikte Fehler, Netz-Links (synthetische Daten)."""

from __future__ import annotations

import pytest

from kursplaner.core.domain.sequence_ladder import LadderBlock, LadderRung, SequenceLadder
from kursplaner.core.domain.sequence_ladder_codec import (
    LadderFormatError,
    format_ladder_section,
    network_block_text,
    parse_ladder_section,
)


def _ladder() -> SequenceLadder:
    return SequenceLadder(
        (
            LadderRung(
                (LadderBlock("Brüche deuten"), LadderBlock("Zahlenstrahl", "Mat-RF-14")),
                (LadderBlock("Darstellen", "Mat-DA-2"),),
                ("Pizza-Aufgabe", "", "Plakat"),
            ),
            LadderRung(),
            LadderRung(prozess=(LadderBlock("eigener Prozess-Baustein mit [[Link]] drin"),)),
        )
    )


def test_roundtrip_keeps_order_ideas_and_empty_middle_rungs():
    lines = format_ladder_section(_ladder())
    assert lines[:3] == ["- Sprosse 1", "  - Inhalt: Brüche deuten", "  - Inhalt: [[Mat-RF-14|Zahlenstrahl]]"]
    assert "  - Idee:" in lines
    assert parse_ladder_section("\n".join(lines)) == _ladder()


def test_empty_ladder_formats_to_nothing_and_trailing_empty_rungs_are_dropped():
    assert format_ladder_section(SequenceLadder((LadderRung(), LadderRung()))) == []
    assert parse_ladder_section("") == SequenceLadder()


def test_title_with_pipe_survives_the_roundtrip():
    text = network_block_text("Mat-1", "a|b")
    ladder = SequenceLadder((LadderRung((LadderBlock(text, "Mat-1"),)),))
    assert parse_ladder_section("\n".join(format_ladder_section(ladder))) == ladder


def test_network_text_normalizes_like_the_file_does():
    assert network_block_text("Mat-1", "Titel [mit] Klammern") == "Titel mit Klammern"
    assert network_block_text("Mat-1", "") == "Mat-1"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("- Sprosse 2", "Sprosse 1"),
        ("  - Inhalt: x", "vor der ersten Sprosse"),
        ("- Sprosse 1\n  - Methode: x", "Unbekannte Spalte"),
        ("- Sprosse 1\nirgendwas", "Unbekannte Zeile"),
        ("- Sprosse 1\n  - Inhalt: [[a]] und mehr", "genau ein Wiki-Link"),
        ("- Sprosse 1\n  - Inhalt:", "ohne Beschreibung"),
    ],
)
def test_parser_is_strict_with_line_numbers(body, message):
    with pytest.raises(LadderFormatError, match=message) as info:
        parse_ladder_section(body)
    assert info.value.line_no >= 1
