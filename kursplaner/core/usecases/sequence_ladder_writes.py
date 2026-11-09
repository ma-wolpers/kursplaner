"""Schreibschritte der Sequenzleiter – **einzige** Stelle, die festlegt, was wohin geschrieben wird (§37).

Aus einem alten und neuen Stand (Einheiten-Inhalte und Ablage) entstehen nur die
nötigen Schreibvorgänge: Ziele/Kompetenzen einer Einheit über
`LessonEditUseCase.set_lesson_fields` (nur Unterricht), ihr ``## Ideen``-Abschnitt
über `LessonRepository.write_lesson_section`, die Ablage über
`SequencePlanRepository.write_ladder_ablage`. Genutzt vom Bearbeiten
(`EditSequenceLadderUseCase`) und vom Zuordnen einer Ablage-Sprosse
(`AssignAblageRungUseCase`); beide führen die Liste in **einem** Undo-Eintrag aus.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from kursplaner.core.domain.sequence_ladder import SequenceLadder
from kursplaner.core.domain.sequence_ladder_homes import (
    IDEEN_HEADING,
    UNIT_LESSON_TYPE,
    UnitContent,
    unit_ladder_fields,
)
from kursplaner.core.ports.repositories import LessonRepository, SequencePlanRepository
from kursplaner.core.usecases.lesson_edit_usecase import LessonEditUseCase


@dataclass(frozen=True)
class LadderWrite:
    """Ein geplanter Schreibvorgang auf *path*."""

    path: Path
    run: Callable[[], object]


@dataclass(frozen=True)
class LadderWriters:
    """Die drei Schreibwege der Leiter."""

    lesson_edit: LessonEditUseCase
    lessons: LessonRepository
    sequences: SequencePlanRepository


def ladder_writes(
    writers: LadderWriters,
    *,
    sequence_path: Path,
    old_units: Mapping[Path, UnitContent],
    new_units: Mapping[Path, UnitContent],
    old_ablage: SequenceLadder,
    new_ablage: SequenceLadder,
) -> list[LadderWrite]:
    """Schreibvorgänge nur für tatsächlich geänderte Teile.

    Args:
        writers: Schreibwege.
        sequence_path: Sequenzdatei (für die Ablage).
        old_units: Bisheriger Inhalt je Einheit (fehlend = leer, z. B. neu angelegt).
        new_units: Neuer Inhalt je zu prüfender Einheit.
        old_ablage: Bisherige Ablage (getrimmt).
        new_ablage: Neue Ablage (getrimmt).
    """
    writes: list[LadderWrite] = []
    for path, new in new_units.items():
        old = old_units.get(path, UnitContent())
        fields = unit_ladder_fields(new)
        if fields != unit_ladder_fields(old):
            set_fields = partial(writers.lesson_edit.set_lesson_fields, path, fields, require_type=UNIT_LESSON_TYPE)
            writes.append(LadderWrite(path, set_fields))
        if new.ideen != old.ideen:
            writes.append(
                LadderWrite(path, partial(writers.lessons.write_lesson_section, path, IDEEN_HEADING, new.ideen))
            )
    if new_ablage != old_ablage:
        write = partial(writers.sequences.write_ladder_ablage, sequence_path=sequence_path, ablage=new_ablage)
        writes.append(LadderWrite(sequence_path, write))
    return writes
