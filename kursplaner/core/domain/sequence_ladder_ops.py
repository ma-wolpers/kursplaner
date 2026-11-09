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

Gesperrte Sprossen (`SequenceLadder.locked_rungs`) nehmen nichts auf: Anlegen,
Verschieben und Ideen dorthin sind Regelfehler; Strg+↑/↓ und der Netz-Import
überspringen sie. Beim Verschieben wird die Eindeutigkeit nur geprüft, wenn der
Baustein seinen Eindeutigkeitsbereich wechselt – so bleiben Altbestand-Doppelungen
(`duplicate_groups`) verschieb-, umbenenn- und löschbar, neue entstehen nie.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Callable, Union

from kursplaner.core.domain.sequence_ladder import (
    COMPETENCE_SIDES,
    BlockRef,
    LadderBlock,
    LadderRuleError,
    LadderSide,
    LadderSlot,
    SequenceLadder,
    block_text_error,
    conflict_message,
    locked_message,
    uniqueness_scope,
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


def _require_open(ladder: SequenceLadder, rung: int) -> None:
    if ladder.is_locked(rung):
        raise LadderRuleError(locked_message(rung))


def _next_open(ladder: SequenceLadder, rung: int, step: int) -> int:
    """Erste nicht gesperrte Sprosse ab *rung* in Richtung *step*; ``-1`` unter der untersten."""
    while rung >= 0 and ladder.is_locked(rung):
        rung += step
    return rung


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
    """Baustein *ref* nach *target* bringen.

    Gesperrte Zielsprosse und – nur bei Wechsel des Eindeutigkeitsbereichs –
    eine Kollision im Zielbereich sind Regelfehler.
    """
    slot, block = _require(ladder, ref)
    if target.side is not slot.side:
        raise LadderRuleError("Bausteine bleiben in ihrer Spalte.")
    _require_open(ladder, target.rung)
    if uniqueness_scope(target.side, target.rung) != uniqueness_scope(slot.side, slot.rung):
        clash = ladder.conflict(target.side, target.rung, block.text, kompetenz_id=block.kompetenz_id, ignore=ref)
        if clash is not None:
            raise LadderRuleError(f"Sprosse {target.rung + 1}: {conflict_message(clash, target.side)}")
    moved = _insert(_remove(ladder, slot), target, block)
    return LadderApplyResult(moved, focus=BlockRef(target.rung, target.side, block.text))


def _add(ladder: SequenceLadder, op: AddBlock) -> LadderApplyResult:
    _require_open(ladder, op.slot.rung)
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
    """Eine Position höher/tiefer; über Sprossengrenzen hinweg, gesperrte Sprossen werden übersprungen."""
    slot, _block = _require(ladder, op.ref)
    count = len(ladder.rung(slot.rung).blocks(slot.side))
    if op.up and slot.index > 0:
        target = LadderSlot(slot.rung, slot.side, slot.index - 1)
    elif op.up:
        above = _next_open(ladder, slot.rung + 1, 1)
        target = LadderSlot(above, slot.side, len(ladder.rung(above).blocks(slot.side)))
    elif slot.index < count - 1:
        target = LadderSlot(slot.rung, slot.side, slot.index + 1)
    elif (below := _next_open(ladder, slot.rung - 1, -1)) >= 0:
        target = LadderSlot(below, slot.side, 0)
    else:
        return LadderApplyResult(ladder, focus=op.ref)
    return _relocate(ladder, op.ref, target)


def _import(ladder: SequenceLadder, op: ImportCompetences) -> LadderApplyResult:
    """Je Spalte in die erste offene Sprosse über der höchsten belegten."""
    notes: list[str] = []
    targets = {side: _next_open(ladder, ladder.highest_occupied(side) + 1, 1) for side in COMPETENCE_SIDES}
    for item in op.items:
        rung = targets[item.side]
        clash = ladder.conflict(item.side, rung, item.text, kompetenz_id=item.kompetenz_id)
        if clash is not None:
            notes.append(f"{item.kompetenz_id}: {conflict_message(clash, item.side)}")
            continue
        end = len(ladder.rung(rung).blocks(item.side))
        ladder = _insert(ladder, LadderSlot(rung, item.side, end), LadderBlock(item.text, item.kompetenz_id))
    return LadderApplyResult(ladder, tuple(notes))


MATERIAL_PREFIX = "+ "
"""Beginnt eine der ersten Zeilen des Ideenfelds damit, wird sie beim Übernehmen ein Material-Baustein."""


def split_material_lines(lines: Sequence[str]) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    """Trennt die führenden ``+ ``-Zeilen des Ideenfelds ab – die einzige Stelle dieser Regel.

    Nur der Block am Anfang zählt (Leerraum vor dem ``+`` ist erlaubt); die erste
    andere Zeile beendet ihn, spätere ``+ ``-Zeilen bleiben Ideen.

    Returns:
        ``(material, rest)`` – ``material`` als ``(Zeile wie getippt, Material-Text)``,
        ``rest`` die übrigen Zeilen in Reihenfolge.
    """
    count = 0
    while count < len(lines) and lines[count].lstrip().startswith(MATERIAL_PREFIX):
        count += 1
    material = tuple((line, line.lstrip()[len(MATERIAL_PREFIX) :].strip()) for line in lines[:count])
    return material, tuple(lines[count:])


def _ideas(ladder: SequenceLadder, op: SetIdeas) -> LadderApplyResult:
    """Ideenfeld übernehmen; führende ``+ ``-Zeilen werden Material unten im Stapel (direkt über den Ideen).

    Eine ``+ ``-Zeile, deren Text kein gültiger Material-Baustein ist (`block_text_error`,
    z. B. schon vorhanden), bleibt wörtlich im Ideenfeld und erzeugt einen Hinweis – nichts
    geht still verloren.
    """
    _require_open(ladder, op.rung)
    material, rest = split_material_lines(op.lines)
    kept: list[str] = []
    notes: list[str] = []
    side = LadderSide.MATERIAL
    for line, text in material:
        error = block_text_error(text, ladder, side=side, rung=op.rung)
        if error:
            kept.append(line)
            notes.append(f"„{line.strip()}“ bleibt im Ideenfeld: {error}")
            continue
        end = len(ladder.rung(op.rung).blocks(side))
        ladder = _insert(ladder, LadderSlot(op.rung, side, end), LadderBlock(text))
    lines = tuple(line.rstrip() for line in (*kept, *rest))
    while lines and not lines[-1]:
        lines = lines[:-1]
    rung = ladder.rung(op.rung)
    return LadderApplyResult(ladder.with_rung(op.rung, replace(rung, ideen=lines)), tuple(notes))


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
    if isinstance(op, SetIdeas) and split_material_lines(op.lines)[0]:
        return "Ideen/Material bearbeiten"
    return _REGISTRY[type(op)][1]
