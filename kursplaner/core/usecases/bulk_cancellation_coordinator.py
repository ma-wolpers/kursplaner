from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Sequence

from kursplaner.core.domain.row_identity import ResolutionStatus
from kursplaner.core.domain.school_wide_cancellation import CourseApplicationLedger
from kursplaner.core.ports.repositories import ConflictContext, ConflictDecision, ConflictKind, ConflictResolution
from kursplaner.core.usecases.school_wide_cancellation_apply_usecase import SchoolWideCancellationApplyUseCase
from kursplaner.core.usecases.school_wide_cancellation_revert_usecase import (
    RevertIssue,
    SchoolWideCancellationRevertUseCase,
)


class OperationKind(Enum):
    """Art einer geplanten Kurs-Operation innerhalb eines Bulk-Vorgangs."""

    APPLY = "apply"
    REVERT = "revert"


class CourseOperationOutcome(Enum):
    """Endergebnis einer einzelnen Kurs-Operation nach Abschluss des Bulk-Vorgangs."""

    SUCCESS = "success"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class PlannedOperation:
    """Eine geplante Kurs-Operation (Apply oder Revert) innerhalb eines Bulk-Vorgangs.

    `date_from`/`date_to`/`reason` sind immer die Parameter des zugrunde
    liegenden Entrys - auch bei `REVERT` werden sie mitgefuehrt, damit ein
    spaeteres Rollback per erneutem Apply exakt dieselben Parameter nutzen
    kann. `ledger` ist bei `REVERT` das zurueckzunehmende Ledger, bei `APPLY`
    ungenutzt.
    """

    kind: OperationKind
    markdown_path: Path
    course_label: str
    date_from: date
    date_to: date
    reason: str
    ledger: CourseApplicationLedger | None = None


@dataclass(frozen=True)
class CourseOperationResult:
    """Endergebnis einer einzelnen Kurs-Operation."""

    markdown_path: Path
    kind: OperationKind
    outcome: CourseOperationOutcome
    ledger: CourseApplicationLedger | None = None


@dataclass(frozen=True)
class BulkOperationResult:
    """Gesamtergebnis eines Bulk-Vorgangs ueber mehrere Kurse."""

    aborted: bool
    course_results: tuple[CourseOperationResult, ...]


class BulkCancellationCoordinator:
    """Fuehrt eine Liste geplanter Kurs-Operationen sequenziell aus, mit zentraler Fehlerbehandlung.

    Einzige Stelle im Feature mit Fehler-/Konflikt-/Rollback-Logik - Apply und
    Revert selbst sind single-course und entscheidungsfrei (siehe
    `SchoolWideCancellationApplyUseCase`/`SchoolWideCancellationRevertUseCase`).
    Haelt waehrend der Ausfuehrung einen In-Memory-Undo-Stack bereits
    erfolgreicher Schritte fuer *diesen* Vorgang; entscheidet sich die
    Nutzer:in fuer "gesamten Vorgang zurueckrollen", wird dieser Stack in
    umgekehrter Reihenfolge abgearbeitet (Apply-Schritte per Revert
    rueckgaengig, Revert-Schritte per erneutem Apply mit denselben
    Parametern rueckgaengig) - Rollback ist damit reine Wiederverwendung von
    Apply/Revert, keine dritte Implementierung derselben Logik.
    """

    def __init__(
        self,
        apply_uc: SchoolWideCancellationApplyUseCase,
        revert_uc: SchoolWideCancellationRevertUseCase,
    ) -> None:
        """Nimmt die single-course Apply-/Revert-Usecases entgegen, die orchestriert werden."""
        self._apply_uc = apply_uc
        self._revert_uc = revert_uc

    def run(self, operations: Sequence[PlannedOperation], *, decide: ConflictDecision) -> BulkOperationResult:
        """Fuehrt alle geplanten Operationen der Reihe nach aus.

        Bei einer Rollback-Entscheidung wird der bisherige Vorgang komplett
        zurueckgerollt und `aborted=True` geliefert - die bereits erfolgten
        `course_results` spiegeln dann nur, was vor dem Rollback erreicht war,
        nicht den (zurueckgerollten) Endzustand.
        """
        undo_stack: list[PlannedOperation] = []
        results: list[CourseOperationResult] = []

        for operation in operations:
            outcome = self._run_one(operation, decide=decide, undo_stack=undo_stack)
            if outcome is None:
                self._rollback(undo_stack, decide=decide)
                return BulkOperationResult(aborted=True, course_results=tuple(results))
            results.append(outcome)

        return BulkOperationResult(aborted=False, course_results=tuple(results))

    def _run_one(
        self,
        operation: PlannedOperation,
        *,
        decide: ConflictDecision,
        undo_stack: list[PlannedOperation],
    ) -> CourseOperationResult | None:
        """Fuehrt eine Operation aus (inkl. Retry-/Trotzdem-Schleife). `None` = Rollback gewuenscht."""
        force_warnings = False
        while True:
            try:
                if operation.kind is OperationKind.APPLY:
                    return self._run_apply(operation, undo_stack=undo_stack)
                step_result = self._run_revert(operation, undo_stack=undo_stack, force_warnings=force_warnings)
            except Exception as exc:  # technischer Fehler (I/O, unerwartete Struktur, ...)
                step_result = ConflictContext(
                    kind=ConflictKind.ERROR, title=f"Fehler bei {operation.course_label}", message=str(exc)
                )

            if isinstance(step_result, CourseOperationResult):
                return step_result

            resolution = decide(step_result)
            if resolution is ConflictResolution.RETRY:
                continue
            if resolution is ConflictResolution.SKIP:
                return CourseOperationResult(operation.markdown_path, operation.kind, CourseOperationOutcome.SKIPPED)
            if resolution is ConflictResolution.ROLLBACK:
                return None
            if resolution is ConflictResolution.PROCEED and step_result.kind is ConflictKind.WARNING:
                force_warnings = True
                continue
            return CourseOperationResult(operation.markdown_path, operation.kind, CourseOperationOutcome.SKIPPED)

    def _run_apply(
        self, operation: PlannedOperation, *, undo_stack: list[PlannedOperation]
    ) -> CourseOperationResult:
        ledger = self._apply_uc.execute(
            markdown_path=operation.markdown_path,
            date_from=operation.date_from,
            date_to=operation.date_to,
            reason=operation.reason,
        )
        if ledger.moves:
            undo_stack.append(self._inverse(operation, ledger))
        return CourseOperationResult(operation.markdown_path, operation.kind, CourseOperationOutcome.SUCCESS, ledger)

    def _run_revert(
        self,
        operation: PlannedOperation,
        *,
        undo_stack: list[PlannedOperation],
        force_warnings: bool,
    ) -> CourseOperationResult | ConflictContext:
        assert operation.ledger is not None
        revert_outcome = self._revert_uc.execute(
            markdown_path=operation.markdown_path, ledger=operation.ledger, force_warnings=force_warnings
        )
        if revert_outcome.issues:
            return self._conflict_context(operation, revert_outcome.issues)
        if revert_outcome.reverted_move_count:
            undo_stack.append(self._inverse(operation, operation.ledger))
        return CourseOperationResult(operation.markdown_path, operation.kind, CourseOperationOutcome.SUCCESS)

    def _rollback(self, undo_stack: list[PlannedOperation], *, decide: ConflictDecision) -> None:
        """Arbeitet den Undo-Stack bestmoeglich in umgekehrter Reihenfolge ab."""
        while undo_stack:
            inverse_operation = undo_stack.pop()
            self._run_one(inverse_operation, decide=decide, undo_stack=[])

    @staticmethod
    def _inverse(operation: PlannedOperation, ledger: CourseApplicationLedger) -> PlannedOperation:
        inverse_kind = OperationKind.REVERT if operation.kind is OperationKind.APPLY else OperationKind.APPLY
        return PlannedOperation(
            kind=inverse_kind,
            markdown_path=operation.markdown_path,
            course_label=operation.course_label,
            date_from=operation.date_from,
            date_to=operation.date_to,
            reason=operation.reason,
            ledger=ledger if inverse_kind is OperationKind.REVERT else None,
        )

    @staticmethod
    def _conflict_context(operation: PlannedOperation, issues: Sequence[RevertIssue]) -> ConflictContext:
        has_error = any(issue.resolution.status is ResolutionStatus.ERROR for issue in issues)
        detail = "; ".join(issue.resolution.detail for issue in issues if issue.resolution.detail)
        return ConflictContext(
            kind=ConflictKind.ERROR if has_error else ConflictKind.WARNING,
            title=f"Konflikt bei {operation.course_label}",
            message=detail or "Unbekannte Abweichung.",
        )
