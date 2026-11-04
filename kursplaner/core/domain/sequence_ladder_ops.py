"""Sequenzleiter-Operationen: ein Operation-Objekt pro Nutzeraktion, ein Dispatcher.

Jede Aktion im Leiter-Editor (anlegen, einfügen, löschen, umbenennen,
verschieben, Strg+Pfeil, Netz-Import, Ideen) ist ein unveränderliches
Operation-Objekt. `apply_ladder_operation` ist die einzige Stelle, die
Operationen auf eine Leiter anwendet (Registry), `operation_label` die einzige
Quelle der Undo-Beschriftung. Bausteine werden immer per Text referenziert,
nie per Index: der Use Case liest vor jeder Operation neu, eine zwischenzeitlich
extern geänderte Datei trifft so nie den falschen Baustein.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Union

from kursplaner.core.domain.sequence_ladder import (
    LadderBlock,
    LadderRuleError,
    LadderRung,
    LadderSide,
    LadderSlot,
    SequenceLadder,
    block_key,
    block_text_error,
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

    text: str


@dataclass(frozen=True)
class RenameBlock:
    """Eigenen Baustein umbenennen (Netz-Bausteine sind gesperrt)."""

    text: str
    new_text: str


@dataclass(frozen=True)
class MoveBlock:
    """Baustein an *target* verschieben (gleiche Spalte; Index gilt nach dem Herausnehmen)."""

    text: str
    target: LadderSlot


@dataclass(frozen=True)
class StepBlock:
    """Strg+↑/↓: eine Position höher bzw. tiefer, über Sprossengrenzen hinweg."""

    text: str
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
    """Ergebnis einer Operation: neue Leiter (ohne leere Sprossen oben) und Hinweise für die Nutzerin."""

    ladder: SequenceLadder
    notes: tuple[str, ...] = ()


def _require(ladder: SequenceLadder, text: str) -> tuple[LadderSlot, LadderBlock]:
    found = ladder.locate(text)
    if found is None:
        raise LadderRuleError(f"Baustein „{text}“ nicht gefunden (Datei wurde zwischenzeitlich geändert?).")
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


def _add(ladder: SequenceLadder, op: AddBlock) -> LadderApplyResult:
    error = block_text_error(op.text, ladder)
    if error:
        raise LadderRuleError(error)
    return LadderApplyResult(_insert(ladder, op.slot, LadderBlock(op.text.strip())))


def _remove_op(ladder: SequenceLadder, op: RemoveBlock) -> LadderApplyResult:
    slot, _block = _require(ladder, op.text)
    return LadderApplyResult(_remove(ladder, slot))


def _rename(ladder: SequenceLadder, op: RenameBlock) -> LadderApplyResult:
    slot, block = _require(ladder, op.text)
    if block.is_network:
        raise LadderRuleError("Bausteine aus dem Kompetenznetz können nicht umbenannt werden.")
    error = block_text_error(op.new_text, ladder, ignore=block.text)
    if error:
        raise LadderRuleError(error)
    renamed = _remove(ladder, slot)
    return LadderApplyResult(_insert(renamed, slot, LadderBlock(op.new_text.strip())))


def _move(ladder: SequenceLadder, op: MoveBlock) -> LadderApplyResult:
    slot, block = _require(ladder, op.text)
    if op.target.side is not slot.side:
        raise LadderRuleError("Bausteine bleiben in ihrer Spalte.")
    return LadderApplyResult(_insert(_remove(ladder, slot), op.target, block))


def _step(ladder: SequenceLadder, op: StepBlock) -> LadderApplyResult:
    slot, block = _require(ladder, op.text)
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
        return LadderApplyResult(ladder)
    return LadderApplyResult(_insert(_remove(ladder, slot), target, block))


def _import(ladder: SequenceLadder, op: ImportCompetences) -> LadderApplyResult:
    notes: list[str] = []
    targets = {side: ladder.highest_occupied(side) + 1 for side in LadderSide}
    seen: set[str] = set()
    for item in op.items:
        if ladder.contains_kompetenz(item.kompetenz_id):
            notes.append(f"{item.kompetenz_id} liegt bereits auf der Leiter.")
            continue
        if ladder.locate(item.text) is not None or block_key(item.text) in seen:
            notes.append(f"{item.kompetenz_id}: Ein Baustein „{item.text}“ existiert bereits.")
            continue
        seen.add(block_key(item.text))
        rung = targets[item.side]
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
    return LadderApplyResult(result.ladder.trimmed(), result.notes)


def operation_label(op: LadderOperation) -> str:
    """Undo-Beschriftung einer Operation (höchstens vier Wörter)."""
    if isinstance(op, AddBlock) and op.pasted:
        return "Baustein einfügen"
    return _REGISTRY[type(op)][1]
