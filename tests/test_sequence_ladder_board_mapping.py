"""Leiter ↔ Board: Reihenfolge, Beschriftung, Farbtöne, Blasen, Spaltensperre (ohne Tk)."""

from __future__ import annotations

from pathlib import Path

from bw_gui.widgets.card_board import BoardCell, BoardSlot

from kursplaner.adapters.gui.lesson_kind_tints import LESSON_KIND_TINTS
from kursplaner.adapters.gui.sequence_ladder_board_mapping import (
    LANE_IDEEN,
    LANE_INHALT,
    LANE_PROZESS,
    block_ref,
    board_rows,
    can_drop,
    card_key,
    initial_cursor,
    ladder_slot,
    rung_key,
)
from kursplaner.core.domain.sequence_ladder import (
    BlockRef,
    LadderBlock,
    LadderRung,
    LadderSide,
    LadderSlot,
    SequenceLadder,
)
from kursplaner.core.usecases.load_sequence_ladder_usecase import RungInfo, RungKind, SequenceLadderView

LADDER = SequenceLadder(
    (
        LadderRung((LadderBlock("A"),), (LadderBlock("Netz", "Mat-PL-1"),), ("Idee 1", "Idee 2")),
        LadderRung((LadderBlock("B"),)),
    )
)


def _view(ladder=LADDER):
    rungs = (
        RungInfo("Mo 02.11.", RungKind.UNTERRICHT),
        RungInfo("Di 03.11.", RungKind.LZK),
        RungInfo("??", RungKind.OFFEN),
    )
    return SequenceLadderView(Path("x.md"), "Brüche", ladder, rungs)


def test_rows_run_top_down_with_dates_kinds_and_tints():
    rows = board_rows(_view())
    assert [row.key for row in rows] == [rung_key(2), rung_key(1), rung_key(0)]
    assert rows[1].label == "Sprosse 2\nDi 03.11. · LZK"
    lzk = LESSON_KIND_TINTS["lzk"]
    assert (rows[1].tint.color_tint, rows[1].tint.degree) == (lzk.color_tint, lzk.degree)
    assert rows[0].label == "Sprosse 3\n??" and rows[0].tint is None


A = card_key(BlockRef(0, LadderSide.INHALT, "A"))
NETZ = card_key(BlockRef(0, LadderSide.PROZESS, "Netz"))


def test_cards_key_a_block_ref_and_show_the_competence_code_as_badge():
    bottom = board_rows(_view())[-1]
    assert [(c.key, c.text, c.badge) for c in bottom.cards[LANE_PROZESS]] == [(NETZ, "Netz", "Mat-PL-1")]
    assert [c.key for c in bottom.cards[LANE_INHALT]] == [A]
    assert bottom.texts[LANE_IDEEN] == "Idee 1\nIdee 2"


def test_card_key_round_trips_texts_with_separators_of_other_kinds():
    ref = BlockRef(3, LadderSide.PROZESS, "a | b: c")
    assert block_ref(card_key(ref)) == ref


def test_drop_only_into_the_blocks_own_column():
    assert can_drop(LADDER, A, BoardSlot(rung_key(1), LANE_INHALT, 0))
    assert not can_drop(LADDER, A, BoardSlot(rung_key(1), LANE_PROZESS, 0))
    assert not can_drop(LADDER, NETZ, BoardSlot(rung_key(0), LANE_IDEEN, 0))


def test_no_drop_line_where_the_right_rung_already_holds_the_block():
    ladder = LADDER.with_rung(1, LadderRung((LadderBlock("B"),), (LadderBlock("Netz", "Mat-PL-1"),)))
    assert not can_drop(ladder, NETZ, BoardSlot(rung_key(1), LANE_PROZESS, 0))
    assert can_drop(ladder, NETZ, BoardSlot(rung_key(2), LANE_PROZESS, 0))
    assert can_drop(ladder, NETZ, BoardSlot(rung_key(0), LANE_PROZESS, 0))


def test_slot_translation_and_initial_cursor():
    assert ladder_slot(BoardSlot(rung_key(4), LANE_PROZESS, 2)) == LadderSlot(4, LadderSide.PROZESS, 2)
    assert initial_cursor(LADDER) == A
    assert initial_cursor(SequenceLadder()) == BoardCell(rung_key(0), LANE_INHALT)
