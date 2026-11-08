"""Sequenzleiter ↔ bw-gui-CardBoard: einzige Übersetzungsstelle.

Hier – und nur hier – stehen Spaltentitel, Lane-/Zeilenschlüssel, die
Darstellung der Sprossen-Beschriftung (Datum + Typ-Kürzel) und die Zuordnung
Termin-Art → Farbton (aus `LESSON_KIND_TINTS`). Board-Kartenschlüssel kodieren
einen `BlockRef` (Sprosse, Spalte, Text; `card_key`/`block_ref`), weil derselbe
Text rechts in mehreren Sprossen stehen darf (§37). Leiter-Index 0 ist die unterste Sprosse,
das Board zeigt die oberste Zeile zuerst; die Umrechnung steckt in
`rung_key`/`rung_index`.

Markierungen: gesperrte Sprossen (LZK/Hospitation/Ausfall) werden gesperrte
Board-Zeilen; der oberste linke Baustein einer Unterrichts-Sprosse – ihr
Stundenziel nach der Positionsregel (`sequence_ladder_homes.goals_from_left`) –
trägt den Ton `EMPHASIS`; Altbestand-Doppelungen (`SequenceLadderView.duplicates`)
den Ton `WARNING` und einen Hinweis im Banner (`view_hints`).
"""

from __future__ import annotations

from bw_gui.widgets.card_board import (
    BoardCard,
    BoardCell,
    BoardLane,
    BoardRow,
    BoardSlot,
    CardTone,
    Cursor,
    LaneKind,
    RowTint,
)

from kursplaner.adapters.gui.lesson_kind_tints import LESSON_KIND_TINTS, LessonKindTint
from kursplaner.core.domain.sequence_ladder import (
    BlockRef,
    LadderRuleError,
    LadderRung,
    LadderSide,
    LadderSlot,
    SequenceLadder,
)
from kursplaner.core.domain.sequence_ladder_ops import MoveBlock, apply_ladder_operation
from kursplaner.core.usecases.load_sequence_ladder_usecase import RungInfo, RungKind, SequenceLadderView

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


def _kind_tint(kind: RungKind) -> LessonKindTint | None:
    """Farbton einer Sprossenart: `RungKind`-Werte sind die Terminart-Schlüssel (`lesson_kinds`)."""
    return LESSON_KIND_TINTS.get(kind.value)


def rung_key(index: int) -> str:
    """Board-Zeilenschlüssel einer Sprosse (Index 0 = unten)."""
    return f"sprosse-{index}"


def rung_index(row_key: str) -> int:
    """Sprossen-Index zu einem Board-Zeilenschlüssel."""
    return int(row_key.rsplit("-", 1)[1])


_KEY_SEPARATOR = "\n"
"""Trenner im Kartenschlüssel; Baustein-Texte sind einzeilig und enthalten ihn nie."""


def card_key(ref: BlockRef) -> str:
    """Board-Kartenschlüssel eines Bausteins."""
    return _KEY_SEPARATOR.join((str(ref.rung), ref.side.value, ref.text))


def block_ref(key: str) -> BlockRef:
    """Baustein-Verweis zu einem Board-Kartenschlüssel (Umkehrung von `card_key`)."""
    rung, side, text = key.split(_KEY_SEPARATOR, 2)
    return BlockRef(int(rung), LadderSide(side), text)


def cursor_rung(cursor: Cursor) -> int | None:
    """Sprossen-Index unter dem Board-Cursor (Zelle oder Baustein); ``None`` ohne Cursor."""
    if isinstance(cursor, BoardCell):
        return rung_index(cursor.row_key)
    if isinstance(cursor, str):
        return block_ref(cursor).rung
    return None


def rung_cursor(index: int) -> BoardCell:
    """Cursor auf die Inhaltszelle einer Sprosse (Einstieg beim Umschalten aus dem Grid)."""
    return BoardCell(rung_key(index), LANE_INHALT)


ASSIGN_ACTION_TEXT = "→ Einheit"
"""Knopftext an Ablage-Sprossen mit Inhalt: Sprosse einer Plan-Zeile zuordnen."""


def term_label(info: RungInfo) -> str:
    """Termin-Text: Kurzdatum, bei LZK/Hospitation/Ausfall mit Art (Sprossen-Label und Zielauswahl)."""
    tint = _kind_tint(info.kind)
    suffix = f" · {tint.label}" if tint is not None else ""
    return f"{info.date_label}{suffix}"


def _row_label(index: int, view: SequenceLadderView) -> str:
    return f"Sprosse {index + 1}\n{term_label(view.rungs[index])}"


def _row_action(index: int, rung: LadderRung, view: SequenceLadderView) -> str | None:
    """Zuordnen-Knopf nur an Ablage-Sprossen („??“) mit Inhalt einer lesbaren Leiter."""
    assignable = view.ladder is not None and view.rungs[index].kind is RungKind.OFFEN and not rung.is_empty
    return ASSIGN_ACTION_TEXT if assignable else None


def _row_tint(index: int, view: SequenceLadderView) -> RowTint | None:
    tint = _kind_tint(view.rungs[index].kind)
    if tint is None:
        return None
    return RowTint(tint.color_tint, tint.degree, tint.base_token)


def _tone(view: SequenceLadderView, ref: BlockRef, position: int, locked: bool) -> CardTone:
    if any(ref in group for group in view.duplicates):
        return CardTone.WARNING
    is_unit = view.rungs[ref.rung].kind is RungKind.UNTERRICHT and not locked
    return CardTone.EMPHASIS if is_unit and ref.side is LadderSide.INHALT and position == 0 else CardTone.NORMAL


def board_rows(view: SequenceLadderView) -> list[BoardRow]:
    """Zeilen für das Board, oberste Sprosse zuerst (alle Sprossen aus `view.rungs`)."""
    ladder = view.ladder or SequenceLadder()
    rows: list[BoardRow] = []
    for index in reversed(range(len(view.rungs))):
        rung, locked = ladder.rung(index), ladder.is_locked(index)
        cards = {
            LANE_BY_SIDE[side]: tuple(
                BoardCard(
                    card_key(ref := BlockRef(index, side, block.text)),
                    block.text,
                    block.kompetenz_id,
                    _tone(view, ref, position, locked),
                )
                for position, block in enumerate(rung.blocks(side))
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
                locked=locked,
                action=_row_action(index, rung, view),
            )
        )
    return rows


def view_hints(view: SequenceLadderView) -> tuple[str, ...]:
    """Banner-Hinweise: Sprossen-Hinweise der Ansicht und je Altbestand-Doppelung eine Zeile.

    Die Gruppen bildet die Domain (`SequenceLadder.duplicate_groups`); hier steht nur der Text.
    """
    lines = list(view.notes)
    for group in view.duplicates:
        rungs = " und ".join(str(rung + 1) for rung in sorted({ref.rung for ref in group}))
        what = "Lernziel" if group[0].side is LadderSide.INHALT else "Kompetenz"
        lines.append(f"{what} „{group[0].text}“ steht mehrfach (Sprossen {rungs}) – bitte zusammenführen.")
    return tuple(lines)


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
    return card_key(BlockRef(0, LadderSide.INHALT, blocks[0].text)) if blocks else BoardCell(rung_key(0), LANE_INHALT)


def can_drop(ladder: SequenceLadder, key: str, slot: BoardSlot) -> bool:
    """Ablegen nur, wo es auch gelingt (§37): fragt die Domain, ob `MoveBlock` gelingen würde.

    So gelten dieselben Regeln wie beim Ablegen selbst (eigene Spalte, keine
    gesperrte Sprosse, Eindeutigkeit beim Bereichswechsel) – ohne Kopie. Die
    Einfügelinie erscheint nur dort, wo das Ablegen auch gelingt.
    """
    if slot.lane_key not in SIDE_BY_LANE:
        return False
    try:
        apply_ladder_operation(ladder, MoveBlock(block_ref(key), ladder_slot(slot)))
    except LadderRuleError:
        return False
    return True
