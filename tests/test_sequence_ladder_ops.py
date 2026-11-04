"""Sequenzleiter-Operationen: Regeln, Strg+Pfeil-Semantik, Import-Platzierung (synthetische Daten)."""

from __future__ import annotations

import pytest

from kursplaner.core.domain.sequence_ladder import (
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


def test_add_appends_and_rejects_duplicates_case_insensitively():
    ladder = _apply(_ladder(), AddBlock(LadderSlot(1, INH, 99), "D"))
    assert _texts(ladder, 1, INH) == ["C", "D"]
    with pytest.raises(LadderRuleError, match="bereits"):
        _apply(ladder, AddBlock(LadderSlot(0, PRO, 0), "  d "))


def test_paste_inserts_above_the_selected_block():
    ladder = _apply(_ladder(), AddBlock(LadderSlot(0, INH, 1), "Kopie", pasted=True))
    assert _texts(ladder, 0, INH) == ["A", "Kopie", "B"]


@pytest.mark.parametrize("text", ["", "   ", "zwei\nZeilen", "[[Mat-1]]"])
def test_own_block_text_rules(text):
    assert block_text_error(text, SequenceLadder()) is not None


def test_rename_keeps_position_and_allows_case_change_of_itself():
    ladder = _apply(_ladder(), RenameBlock("B", "b"))
    assert _texts(ladder, 0, INH) == ["A", "b"]


def test_rename_of_network_block_is_refused():
    with pytest.raises(LadderRuleError, match="nicht umbenannt"):
        _apply(_ladder(), RenameBlock("Netz", "Neu"))


def test_remove_deletes_any_block_and_trims_empty_top_rungs():
    ladder = _apply(_ladder(), RemoveBlock("C"))
    assert len(ladder.rungs) == 1
    assert _texts(_apply(ladder, RemoveBlock("Netz")), 0, PRO) == []


def test_step_up_swaps_within_cell_then_jumps_to_bottom_of_next_rung():
    ladder = _apply(_ladder(), StepBlock("B", up=True))
    assert _texts(ladder, 0, INH) == ["B", "A"]
    ladder = _apply(ladder, StepBlock("B", up=True))
    assert _texts(ladder, 0, INH) == ["A"]
    assert _texts(ladder, 1, INH) == ["C", "B"]


def test_step_up_from_top_rung_creates_a_new_rung():
    ladder = _apply(_ladder(), StepBlock("C", up=True))
    assert _texts(ladder, 2, INH) == ["C"]
    assert _texts(ladder, 1, INH) == []


def test_step_down_is_symmetric_and_stops_at_the_bottom():
    ladder = _apply(_ladder(), StepBlock("C", up=False))
    assert _texts(ladder, 0, INH) == ["C", "A", "B"]
    ladder = _apply(ladder, StepBlock("B", up=False))
    unchanged = apply_ladder_operation(ladder, StepBlock("B", up=False)).ladder
    assert unchanged == ladder


def test_move_respects_index_after_removal_and_column_lock():
    ladder = _apply(_ladder(), MoveBlock("A", LadderSlot(0, INH, 1)))
    assert _texts(ladder, 0, INH) == ["B", "A"]
    ladder = _apply(_ladder(), MoveBlock("A", LadderSlot(3, INH, 0)))
    assert _texts(ladder, 3, INH) == ["A"]
    with pytest.raises(LadderRuleError, match="Spalte"):
        _apply(_ladder(), MoveBlock("A", LadderSlot(0, PRO, 0)))


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


def test_import_skips_known_ids_and_text_collisions_with_notes():
    items = (ImportedCompetence("Mat-PL-1", "Netz", PRO), ImportedCompetence("Mat-X-9", "a", INH))
    result = apply_ladder_operation(_ladder(), ImportCompetences(items))
    assert result.ladder == _ladder()
    assert len(result.notes) == 2


def test_set_ideas_drops_trailing_blank_lines():
    ladder = _apply(SequenceLadder(), SetIdeas(1, ("Idee", "", "  ")))
    assert ladder.rung(1).ideen == ("Idee",)
    assert ladder.rung(0).is_empty


def test_labels_are_short_and_distinguish_paste():
    assert operation_label(AddBlock(LadderSlot(0, INH, 0), "x")) == "Baustein anlegen"
    assert operation_label(AddBlock(LadderSlot(0, INH, 0), "x", pasted=True)) == "Baustein einfügen"
    assert operation_label(StepBlock("x", up=True)) == "Baustein verschieben"


def test_unknown_block_reference_is_a_rule_error():
    with pytest.raises(LadderRuleError, match="nicht gefunden"):
        _apply(_ladder(), RemoveBlock("gibt es nicht"))
