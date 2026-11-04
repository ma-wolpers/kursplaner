"""Speicherorte der Sequenzleiter: Zuhause je Sprosse, Zusammensetzen und Zurückverteilen (rein, synthetisch)."""

from __future__ import annotations

from pathlib import Path

import pytest
from day_column_factory import make_day_column

from kursplaner.core.domain.sequence_ladder import (
    BlockRef,
    LadderBlock,
    LadderRuleError,
    LadderRung,
    LadderSide,
    SequenceLadder,
)
from kursplaner.core.domain.sequence_ladder_entries import block_from_entry, entry_from_block
from kursplaner.core.domain.sequence_ladder_homes import (
    AblageHome,
    MarkerHome,
    RungKind,
    UnitContent,
    UnitHome,
    compose_ladder,
    goals_from_left,
    ladder_homes,
    rung_kind,
    split_ladder,
)
from kursplaner.core.domain.sequence_ladder_ops import MoveBlock, RemoveBlock, apply_ladder_operation

U0, U1 = Path("u0.md"), Path("u1.ebw")


def _day(index, *, link=None, typ="Unterricht", ausfall=False):
    yaml = {} if ausfall else {"Stundentyp": typ}
    return make_day_column(
        row_index=index, datum="02-11-26", link=link, yaml=yaml, thema_ausfall="X Krank" if ausfall else ""
    )


def _existing(tmp_path, name, typ):
    """Stundentyp liest `DayColumn` nur aus einer existierenden Datei im Einheiten-Ordner (`is_valid_unterricht_link`)."""
    path = tmp_path / "Einheiten" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(f"---\nStundentyp: {typ}\n---\n", encoding="utf-8")
    return path


def test_homes_follow_the_terms_and_ablage_continues_above(tmp_path):
    lzk = _existing(tmp_path, "l.md", "LZK")
    homes = ladder_homes([_day(0, link=U0), _day(1, ausfall=True), _day(2, link=lzk, typ="LZK"), _day(3, link=U1)])
    assert homes.terms == (UnitHome(U0), MarkerHome(RungKind.AUSFALL), MarkerHome(RungKind.LZK), UnitHome(U1))
    assert homes.home(4) == AblageHome(1) and homes.home(6) == AblageHome(3)
    assert homes.locked_rungs == frozenset({1, 2}) and homes.unit_paths == (U0, U1)


def test_a_file_linked_twice_lives_only_in_its_first_rung_and_unlinked_lessons_are_locked():
    homes = ladder_homes([_day(0, link=U0), _day(1, link=U0), _day(2)])
    assert homes.terms == (UnitHome(U0), MarkerHome(RungKind.UNTERRICHT), MarkerHome(RungKind.UNTERRICHT))


def test_rung_kind_uses_the_one_lesson_type_rule(tmp_path):
    hospitation = _existing(tmp_path, "h.md", "Hospitation")
    assert rung_kind(_day(0, link=hospitation, typ="Hospitation")) is RungKind.HOSPITATION
    assert rung_kind(_day(0, ausfall=True)) is RungKind.AUSFALL
    assert ladder_homes([_day(0, link=hospitation, typ="Hospitation")]).terms == (MarkerHome(RungKind.HOSPITATION),)


def test_position_rule():
    assert goals_from_left(["Z", "T1", "T2"]) == ("Z", ("T1", "T2"))
    assert goals_from_left([]) == ("", ())


def _homes():
    return ladder_homes([_day(0, link=U0), _day(1, link=U1)])


def test_compose_and_split_round_trip_without_changes():
    units = {
        U0: UnitContent("Z", ("T",), ("[[Mat-1|Modellieren]]", "Frei"), ("Idee",)),
        U1: UnitContent("", ("Nur Teilziel",), (), ()),
    }
    ablage = SequenceLadder((LadderRung((LadderBlock("Abgelegt"),)),))
    composed = compose_ladder(_homes(), units, ablage)
    assert composed.ladder.rung(0).prozess[0] == LadderBlock("Modellieren", "Mat-1")
    assert composed.ladder.rung(2).inhalt == (LadderBlock("Abgelegt"),)
    split = split_ladder(composed.ladder, _homes(), units)
    assert split.units == {} and split.ablage == ablage


def test_split_keeps_stored_entry_text_of_unchanged_blocks():
    units = {U0: UnitContent("Z", (), ("[[Mat-1|Titel  mit  Leerraum]]",), ()), U1: UnitContent()}
    ladder = compose_ladder(_homes(), units, SequenceLadder()).ladder
    moved = apply_ladder_operation(ladder, MoveBlock(BlockRef(0, LadderSide.PROZESS, "Titel  mit  Leerraum"),
                                                     _slot(1, LadderSide.PROZESS))).ladder  # fmt: skip
    split = split_ladder(moved, _homes(), units)
    assert split.units[U1].kompetenzen == ("[[Mat-1|Titel  mit  Leerraum]]",)
    assert split.units[U0] == UnitContent("Z", (), (), ())


def _slot(rung, side):
    from kursplaner.core.domain.sequence_ladder import LadderSlot

    return LadderSlot(rung, side, 0)


def test_removing_the_stundenziel_promotes_the_first_teilziel():
    units = {U0: UnitContent("Z", ("T1", "T2"), (), ()), U1: UnitContent()}
    ladder = compose_ladder(_homes(), units, SequenceLadder()).ladder
    removed = apply_ladder_operation(ladder, RemoveBlock(BlockRef(0, LadderSide.INHALT, "Z"))).ladder
    assert split_ladder(removed, _homes(), units).units[U0] == UnitContent("T1", ("T2",), (), ())


def test_unreadable_or_multiline_units_lock_their_rung_with_a_note():
    units = {U1: UnitContent("Zeile 1\nZeile 2")}
    composed = compose_ladder(_homes(), units, SequenceLadder())
    assert composed.ladder.locked_rungs == frozenset({0, 1})
    assert len(composed.notes) == 2 and "nicht lesbar" in composed.notes[0]
    assert split_ladder(composed.ladder, _homes(), units).units == {}


def test_duplicates_inside_one_unit_are_shown_once_with_a_note():
    units = {U0: UnitContent("Z", ("Z", "T"), ("K", "k"), ()), U1: UnitContent()}
    composed = compose_ladder(_homes(), units, SequenceLadder())
    assert [b.text for b in composed.ladder.rung(0).inhalt] == ["Z", "T"]
    assert [b.text for b in composed.ladder.rung(0).prozess] == ["K"]
    assert "nur einmal" in composed.notes[0]
    assert split_ladder(composed.ladder, _homes(), units).units == {}  # unverändert: nichts geschrieben


def test_split_refuses_content_on_a_locked_rung():
    homes = ladder_homes([_day(0, ausfall=True)])
    ladder = SequenceLadder((LadderRung((LadderBlock("X"),)),), frozenset({0}))
    with pytest.raises(LadderRuleError, match="Sprosse 1"):
        split_ladder(ladder, homes, {})


@pytest.mark.parametrize(
    ("entry", "block"),
    [
        ("[[Mat-RF-14|Terme]]", LadderBlock("Terme", "Mat-RF-14")),
        ("[[Notiz]]", LadderBlock("[[Notiz]]")),
        ("Tafelbild [[Skizze]]", LadderBlock("Tafelbild [[Skizze]]")),
        ("Freitext", LadderBlock("Freitext")),
    ],
)
def test_entries_and_blocks_translate_both_ways(entry, block):
    assert block_from_entry(entry) == block
    assert entry_from_block(block) == entry
