"""Material als dritte Leiter-Seite: Regeln, „+ “-Zeilen, Speicherorte, Ablage, Zuordnen, Board (synthetisch)."""

from __future__ import annotations

from pathlib import Path

from sequence_ladder_test_support import make_ladder_env

from kursplaner.adapters.gui.sequence_ladder_board_mapping import LANE_IDEEN, board_rows, can_drop, card_key
from kursplaner.core.domain.sequence_ladder import (
    COMPETENCE_SIDES,
    BlockRef,
    LadderBlock,
    LadderRung,
    LadderSide,
    LadderSlot,
    SequenceLadder,
    block_text_error,
    uniqueness_scope,
)
from kursplaner.core.domain.sequence_ladder_assign import merge_rung_into_unit, overwrite_warnings
from kursplaner.core.domain.sequence_ladder_codec import format_ablage_section, parse_ablage_section
from kursplaner.core.domain.sequence_ladder_homes import UnitContent
from kursplaner.core.domain.sequence_ladder_ops import (
    AddBlock,
    SetIdeas,
    StepBlock,
    apply_ladder_operation,
    operation_label,
    split_material_lines,
)
from kursplaner.core.usecases.load_sequence_ladder_usecase import RungInfo, RungKind, SequenceLadderView
from kursplaner.infrastructure.repositories.plan_table_file_repository import load_linked_lesson_yaml

MAT, INH = LadderSide.MATERIAL, LadderSide.INHALT
LINK = "[[Material/AB Brüche.pdf|AB 1]]"


def _material(*texts):
    return tuple(LadderBlock(text) for text in texts)


# -- Regeln -----------------------------------------------------------------------


def test_material_is_unique_per_rung_and_may_be_a_wiki_link():
    assert COMPETENCE_SIDES == (LadderSide.INHALT, LadderSide.PROZESS)
    assert uniqueness_scope(MAT, 2) == (MAT, 2)
    ladder = SequenceLadder((LadderRung(material=_material("Buch")), LadderRung()))
    assert block_text_error(LINK, ladder, side=MAT, rung=0) is None
    assert block_text_error("buch", ladder, side=MAT, rung=0) is not None
    assert block_text_error("Buch", ladder, side=MAT, rung=1) is None
    assert block_text_error(LINK, ladder, side=INH, rung=0) is not None


def test_material_alone_makes_a_rung_non_empty():
    assert not LadderRung(material=_material("Buch")).is_empty


# -- „+ “-Zeilen ---------------------------------------------------------------------


def test_only_the_leading_plus_lines_are_material():
    material, rest = split_material_lines(("+ AB 1", "  + Buch S. 12", "Idee", "+ später"))
    assert material == (("+ AB 1", "AB 1"), ("  + Buch S. 12", "Buch S. 12"))
    assert rest == ("Idee", "+ später")
    assert split_material_lines(("+Kein Leerzeichen",)) == ((), ("+Kein Leerzeichen",))


def test_set_ideas_turns_plus_lines_into_material_above_the_ideas():
    ladder = SequenceLadder((LadderRung(material=_material("Alt")),))
    op = SetIdeas(0, ("+ AB 1", "+ Buch", "Plakat"))
    result = apply_ladder_operation(ladder, op)
    rung = result.ladder.rung(0)
    assert [b.text for b in rung.material] == ["Alt", "AB 1", "Buch"]
    assert rung.ideen == ("Plakat",)
    assert operation_label(op) == "Ideen/Material bearbeiten"
    assert operation_label(SetIdeas(0, ("Plakat",))) == "Ideen bearbeiten"


def test_rejected_plus_line_stays_in_the_ideas_with_a_note():
    ladder = SequenceLadder((LadderRung(material=_material("Buch")),))
    result = apply_ladder_operation(ladder, SetIdeas(0, ("+ buch", "+ ---", "+ Neu", "Rest")))
    rung = result.ladder.rung(0)
    assert [b.text for b in rung.material] == ["Buch", "Neu"]
    assert rung.ideen == ("+ buch", "+ ---", "Rest")
    assert len(result.notes) == 2 and "bleibt im Ideenfeld" in result.notes[0]


def test_editing_ideas_keeps_existing_material():
    ladder = SequenceLadder((LadderRung(_material("Z"), (), ("alt",), _material("Buch")),))
    rung = apply_ladder_operation(ladder, SetIdeas(0, ("neu",))).ladder.rung(0)
    assert [b.text for b in rung.material] == ["Buch"] and rung.inhalt == _material("Z")


# -- Verschieben ----------------------------------------------------------------------


def test_lowest_material_steps_down_to_the_top_of_the_rung_below_and_back():
    ladder = SequenceLadder((LadderRung(material=_material("X")), LadderRung(material=_material("A", "B"))))
    down = apply_ladder_operation(ladder, StepBlock(BlockRef(1, MAT, "B"), up=False)).ladder
    assert [b.text for b in down.rung(0).material] == ["B", "X"]
    assert [b.text for b in down.rung(1).material] == ["A"]
    up = apply_ladder_operation(down, StepBlock(BlockRef(0, MAT, "B"), up=True)).ladder
    assert [b.text for b in up.rung(1).material] == ["A", "B"]


# -- Ablage-Format --------------------------------------------------------------------


def test_ablage_round_trips_material_lines_literally():
    ablage = SequenceLadder((LadderRung(_material("Z"), (), ("Idee",), _material(LINK, "Buch")),))
    lines = format_ablage_section(ablage)
    assert lines == ["- Ablage 1", "  - Inhalt: Z", f"  - Material: {LINK}", "  - Material: Buch", "  - Idee: Idee"]
    assert parse_ablage_section("\n".join(lines)) == ablage


# -- Zuordnen -------------------------------------------------------------------------


def test_assign_appends_material_without_duplicates_and_warns():
    rung = LadderRung(material=_material("buch", "Neu"))
    old = UnitContent("Ziel", (), ("K",), ("I",), ("Buch",))
    merged = merge_rung_into_unit(rung, old)
    assert merged.material == ("Buch", "Neu")
    assert (merged.stundenziel, merged.kompetenzen, merged.ideen) == ("Ziel", ("K",), ("I",))
    assert any("Material" in warning for warning in overwrite_warnings(rung, old, "", ""))


# -- Echte Dateien ---------------------------------------------------------------------


def test_unit_material_is_read_as_blocks_and_plus_lines_land_in_the_yaml(tmp_path):
    env = make_ladder_env(tmp_path, "UU", u0={"material": (LINK,)})
    view = env.view()
    assert view.ladder.rung(0).material == (LadderBlock(LINK),)
    result = env.execute(SetIdeas(0, ("+ Buch S. 12", "Plakat")))
    assert result.applied
    unit = env.units[0]
    assert load_linked_lesson_yaml(unit).data["Material"] == [LINK, "Buch S. 12"]
    text = unit.read_text(encoding="utf-8")
    assert text.endswith("## Ideen\n\nPlakat\n") and "+ Buch" not in text


def test_material_moves_between_units_and_keeps_its_stored_text(tmp_path):
    env = make_ladder_env(tmp_path, "UU", u1={"material": (LINK,)})
    assert env.execute(StepBlock(BlockRef(1, MAT, LINK), up=False)).applied
    assert load_linked_lesson_yaml(env.units[0]).data["Material"] == [LINK]
    assert load_linked_lesson_yaml(env.units[1]).data.get("Material", []) == []


def test_plus_adds_material_at_the_end_of_the_stack(tmp_path):
    env = make_ladder_env(tmp_path, "U", u0={"material": ("A",)})
    assert env.execute(AddBlock(LadderSlot(0, MAT, 1), "B")).applied
    assert load_linked_lesson_yaml(env.units[0]).data["Material"] == ["A", "B"]


# -- Board ----------------------------------------------------------------------------


def test_material_cards_sit_in_the_ideas_lane_with_their_display_name():
    ladder = SequenceLadder((LadderRung(ideen=("Idee",), material=_material(LINK)),))
    view = SequenceLadderView(Path("x.md"), "Brüche", ladder, (RungInfo("Mo", RungKind.UNTERRICHT),))
    (row,) = board_rows(view)
    (card,) = row.cards[LANE_IDEEN]
    assert card.text == "AB 1" and card.key == card_key(BlockRef(0, MAT, LINK))
    assert row.texts[LANE_IDEEN] == "Idee"


def test_material_cannot_be_dropped_into_a_competence_lane():
    from bw_gui.widgets.card_board import BoardSlot

    from kursplaner.adapters.gui.sequence_ladder_board_mapping import LANE_PROZESS, rung_key

    ladder = SequenceLadder((LadderRung(), LadderRung(material=_material("Buch"))))
    key = card_key(BlockRef(1, MAT, "Buch"))
    assert can_drop(ladder, key, BoardSlot(rung_key(0), LANE_IDEEN, 0))
    assert not can_drop(ladder, key, BoardSlot(rung_key(0), LANE_PROZESS, 0))
