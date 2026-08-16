from __future__ import annotations

from datetime import date
from pathlib import Path

from kursplaner.core.domain.row_identity import MoveResolution, ResolutionStatus, SourceResolution, TargetResolution
from kursplaner.core.domain.school_wide_cancellation import CourseApplicationLedger, RowLocation, UnitMove
from kursplaner.core.ports.repositories import ConflictKind, ConflictResolution
from kursplaner.core.usecases.bulk_cancellation_coordinator import (
    BulkCancellationCoordinator,
    CourseOperationOutcome,
    OperationKind,
    PlannedOperation,
)
from kursplaner.core.usecases.school_wide_cancellation_revert_usecase import RevertIssue, RevertOutcome

_PATH_A = Path("a.md")
_PATH_B = Path("b.md")

_LEDGER = CourseApplicationLedger(
    moves=(UnitMove(source=RowLocation(date="06-01-26", position_in_date=0), reference=None, target=None),)
)


def _op_apply(path: Path) -> PlannedOperation:
    return PlannedOperation(
        kind=OperationKind.APPLY,
        markdown_path=path,
        course_label=path.stem,
        date_from=date(2026, 1, 6),
        date_to=date(2026, 1, 6),
        reason="Wandertag",
    )


def _op_revert(path: Path, ledger: CourseApplicationLedger = _LEDGER) -> PlannedOperation:
    return PlannedOperation(
        kind=OperationKind.REVERT,
        markdown_path=path,
        course_label=path.stem,
        date_from=date(2026, 1, 6),
        date_to=date(2026, 1, 6),
        reason="Wandertag",
        ledger=ledger,
    )


class _FakeApplyUseCase:
    def __init__(self, *, raise_for: set[Path] | None = None) -> None:
        self._raise_for = set(raise_for or ())
        self.calls: list[Path] = []

    def execute(self, *, markdown_path: Path, date_from, date_to, reason):
        self.calls.append(markdown_path)
        if markdown_path in self._raise_for:
            raise RuntimeError("technischer Fehler")
        return _LEDGER


class _FlakyOnceApplyUseCase:
    """Wirft beim ersten Aufruf, gelingt danach - fuer Retry-Tests."""

    def __init__(self) -> None:
        self.call_count = 0

    def execute(self, *, markdown_path: Path, date_from, date_to, reason):
        self.call_count += 1
        if self.call_count == 1:
            raise RuntimeError("transient")
        return _LEDGER


class _FakeRevertUseCase:
    def __init__(self, *, issues_by_path: dict[Path, list[RevertIssue]] | None = None) -> None:
        self._issues_by_path = issues_by_path or {}
        self.calls: list[tuple[Path, bool]] = []

    def execute(self, *, markdown_path: Path, ledger, force_warnings: bool = False):
        self.calls.append((markdown_path, force_warnings))
        issues = () if force_warnings else tuple(self._issues_by_path.get(markdown_path, []))
        return RevertOutcome(reverted_move_count=0 if issues else 1, issues=issues)


def _warning_issue() -> RevertIssue:
    resolution = MoveResolution(
        ResolutionStatus.WARNING,
        SourceResolution(ResolutionStatus.MATCH, 0),
        TargetResolution(ResolutionStatus.WARNING, 1, detail="Referenz geändert"),
        "Referenz geändert",
    )
    return RevertIssue(move=_LEDGER.moves[0], resolution=resolution)


def _error_issue() -> RevertIssue:
    resolution = MoveResolution(
        ResolutionStatus.ERROR,
        SourceResolution(ResolutionStatus.ERROR, None, "nicht gefunden"),
        TargetResolution(ResolutionStatus.ERROR, None),
        "nicht gefunden",
    )
    return RevertIssue(move=_LEDGER.moves[0], resolution=resolution)


def _coordinator(apply_uc=None, revert_uc=None) -> BulkCancellationCoordinator:
    return BulkCancellationCoordinator(apply_uc=apply_uc or _FakeApplyUseCase(), revert_uc=revert_uc or _FakeRevertUseCase())


def test_all_operations_succeed():
    coordinator = _coordinator()
    result = coordinator.run([_op_apply(_PATH_A), _op_apply(_PATH_B)], decide=lambda ctx: ConflictResolution.SKIP)
    assert not result.aborted
    assert all(r.outcome is CourseOperationOutcome.SUCCESS for r in result.course_results)


def test_retry_then_success():
    apply_uc = _FlakyOnceApplyUseCase()
    coordinator = _coordinator(apply_uc=apply_uc)
    result = coordinator.run([_op_apply(_PATH_A)], decide=lambda ctx: ConflictResolution.RETRY)

    assert not result.aborted
    assert result.course_results[0].outcome is CourseOperationOutcome.SUCCESS
    assert apply_uc.call_count == 2


def test_error_then_skip_continues_with_remaining_operations():
    apply_uc = _FakeApplyUseCase(raise_for={_PATH_A})
    coordinator = _coordinator(apply_uc=apply_uc)
    result = coordinator.run([_op_apply(_PATH_A), _op_apply(_PATH_B)], decide=lambda ctx: ConflictResolution.SKIP)

    assert not result.aborted
    assert result.course_results[0].outcome is CourseOperationOutcome.SKIPPED
    assert result.course_results[1].outcome is CourseOperationOutcome.SUCCESS


def test_rollback_undoes_already_applied_operations():
    apply_uc = _FakeApplyUseCase(raise_for={_PATH_B})
    revert_uc = _FakeRevertUseCase()
    coordinator = _coordinator(apply_uc=apply_uc, revert_uc=revert_uc)

    result = coordinator.run([_op_apply(_PATH_A), _op_apply(_PATH_B)], decide=lambda ctx: ConflictResolution.ROLLBACK)

    assert result.aborted
    # Kurs A wurde erfolgreich appliziert, dann durch Rollback per Revert rueckgaengig gemacht.
    assert (_PATH_A, False) in revert_uc.calls


def test_proceed_forces_warning_through():
    revert_uc = _FakeRevertUseCase(issues_by_path={_PATH_A: [_warning_issue()]})
    coordinator = _coordinator(revert_uc=revert_uc)

    result = coordinator.run([_op_revert(_PATH_A)], decide=lambda ctx: ConflictResolution.PROCEED)

    assert not result.aborted
    assert result.course_results[0].outcome is CourseOperationOutcome.SUCCESS
    assert (_PATH_A, True) in revert_uc.calls


def test_proceed_is_ignored_for_technical_errors():
    """PROCEED ist bei echten Fehlern (nicht Warnungen) nicht sinnvoll und wird wie SKIPPED behandelt."""
    apply_uc = _FakeApplyUseCase(raise_for={_PATH_A})
    coordinator = _coordinator(apply_uc=apply_uc)

    result = coordinator.run([_op_apply(_PATH_A)], decide=lambda ctx: ConflictResolution.PROCEED)

    assert not result.aborted
    assert result.course_results[0].outcome is CourseOperationOutcome.SKIPPED


def test_conflict_context_classifies_error_vs_warning():
    revert_uc = _FakeRevertUseCase(issues_by_path={_PATH_A: [_error_issue()]})
    contexts = []

    def decide(ctx):
        contexts.append(ctx)
        return ConflictResolution.SKIP

    coordinator = _coordinator(revert_uc=revert_uc)
    coordinator.run([_op_revert(_PATH_A)], decide=decide)

    assert contexts[0].kind is ConflictKind.ERROR
