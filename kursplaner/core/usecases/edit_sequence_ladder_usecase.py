"""Use Case: eine Sequenzleiter-Operation anwenden – genau ein Schreibvorgang, genau ein Undo-Eintrag.

Einziger Schreibweg der Leiter (§4/§15, §37): Datei neu lesen, Operation über
`apply_ladder_operation` anwenden, nur bei echter Änderung über
`TrackedWriteUseCase.run_tracked_file_action` schreiben. Regel- und
Formatfehler schreiben nichts und erzeugen keinen Eintrag.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.sequence_ladder import LadderRuleError, SequenceLadder
from kursplaner.core.domain.sequence_ladder_codec import LadderFormatError
from kursplaner.core.domain.sequence_ladder_import import competence_import_items
from kursplaner.core.domain.sequence_ladder_ops import (
    ImportCompetences,
    LadderOperation,
    apply_ladder_operation,
    operation_label,
)
from kursplaner.core.ports.repositories import SequencePlanRepository
from kursplaner.core.usecases.tracked_write_usecase import TrackedWriteUseCase


@dataclass(frozen=True)
class EditSequenceLadderResult:
    """Ergebnis einer Leiter-Operation.

    Attributes:
        applied: ``True``, wenn die Datei geändert wurde (ein Undo-Eintrag).
        ladder: Aktuelle Leiter nach der Operation (bei Formatfehler ``None``).
        error: Nutzerlesbarer Grund, warum nichts geändert wurde.
        notes: Hinweise (z. B. beim Import übersprungene Kompetenzen).
    """

    applied: bool
    ladder: SequenceLadder | None
    error: str | None = None
    notes: tuple[str, ...] = ()


class EditSequenceLadderUseCase:
    """Wendet Leiter-Operationen an und schreibt sie undo-fähig."""

    def __init__(self, sequence_plan_repo: SequencePlanRepository, tracked_write: TrackedWriteUseCase) -> None:
        """Initialisiert den Use Case mit Repository und Undo-Orchestrierung."""
        self._repo = sequence_plan_repo
        self._tracked_write = tracked_write

    def execute(
        self, *, sequence_path: Path, operation: LadderOperation, notes: tuple[str, ...] = ()
    ) -> EditSequenceLadderResult:
        """Liest, wendet *operation* an und schreibt bei Änderung.

        Args:
            sequence_path: Sequenzdatei.
            operation: Die Operation (siehe `sequence_ladder_ops`).
            notes: Zusätzliche Hinweise, die dem Ergebnis vorangestellt werden.
        """
        try:
            ladder = self._repo.read_sequence_ladder(sequence_path)
        except LadderFormatError as exc:
            return EditSequenceLadderResult(False, None, str(exc), notes)
        try:
            result = apply_ladder_operation(ladder, operation)
        except LadderRuleError as exc:
            return EditSequenceLadderResult(False, ladder, str(exc), notes)
        all_notes = notes + result.notes
        if result.ladder == ladder.trimmed():
            return EditSequenceLadderResult(False, ladder, None, all_notes)
        self._tracked_write.run_tracked_file_action(
            label=operation_label(operation),
            paths=[sequence_path],
            action=lambda: self._repo.write_sequence_ladder(sequence_path=sequence_path, ladder=result.ladder),
        )
        return EditSequenceLadderResult(True, result.ladder, None, all_notes)

    def import_competences(
        self, *, sequence_path: Path, snapshot: KompetenzGraphSnapshot, kompetenz_ids: Iterable[str]
    ) -> EditSequenceLadderResult:
        """Übernimmt Kompetenzen aus dem Netz als ein Undo-Schritt (Spalte aus der Bereichsart).

        Nicht übernehmbare IDs (unbekannt, ohne Primärbereich) und übersprungene
        Duplikate stehen in ``notes``.
        """
        items, problems = competence_import_items(snapshot, kompetenz_ids)
        if not items:
            return EditSequenceLadderResult(False, None, "Keine übernehmbaren Kompetenzen markiert.", problems)
        return self.execute(sequence_path=sequence_path, operation=ImportCompetences(items), notes=problems)
