"""Sequenzleiter-Operationen: ein Operation-Objekt pro Nutzeraktion, ein Dispatcher.

Jede Aktion im Leiter-Editor (anlegen, einfügen, löschen, umbenennen,
verschieben, Strg+Pfeil, Netz-Import, Ideen) ist ein unveränderliches
Operation-Objekt. `apply_ladder_operation` ist die einzige Stelle, die
Operationen auf eine Leiter anwendet (Registry), `operation_label` die einzige
Quelle der Undo-Beschriftung. Bausteine werden immer per `BlockRef` (Sprosse,
Spalte, Text) referenziert, nie per Index: der Use Case liest vor jeder
Operation neu, eine zwischenzeitlich extern geänderte Datei trifft so nie den
falschen Baustein. Jede Operation, die einen Baustein anlegt oder bewegt, meldet
seinen neuen Verweis als `focus` (für die Auswahl im Editor).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Union

from kursplaner.core.domain.sequence_ladder import (
    BlockRef,
    LadderBlock,
    LadderRuleError,
    LadderRung,
    LadderSide,
    LadderSlot,
    SequenceLadder,
    block_text_error,
    conflict_message,
)


@dataclass(frozen=True)
class AddBlock:
    """Eigenen Baustein an *slot* anlegen ("+": unten in der Zelle; Strg+V: über dem gewählten)."""

    slot: LadderSlot
    text: str
    pasted: bool = False


@dataclass(frozen=True)
class RemoveBlock:
    """Baustein löschen."""

    ref: BlockRef


@dataclass(frozen=True)
class RenameBlock:
    """Eigenen Baustein umbenennen (Netz-Bausteine sind gesperrt)."""

    ref: BlockRef
    new_text: str


@dataclass(frozen=True)
class MoveBlock:
    """Baustein an *target* verschieben (gleiche Spalte; Index gilt nach dem Herausnehmen)."""

    ref: BlockRef
    target: LadderSlot


@dataclass(frozen=True)
class StepBlock:
    """Strg+↑/↓: eine Position höher bzw. tiefer, über Sprossengrenzen hinweg."""

    ref: BlockRef
    up: bool


@dataclass(frozen=True)
class ImportedCompetence:
    """Ein zu übernehmender Netz-Baustein (Text bereits im Dateiformat-Rundweg normalisiert)."""

    kompetenz_id: str
    text: str
    side: LadderSide


@dataclass(frozen=True)
class ImportCompetences:
    """Kompetenzen aus dem Netz je Spalte gemeinsam in die Sprosse über der höchsten belegten legen."""

    items: tuple[ImportedCompetence, ...]


@dataclass(frozen=True)
class SetIdeas:
    """Ideenfeld einer Sprosse ersetzen (eine Zeile pro Eintrag)."""

    rung: int
    lines: tuple[str, ...]


LadderOperation = Union[AddBlock, RemoveBlock, RenameBlock, MoveBlock, StepBlock, ImportCompetences, SetIdeas]


@dataclass(frozen=True)
class LadderApplyResult:
    """Ergebnis einer Operation.

    Attributes:
        ladder: Neue Leiter (ohne leere Sprossen oben).
        notes: Hinweise für die Nutzerin (z. B. übersprungene Kompetenzen).
        focus: Neuer Verweis des angelegten/bewegten Bausteins, sonst ``None``.
    """

    ladder: SequenceLadder
    notes: tuple[str, ...] = ()
    focus: BlockRef | None = None


def _require(ladder: SequenceLadder, ref: BlockRef) -> tuple[LadderSlot, LadderBlock]:
    found = ladder.find(ref)
    if found is None:
        raise LadderRuleError(f"Baustein „{ref.text}“ nicht gefunden (Datei wurde zwischenzeitlich geändert?).")
    return found


def _remove(ladder: SequenceLadder, slot: LadderSlot) -> SequenceLadder:
    rung = ladder.rung(slot.rung)
    blocks = rung.blocks(slot.side)
    return ladder.with_rung(slot.rung, rung.with_blocks(slot.side, blocks[: slot.index] + blocks[slot.index + 1 :]))


def _insert(ladder: SequenceLadder, slot: LadderSlot, block: LadderBlock) -> SequenceLadder:
    rung = ladder.rung(slot.rung)
    blocks = rung.blocks(slot.side)
    index = min(max(0, slot.index), len(blocks))
    return ladder.with_rung(slot.rung, rung.with_blocks(slot.side, blocks[:index] + (block,) + blocks[index:]))


def _relocate(ladder: SequenceLadder, ref: BlockRef, target: LadderSlot) -> LadderApplyResult:
    """Baustein *ref* nach *target* bringen; Kollision im Zielbereich ist ein Regelfehler."""
    slot, block = _require(ladder, ref)
    if target.side is not slot.side:
        raise LadderRuleError("Bausteine bleiben in ihrer Spalte.")
    clash = ladder.conflict(target.side, target.rung, block.text, kompetenz_id=block.kompetenz_id, ignore=ref)
    if clash is not None:
        raise LadderRuleError(f"Sprosse {target.rung + 1}: {conflict_message(clash, target.side)}")
    moved = _insert(_remove(ladder, slot), target, block)
    return LadderApplyResult(moved, focus=BlockRef(target.rung, target.side, block.text))


def _add(ladder: SequenceLadder, op: AddBlock) -> LadderApplyResult:
    error = block_text_error(op.text, ladder, side=op.slot.side, rung=op.slot.rung)
    if error:
        raise LadderRuleError(error)
    text = op.text.strip()
    return LadderApplyResult(
        _insert(ladder, op.slot, LadderBlock(text)), focus=BlockRef(op.slot.rung, op.slot.side, text)
    )


def _remove_op(ladder: SequenceLadder, op: RemoveBlock) -> LadderApplyResult:
    slot, _block = _require(ladder, op.ref)
    return LadderApplyResult(_remove(ladder, slot))


def _rename(ladder: SequenceLadder, op: RenameBlock) -> LadderApplyResult:
    slot, block = _require(ladder, op.ref)
    if block.is_network:
        raise LadderRuleError("Bausteine aus dem Kompetenznetz können nicht umbenannt werden.")
    error = block_text_error(op.new_text, ladder, side=slot.side, rung=slot.rung, ignore=op.ref)
    if error:
        raise LadderRuleError(error)
    text = op.new_text.strip()
    renamed = _insert(_remove(ladder, slot), slot, LadderBlock(text))
    return LadderApplyResult(renamed, focus=BlockRef(slot.rung, slot.side, text))


def _move(ladder: SequenceLadder, op: MoveBlock) -> LadderApplyResult:
    return _relocate(ladder, op.ref, op.target)


def _step(ladder: SequenceLadder, op: StepBlock) -> LadderApplyResult:
    slot, _block = _require(ladder, op.ref)
    count = len(ladder.rung(slot.rung).blocks(slot.side))
    if op.up:
        target = (
            LadderSlot(slot.rung, slot.side, slot.index - 1)
            if slot.index > 0
            else LadderSlot(slot.rung + 1, slot.side, len(ladder.rung(slot.rung + 1).blocks(slot.side)))
        )
    elif slot.index < count - 1:
        target = LadderSlot(slot.rung, slot.side, slot.index + 1)
    elif slot.rung > 0:
        target = LadderSlot(slot.rung - 1, slot.side, 0)
    else:
        return LadderApplyResult(ladder, focus=op.ref)
    return _relocate(ladder, op.ref, target)


def _import(ladder: SequenceLadder, op: ImportCompetences) -> LadderApplyResult:
    notes: list[str] = []
    targets = {side: ladder.highest_occupied(side) + 1 for side in LadderSide}
    for item in op.items:
        rung = targets[item.side]
        clash = ladder.conflict(item.side, rung, item.text, kompetenz_id=item.kompetenz_id)
        if clash is not None:
            notes.append(f"{item.kompetenz_id}: {conflict_message(clash, item.side)}")
            continue
        end = len(ladder.rung(rung).blocks(item.side))
        ladder = _insert(ladder, LadderSlot(rung, item.side, end), LadderBlock(item.text, item.kompetenz_id))
    return LadderApplyResult(ladder, tuple(notes))


def _ideas(ladder: SequenceLadder, op: SetIdeas) -> LadderApplyResult:
    lines = tuple(line.rstrip() for line in op.lines)
    while lines and not lines[-1]:
        lines = lines[:-1]
    rung = ladder.rung(op.rung)
    return LadderApplyResult(ladder.with_rung(op.rung, LadderRung(rung.inhalt, rung.prozess, lines)))


_REGISTRY: dict[type, tuple[Callable[..., LadderApplyResult], str]] = {
    AddBlock: (_add, "Baustein anlegen"),
    RemoveBlock: (_remove_op, "Baustein löschen"),
    RenameBlock: (_rename, "Baustein umbenennen"),
    MoveBlock: (_move, "Baustein verschieben"),
    StepBlock: (_step, "Baustein verschieben"),
    ImportCompetences: (_import, "Kompetenzen übernehmen"),
    SetIdeas: (_ideas, "Ideen bearbeiten"),
}


def apply_ladder_operation(ladder: SequenceLadder, op: LadderOperation) -> LadderApplyResult:
    """Wendet *op* an; Ergebnis-Leiter ohne leere Sprossen am oberen Ende.

    Raises:
        LadderRuleError: Die Operation verletzt eine Regel (Text nutzerlesbar).
    """
    handler, _label = _REGISTRY[type(op)]
    result = handler(ladder, op)
    return LadderApplyResult(result.ladder.trimmed(), result.notes, result.focus)


def operation_label(op: LadderOperation) -> str:
    """Undo-Beschriftung einer Operation (höchstens vier Wörter)."""
    if isinstance(op, AddBlock) and op.pasted:
        return "Baustein einfügen"
    return _REGISTRY[type(op)][1]
