"""Sequenzleiter ↔ bw-gui-CardBoard: einzige Übersetzungsstelle.

Hier – und nur hier – stehen Spaltentitel, Lane-/Zeilenschlüssel, die
Darstellung der Sprossen-Beschriftung (Datum + Typ-Kürzel) und die Zuordnung
Termin-Art → Farbton (aus `LESSON_KIND_TINTS`). Board-Kartenschlüssel sind die
Baustein-Texte (Primärschlüssel, §37). Leiter-Index 0 ist die unterste Sprosse,
das Board zeigt die oberste Zeile zuerst; die Umrechnung steckt in
`rung_key`/`rung_index`.
"""

from __future__ import annotations

from bw_gui.widgets.card_board import BoardCard, BoardCell, BoardLane, BoardRow, BoardSlot, LaneKind, RowTint

from kursplaner.adapters.gui.lesson_kind_tints import KIND_AUSFALL, KIND_HOSPITATION, KIND_LZK, LESSON_KIND_TINTS
from kursplaner.core.domain.sequence_ladder import LadderSide, LadderSlot, SequenceLadder
from kursplaner.core.usecases.load_sequence_ladder_usecase import RungKind, SequenceLadderView

LANE_INHALT = "inhalt"
LANE_PROZESS = "prozess"
LANE_IDEEN = "ideen"

LANES: tuple[BoardLane, ...] = (
    BoardLane(LANE_INHALT, "Inhaltsbezogen – Stunden- und Teilziele"),
    BoardLane(LANE_PROZESS, "Prozessbezogen – vorrangig geförderte Kompetenzen"),
    BoardLane(LANE_IDEEN, "Ideen zur Umsetzung", LaneKind.TEXT, weight=0.8, placeholder="Ideen …"),
)

SIDE_BY_LANE: dict[str, LadderSide] = {LANE_INHALT: LadderSide.INHALT, LANE_PROZESS: LadderSide.PROZESS}
LANE_BY_SIDE: dict[LadderSide, str] = {side: lane for lane, side in SIDE_BY_LANE.items()}

_TINT_KIND = {RungKind.LZK: KIND_LZK, RungKind.HOSPITATION: KIND_HOSPITATION, RungKind.AUSFALL: KIND_AUSFALL}


def rung_key(index: int) -> str:
    """Board-Zeilenschlüssel einer Sprosse (Index 0 = unten)."""
    return f"sprosse-{index}"


def rung_index(row_key: str) -> int:
    """Sprossen-Index zu einem Board-Zeilenschlüssel."""
    return int(row_key.rsplit("-", 1)[1])


def _row_label(index: int, view: SequenceLadderView) -> str:
    info = view.rungs[index]
    tint_kind = _TINT_KIND.get(info.kind)
    suffix = f" · {LESSON_KIND_TINTS[tint_kind].label}" if tint_kind else ""
    return f"Sprosse {index + 1}\n{info.date_label}{suffix}"


def _row_tint(index: int, view: SequenceLadderView) -> RowTint | None:
    tint_kind = _TINT_KIND.get(view.rungs[index].kind)
    if tint_kind is None:
        return None
    tint = LESSON_KIND_TINTS[tint_kind]
    return RowTint(tint.color_tint, tint.degree, tint.base_token)


def board_rows(view: SequenceLadderView) -> list[BoardRow]:
    """Zeilen für das Board, oberste Sprosse zuerst (alle Sprossen aus `view.rungs`)."""
    ladder = view.ladder or SequenceLadder()
    rows: list[BoardRow] = []
    for index in reversed(range(len(view.rungs))):
        rung = ladder.rung(index)
        cards = {
            LANE_BY_SIDE[side]: tuple(
                BoardCard(block.text, block.text, block.kompetenz_id) for block in rung.blocks(side)
            )
            for side in LadderSide
        }
        rows.append(
            BoardRow(
                rung_key(index),
                _row_label(index, view),
                cards,
                {LANE_IDEEN: "\n".join(rung.ideen)},
                _row_tint(index, view),
            )
        )
    return rows


def ladder_slot(slot: BoardSlot) -> LadderSlot:
    """Board-Einfügeposition → Leiter-Position (nur Bausteinspalten)."""
    return LadderSlot(rung_index(slot.row_key), SIDE_BY_LANE[slot.lane_key], slot.index)


def cell_slot(cell: BoardCell, index: int) -> LadderSlot | None:
    """Leiter-Position in einer Board-Zelle; ``None`` für die Ideen-Spalte."""
    side = SIDE_BY_LANE.get(cell.lane_key)
    return LadderSlot(rung_index(cell.row_key), side, index) if side is not None else None


def board_cell(slot: LadderSlot) -> BoardCell:
    """Board-Zelle einer Leiter-Position."""
    return BoardCell(rung_key(slot.rung), LANE_BY_SIDE[slot.side])


def initial_cursor(ladder: SequenceLadder) -> str | BoardCell:
    """Startcursor: erster Inhalts-Baustein der untersten Sprosse, sonst deren Inhaltszelle."""
    blocks = ladder.rung(0).blocks(LadderSide.INHALT)
    return blocks[0].text if blocks else BoardCell(rung_key(0), LANE_INHALT)


def can_drop(ladder: SequenceLadder, card_key: str, slot: BoardSlot) -> bool:
    """Ablegen nur in der eigenen Spalte (§37: kein Baustein wechselt die Spalte)."""
    found = ladder.locate(card_key)
    return found is not None and SIDE_BY_LANE.get(slot.lane_key) is found[0].side
