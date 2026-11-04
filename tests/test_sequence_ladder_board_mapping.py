"""Leiter ↔ Board: Reihenfolge, Beschriftung, Farbtöne, Blasen, Spaltensperre (ohne Tk)."""

from __future__ import annotations

from pathlib import Path

from bw_gui.widgets.card_board import BoardCell, BoardSlot

from kursplaner.adapters.gui.lesson_kind_tints import LESSON_KIND_TINTS
from kursplaner.adapters.gui.sequence_ladder_board_mapping import (
    LANE_IDEEN,
    LANE_INHALT,
    LANE_PROZESS,
    board_rows,
    can_drop,
    initial_cursor,
    ladder_slot,
    rung_key,
)
from kursplaner.core.domain.sequence_ladder import LadderBlock, LadderRung, LadderSide, LadderSlot, SequenceLadder
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


def test_cards_use_text_as_key_and_competence_code_as_badge():
    bottom = board_rows(_view())[-1]
    assert [(c.key, c.badge) for c in bottom.cards[LANE_PROZESS]] == [("Netz", "Mat-PL-1")]
    assert [c.key for c in bottom.cards[LANE_INHALT]] == ["A"]
    assert bottom.texts[LANE_IDEEN] == "Idee 1\nIdee 2"


def test_drop_only_into_the_blocks_own_column():
    assert can_drop(LADDER, "A", BoardSlot(rung_key(1), LANE_INHALT, 0))
    assert not can_drop(LADDER, "A", BoardSlot(rung_key(1), LANE_PROZESS, 0))
    assert not can_drop(LADDER, "Netz", BoardSlot(rung_key(0), LANE_IDEEN, 0))


def test_slot_translation_and_initial_cursor():
    assert ladder_slot(BoardSlot(rung_key(4), LANE_PROZESS, 2)) == LadderSlot(4, LadderSide.PROZESS, 2)
    assert initial_cursor(LADDER) == "A"
    assert initial_cursor(SequenceLadder()) == BoardCell(rung_key(0), LANE_INHALT)
