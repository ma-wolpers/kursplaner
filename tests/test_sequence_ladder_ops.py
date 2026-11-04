"""Sequenzleiter-Operationen: Regeln, Strg+Pfeil-Semantik, Import-Platzierung (synthetische Daten)."""

from __future__ import annotations

import pytest

from kursplaner.core.domain.sequence_ladder import (
    BlockRef,
    LadderBlock,
    LadderRuleError,
    LadderRung,
    LadderSide,
    LadderSlot,
    SequenceLadder,
    block_text_error,
)
from kursplaner.core.domain.sequence_ladder_ops import (
    AddBlock,
    ImportCompetences,
    ImportedCompetence,
    MoveBlock,
    RemoveBlock,
    RenameBlock,
    SetIdeas,
    StepBlock,
    apply_ladder_operation,
    operation_label,
)

INH, PRO = LadderSide.INHALT, LadderSide.PROZESS


def _ladder() -> SequenceLadder:
    return SequenceLadder(
        (
            LadderRung((LadderBlock("A"), LadderBlock("B")), (LadderBlock("Netz", "Mat-PL-1"),)),
            LadderRung((LadderBlock("C"),)),
        )
    )


def _texts(ladder: SequenceLadder, rung: int, side: LadderSide) -> list[str]:
    return [block.text for block in ladder.rung(rung).blocks(side)]


def _apply(ladder, op):
    return apply_ladder_operation(ladder, op).ladder


def test_add_appends_and_rejects_left_duplicates_across_the_column():
    result = apply_ladder_operation(_ladder(), AddBlock(LadderSlot(1, INH, 99), "D"))
    assert _texts(result.ladder, 1, INH) == ["C", "D"]
    assert result.focus == BlockRef(1, INH, "D")
    with pytest.raises(LadderRuleError, match="Spalte bereits"):
        _apply(result.ladder, AddBlock(LadderSlot(0, INH, 0), "  d "))


def test_columns_are_independent_scopes():
    ladder = _apply(_ladder(), AddBlock(LadderSlot(0, PRO, 0), "A"))
    assert _texts(ladder, 0, PRO) == ["A", "Netz"]


def test_right_column_allows_the_same_block_in_other_rungs_but_not_twice_in_one():
    ladder = _apply(_ladder(), AddBlock(LadderSlot(1, PRO, 0), "Netz"))
    assert _texts(ladder, 1, PRO) == ["Netz"]
    with pytest.raises(LadderRuleError, match="Sprosse bereits"):
        _apply(ladder, AddBlock(LadderSlot(1, PRO, 0), "netz"))


def test_moving_a_right_block_into_a_rung_that_already_has_it_is_refused():
    ladder = _apply(_ladder(), AddBlock(LadderSlot(1, PRO, 0), "Netz"))
    with pytest.raises(LadderRuleError, match="Sprosse 2"):
        _apply(ladder, StepBlock(BlockRef(0, PRO, "Netz"), up=True))
    with pytest.raises(LadderRuleError, match="Sprosse 1"):
        _apply(ladder, MoveBlock(BlockRef(1, PRO, "Netz"), LadderSlot(0, PRO, 0)))


def test_paste_inserts_above_the_selected_block():
    ladder = _apply(_ladder(), AddBlock(LadderSlot(0, INH, 1), "Kopie", pasted=True))
    assert _texts(ladder, 0, INH) == ["A", "Kopie", "B"]


@pytest.mark.parametrize("text", ["", "   ", "zwei\nZeilen", "[[Mat-1]]"])
def test_own_block_text_rules(text):
    assert block_text_error(text, SequenceLadder(), side=INH, rung=0) is not None


def test_rename_keeps_position_and_allows_case_change_of_itself():
    result = apply_ladder_operation(_ladder(), RenameBlock(BlockRef(0, INH, "B"), "b"))
    assert _texts(result.ladder, 0, INH) == ["A", "b"]
    assert result.focus == BlockRef(0, INH, "b")


def test_rename_of_network_block_is_refused():
    with pytest.raises(LadderRuleError, match="nicht umbenannt"):
        _apply(_ladder(), RenameBlock(BlockRef(0, PRO, "Netz"), "Neu"))


def test_remove_deletes_any_block_and_trims_empty_top_rungs():
    ladder = _apply(_ladder(), RemoveBlock(BlockRef(1, INH, "C")))
    assert len(ladder.rungs) == 1
    assert _texts(_apply(ladder, RemoveBlock(BlockRef(0, PRO, "Netz"))), 0, PRO) == []


def test_step_up_swaps_within_cell_then_jumps_to_bottom_of_next_rung():
    result = apply_ladder_operation(_ladder(), StepBlock(BlockRef(0, INH, "B"), up=True))
    assert _texts(result.ladder, 0, INH) == ["B", "A"]
    result = apply_ladder_operation(result.ladder, StepBlock(result.focus, up=True))
    assert _texts(result.ladder, 0, INH) == ["A"]
    assert _texts(result.ladder, 1, INH) == ["C", "B"]
    assert result.focus == BlockRef(1, INH, "B")


def test_step_up_from_top_rung_creates_a_new_rung():
    ladder = _apply(_ladder(), StepBlock(BlockRef(1, INH, "C"), up=True))
    assert _texts(ladder, 2, INH) == ["C"]
    assert _texts(ladder, 1, INH) == []


def test_step_down_is_symmetric_and_stops_at_the_bottom():
    ladder = _apply(_ladder(), StepBlock(BlockRef(1, INH, "C"), up=False))
    assert _texts(ladder, 0, INH) == ["C", "A", "B"]
    ladder = _apply(ladder, StepBlock(BlockRef(0, INH, "B"), up=False))
    unchanged = apply_ladder_operation(ladder, StepBlock(BlockRef(0, INH, "B"), up=False)).ladder
    assert unchanged == ladder


def test_move_respects_index_after_removal_and_column_lock():
    ladder = _apply(_ladder(), MoveBlock(BlockRef(0, INH, "A"), LadderSlot(0, INH, 1)))
    assert _texts(ladder, 0, INH) == ["B", "A"]
    ladder = _apply(_ladder(), MoveBlock(BlockRef(0, INH, "A"), LadderSlot(3, INH, 0)))
    assert _texts(ladder, 3, INH) == ["A"]
    with pytest.raises(LadderRuleError, match="Spalte"):
        _apply(_ladder(), MoveBlock(BlockRef(0, INH, "A"), LadderSlot(0, PRO, 0)))


def test_import_puts_each_side_into_one_rung_above_its_highest_occupied():
    items = (
        ImportedCompetence("Mat-RF-1", "Inhalt 1", INH),
        ImportedCompetence("Mat-RF-2", "Inhalt 2", INH),
        ImportedCompetence("Mat-PL-2", "Prozess 2", PRO),
    )
    ladder = _apply(_ladder(), ImportCompetences(items))
    assert _texts(ladder, 2, INH) == ["Inhalt 1", "Inhalt 2"]
    assert _texts(ladder, 1, PRO) == ["Prozess 2"]
    assert ladder.rung(2).inhalt[0].kompetenz_id == "Mat-RF-1"


def test_import_skips_left_collisions_but_repeats_right_competences_in_a_new_rung():
    items = (
        ImportedCompetence("Mat-PL-1", "Netz", PRO),
        ImportedCompetence("Mat-PL-1", "Netz", PRO),
        ImportedCompetence("Mat-X-9", "a", INH),
    )
    result = apply_ladder_operation(_ladder(), ImportCompetences(items))
    assert _texts(result.ladder, 1, PRO) == ["Netz"]
    assert _texts(result.ladder, 2, INH) == []
    assert len(result.notes) == 2


def test_set_ideas_drops_trailing_blank_lines():
    ladder = _apply(SequenceLadder(), SetIdeas(1, ("Idee", "", "  ")))
    assert ladder.rung(1).ideen == ("Idee",)
    assert ladder.rung(0).is_empty


def test_labels_are_short_and_distinguish_paste():
    assert operation_label(AddBlock(LadderSlot(0, INH, 0), "x")) == "Baustein anlegen"
    assert operation_label(AddBlock(LadderSlot(0, INH, 0), "x", pasted=True)) == "Baustein einfügen"
    assert operation_label(StepBlock(BlockRef(0, INH, "x"), up=True)) == "Baustein verschieben"


def test_unknown_block_reference_is_a_rule_error():
    with pytest.raises(LadderRuleError, match="nicht gefunden"):
        _apply(_ladder(), RemoveBlock(BlockRef(0, INH, "gibt es nicht")))
    with pytest.raises(LadderRuleError, match="nicht gefunden"):
        _apply(_ladder(), RemoveBlock(BlockRef(1, PRO, "Netz")))


def _locked() -> SequenceLadder:
    """Sprosse 1 gesperrt (z. B. LZK zwischen zwei Einheiten)."""
    return SequenceLadder(_ladder().rungs[:1] + (LadderRung(), LadderRung((LadderBlock("C"),))), frozenset({1}))


def test_locked_rungs_refuse_blocks_moves_and_ideas():
    ladder = _locked()
    for op in (
        AddBlock(LadderSlot(1, INH, 0), "X"),
        MoveBlock(BlockRef(0, INH, "A"), LadderSlot(1, INH, 0)),
        SetIdeas(1, ("Idee",)),
    ):
        with pytest.raises(LadderRuleError, match="Sprosse 2"):
            apply_ladder_operation(ladder, op)


def test_ctrl_arrows_and_import_skip_locked_rungs():
    ladder = _locked()
    up = apply_ladder_operation(ladder, StepBlock(BlockRef(0, INH, "A"), up=True))
    assert up.focus == BlockRef(2, INH, "A") and _texts(up.ladder, 2, INH) == ["C", "A"]
    down = apply_ladder_operation(ladder, StepBlock(BlockRef(2, INH, "C"), up=False))
    assert down.focus == BlockRef(0, INH, "C")
    item = ImportedCompetence("Mat-X-1", "X", PRO)
    assert _texts(apply_ladder_operation(ladder, ImportCompetences((item,))).ladder, 2, PRO) == ["X"]
    assert up.ladder.locked_rungs == frozenset({1})  # Sperre überlebt jede Operation


def test_legacy_duplicates_stay_movable_renamable_and_deletable():
    ladder = SequenceLadder((LadderRung((LadderBlock("Gleich"),)), LadderRung((LadderBlock("gleich"),))))
    assert ladder.duplicate_groups() == ((BlockRef(0, INH, "Gleich"), BlockRef(1, INH, "gleich")),)
    moved = apply_ladder_operation(ladder, MoveBlock(BlockRef(0, INH, "Gleich"), LadderSlot(2, INH, 0)))
    assert _texts(moved.ladder, 2, INH) == ["Gleich"]
    renamed = apply_ladder_operation(ladder, RenameBlock(BlockRef(1, INH, "gleich"), "Anders")).ladder
    assert renamed.duplicate_groups() == ()
    assert apply_ladder_operation(ladder, RemoveBlock(BlockRef(1, INH, "gleich"))).ladder.duplicate_groups() == ()
    with pytest.raises(LadderRuleError):
        apply_ladder_operation(ladder, AddBlock(LadderSlot(3, INH, 0), "GLEICH"))


def test_moving_a_right_block_to_another_rung_still_checks_that_rung():
    ladder = SequenceLadder(
        (LadderRung(prozess=(LadderBlock("P", "Mat-1"),)), LadderRung(prozess=(LadderBlock("anders", "Mat-1"),)))
    )
    with pytest.raises(LadderRuleError, match="Sprosse 2"):
        apply_ladder_operation(ladder, MoveBlock(BlockRef(0, PRO, "P"), LadderSlot(1, PRO, 0)))


def test_duplicate_groups_are_connected_over_text_and_competence_id():
    ladder = SequenceLadder(
        (
            LadderRung((LadderBlock("Titel", "Mat-1"),)),
            LadderRung((LadderBlock("titel"),)),
            LadderRung((LadderBlock("Anders", "Mat-1"),)),
        )
    )
    assert ladder.duplicate_groups() == (
        (BlockRef(0, INH, "Titel"), BlockRef(1, INH, "titel"), BlockRef(2, INH, "Anders")),
    )


def test_block_text_follows_the_list_entry_contract():
    assert "';'" in (block_text_error("K1; K2", SequenceLadder(), side=INH, rung=0) or "")
