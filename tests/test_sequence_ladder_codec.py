"""Dateiformat der Leiter-Ablage: Rundweg, strikte Fehler, Netz-Links (synthetische Daten)."""

from __future__ import annotations

import pytest

from kursplaner.core.domain.sequence_ladder import LadderBlock, LadderRung, SequenceLadder
from kursplaner.core.domain.sequence_ladder_codec import (
    LadderFormatError,
    format_ablage_section,
    parse_ablage_section,
)
from kursplaner.core.domain.sequence_ladder_entries import network_block_text


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
    lines = format_ablage_section(_ladder())
    assert lines[:3] == ["- Ablage 1", "  - Inhalt: Brüche deuten", "  - Inhalt: [[Mat-RF-14|Zahlenstrahl]]"]
    assert "  - Idee:" in lines
    assert parse_ablage_section("\n".join(lines)) == _ladder()


def test_empty_ladder_formats_to_nothing_and_trailing_empty_rungs_are_dropped():
    assert format_ablage_section(SequenceLadder((LadderRung(), LadderRung()))) == []
    assert parse_ablage_section("") == SequenceLadder()


def test_title_with_pipe_survives_the_roundtrip():
    text = network_block_text("Mat-1", "a|b")
    ladder = SequenceLadder((LadderRung((LadderBlock(text, "Mat-1"),)),))
    assert parse_ablage_section("\n".join(format_ablage_section(ladder))) == ladder


def test_same_right_block_in_several_rungs_is_valid():
    ladder = parse_ablage_section("- Ablage 1\n  - Prozess: [[Mat-1|p]]\n- Ablage 2\n  - Prozess: [[Mat-1|p]]")
    assert [len(rung.prozess) for rung in ladder.rungs] == [1, 1]


def test_network_text_normalizes_like_the_file_does():
    assert network_block_text("Mat-1", "Titel [mit] Klammern") == "Titel mit Klammern"
    assert network_block_text("Mat-1", "") == "Mat-1"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("- Ablage 2", "Ablage 1"),
        ("  - Inhalt: x", "vor der ersten Ablage-Sprosse"),
        ("- Ablage 1\n  - Methode: x", "Unbekannte Spalte"),
        ("- Ablage 1\nirgendwas", "Unbekannte Zeile"),
        ("- Ablage 1\n  - Inhalt: [[a]] und mehr", "genau ein Wiki-Link"),
        ("- Ablage 1\n  - Inhalt:", "ohne Beschreibung"),
        ("- Ablage 1\n  - Inhalt: x\n- Ablage 2\n  - Inhalt: X", "Spalte bereits"),
        ("- Ablage 1\n  - Prozess: [[Mat-1|p]]\n  - Prozess: [[Mat-1|p]]", "Sprosse bereits"),
    ],
)
def test_parser_is_strict_with_line_numbers(body, message):
    with pytest.raises(LadderFormatError, match=message) as info:
        parse_ablage_section(body)
    assert info.value.line_no >= 1


def test_old_rung_label_is_rejected_not_reinterpreted():
    with pytest.raises(LadderFormatError, match="Unbekannte Zeile"):
        parse_ablage_section("- Sprosse 1\n  - Inhalt: x")


def test_link_without_alias_stays_an_own_block_verbatim():
    ladder = parse_ablage_section("- Ablage 1\n  - Inhalt: [[Notiz]]")
    assert ladder.rung(0).inhalt == (LadderBlock("[[Notiz]]"),)
    assert format_ablage_section(ladder) == ["- Ablage 1", "  - Inhalt: [[Notiz]]"]
