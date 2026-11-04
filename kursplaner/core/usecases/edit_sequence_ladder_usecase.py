"""Use Case: eine Sequenzleiter-Operation anwenden – ein Undo-Eintrag über alle betroffenen Dateien.

Einziger Schreibweg der Leiter (§4/§15, §37):

1. Einheiten und Ablage frisch lesen (`SequenceLadderSource`), Leiter zusammensetzen.
2. Operation über `apply_ladder_operation` anwenden.
3. Mit `split_ladder` auf die Speicherorte zurückverteilen.
4. Nur geänderte Dateien schreiben – Ziele/Kompetenzen einer Einheit
   (`LessonEditUseCase.set_lesson_fields`), ihr ``## Ideen``-Abschnitt, die Ablage
   der Sequenzdatei – in **einem** `run_tracked_file_action`: ein Undo-Eintrag,
   der alle Dateien zurücksetzt; schlägt ein Schreibvorgang fehl, werden alle
   Dateien byte-genau zurückgesetzt.

Regel-, Format- und Lesefehler schreiben nichts und erzeugen keinen Eintrag.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from kursplaner.core.domain.course_kc_context import CourseKcContext
from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.sequence_ladder import BlockRef, LadderRuleError, SequenceLadder
from kursplaner.core.domain.sequence_ladder_codec import LadderFormatError
from kursplaner.core.domain.sequence_ladder_homes import (
    IDEEN_HEADING,
    UNIT_LESSON_TYPE,
    LadderSplit,
    split_ladder,
    unit_goal_fields,
)
from kursplaner.core.domain.sequence_ladder_import import competence_import_items
from kursplaner.core.domain.sequence_ladder_ops import (
    ImportCompetences,
    LadderOperation,
    apply_ladder_operation,
    operation_label,
)
from kursplaner.core.domain.topic_sequence_runs import TopicSequenceRun
from kursplaner.core.ports.repositories import LessonRepository, SequencePlanRepository
from kursplaner.core.usecases.lesson_edit_usecase import LessonEditUseCase
from kursplaner.core.usecases.load_sequence_ladder_usecase import sequence_term_days
from kursplaner.core.usecases.sequence_ladder_source import LadderSnapshot, SequenceLadderSource
from kursplaner.core.usecases.tracked_write_usecase import TrackedWriteUseCase


@dataclass(frozen=True)
class EditSequenceLadderResult:
    """Ergebnis einer Leiter-Operation.

    Attributes:
        applied: ``True``, wenn Dateien geändert wurden (ein Undo-Eintrag).
        ladder: Aktuelle Leiter nach der Operation (bei Lesefehler ``None``).
        error: Nutzerlesbarer Grund, warum nichts geändert wurde.
        notes: Hinweise (z. B. beim Import übersprungene Kompetenzen).
        focus: Neuer Verweis des angelegten/bewegten Bausteins (für die Auswahl), sonst ``None``.
        written: Alle geschriebenen Dateien (Einheiten und/oder Sequenzdatei).
    """

    applied: bool
    ladder: SequenceLadder | None
    error: str | None = None
    notes: tuple[str, ...] = ()
    focus: BlockRef | None = None
    written: tuple[Path, ...] = ()


@dataclass(frozen=True)
class _Write:
    path: Path
    run: Callable[[], object]


class EditSequenceLadderUseCase:
    """Wendet Leiter-Operationen an und schreibt sie undo-fähig in Einheiten und Sequenzdatei."""

    def __init__(
        self,
        *,
        source: SequenceLadderSource,
        sequence_plan_repo: SequencePlanRepository,
        lesson_repo: LessonRepository,
        lesson_edit: LessonEditUseCase,
        tracked_write: TrackedWriteUseCase,
    ) -> None:
        """Initialisiert den Use Case mit Lesequelle, Schreibwegen und Undo-Orchestrierung."""
        self._source = source
        self._sequences = sequence_plan_repo
        self._lessons = lesson_repo
        self._lesson_edit = lesson_edit
        self._tracked_write = tracked_write

    def execute(
        self,
        *,
        sequence_path: Path,
        runs: Sequence[TopicSequenceRun],
        day_columns: Sequence[DayColumn],
        operation: LadderOperation,
        notes: tuple[str, ...] = (),
    ) -> EditSequenceLadderResult:
        """Liest, wendet *operation* an und schreibt die geänderten Speicherorte.

        Args:
            sequence_path: Sequenzdatei.
            runs: Alle Läufe mit diesem Pfad (bestimmen die Termine).
            day_columns: Alle Tagesspalten des geöffneten Plans.
            operation: Die Operation (siehe `sequence_ladder_ops`).
            notes: Zusätzliche Hinweise, die dem Ergebnis vorangestellt werden.
        """
        try:
            snapshot = self._source.read(sequence_path, sequence_term_days(day_columns, runs))
        except (LadderFormatError, OSError) as exc:
            return EditSequenceLadderResult(False, None, str(exc), notes)
        try:
            result = apply_ladder_operation(snapshot.ladder, operation)
            split = split_ladder(result.ladder, snapshot.homes, snapshot.units)
        except LadderRuleError as exc:
            return EditSequenceLadderResult(False, snapshot.ladder, str(exc), notes)
        all_notes = notes + result.notes
        writes = self._writes(sequence_path, snapshot, split)
        if not writes:
            return EditSequenceLadderResult(False, snapshot.ladder, None, all_notes, result.focus)
        paths = list(dict.fromkeys(write.path for write in writes))
        try:
            self._tracked_write.run_tracked_file_action(
                label=operation_label(operation),
                paths=paths,
                action=lambda: [write.run() for write in writes],
            )
        except (OSError, RuntimeError, ValueError) as exc:
            error = f"Nichts gespeichert – alle Dateien sind unverändert: {exc}"
            return EditSequenceLadderResult(False, snapshot.ladder, error, all_notes)
        return EditSequenceLadderResult(True, result.ladder, None, all_notes, result.focus, tuple(paths))

    def _writes(self, sequence_path: Path, snapshot: LadderSnapshot, split: LadderSplit) -> list[_Write]:
        """Geplante Schreibvorgänge, nur für tatsächlich geänderte Teile."""
        writes: list[_Write] = []
        for path, new in split.units.items():
            old = snapshot.units[path]
            fields = unit_goal_fields(new)
            if fields != unit_goal_fields(old):
                write_fields = partial(self._lesson_edit.set_lesson_fields, path, fields, require_type=UNIT_LESSON_TYPE)
                writes.append(_Write(path, write_fields))
            if new.ideen != old.ideen:
                writes.append(_Write(path, partial(self._lessons.write_lesson_section, path, IDEEN_HEADING, new.ideen)))
        if split.ablage != snapshot.ablage.trimmed():
            writes.append(
                _Write(
                    sequence_path,
                    lambda: self._sequences.write_ladder_ablage(sequence_path=sequence_path, ablage=split.ablage),
                )
            )
        return writes

    def import_competences(
        self,
        *,
        sequence_path: Path,
        runs: Sequence[TopicSequenceRun],
        day_columns: Sequence[DayColumn],
        snapshot: KompetenzGraphSnapshot,
        kompetenz_ids: Iterable[str],
        kc_context: CourseKcContext = CourseKcContext(),
    ) -> EditSequenceLadderResult:
        """Übernimmt Kompetenzen aus dem Netz als ein Undo-Schritt (Spalte aus der Bereichsart).

        Nicht übernehmbare IDs (unbekannt, ohne Primärbereich, inhaltsbezogene
        Hauptkompetenz im *kc_context* des Kurses) und übersprungene Duplikate
        stehen in ``notes``.
        """
        items, problems = competence_import_items(snapshot, kompetenz_ids, kc_context)
        if not items:
            return EditSequenceLadderResult(False, None, "Keine übernehmbaren Kompetenzen markiert.", problems)
        return self.execute(
            sequence_path=sequence_path,
            runs=runs,
            day_columns=day_columns,
            operation=ImportCompetences(items),
            notes=problems,
        )
