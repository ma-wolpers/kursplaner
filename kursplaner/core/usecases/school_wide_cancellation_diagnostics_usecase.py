from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.row_identity import ResolutionStatus, resolve_move
from kursplaner.core.domain.school_wide_cancellation import SchoolWideCancellationEntry
from kursplaner.core.ports.repositories import PlanRepository


@dataclass(frozen=True)
class DiagnosticIssue:
    """Eine erkannte Abweichung zwischen einem Ledger-Eintrag und dem tatsaechlichen Kurszustand."""

    entry_id: str
    course_label: str
    description: str


class SchoolWideCancellationDiagnosticsUseCase:
    """Rein lesender Konsistenzcheck: passen die Ledger-Eintraege noch zum tatsaechlichen Kurszustand.

    Wird beim Oeffnen des Popups aufgerufen, meldet Abweichungen nur (keine
    automatische Reparatur), und ist bewusst von Apply/Revert getrennt -
    nutzt aber dieselbe Identitaetsaufloesung (`row_identity.resolve_move`)
    wie Revert, um keine zweite Matching-Logik zu pflegen. Ein Fund hier
    verhindert nicht die normale Arbeit mit uebrigen, gueltigen Eintraegen.
    """

    def __init__(self, plan_repo: PlanRepository) -> None:
        """Nimmt das Plan-Repository fuer den Lesezugriff auf betroffene Kurse entgegen."""
        self._plan_repo = plan_repo

    def diagnose(self, entries: list[SchoolWideCancellationEntry]) -> list[DiagnosticIssue]:
        """Prueft jeden Ledger-Move jedes Eintrags gegen den aktuellen Kurszustand."""
        issues: list[DiagnosticIssue] = []
        for entry in entries:
            for course_key, ledger in entry.course_ledgers.items():
                course_path = Path(course_key)
                try:
                    table = self._plan_repo.load_plan_table(course_path)
                except Exception as exc:
                    issues.append(
                        DiagnosticIssue(entry.entry_id, course_path.parent.name, f"Kursdatei nicht ladbar: {exc}")
                    )
                    continue

                for move in ledger.moves:
                    resolution = resolve_move(table.headers, table.rows, move)
                    if resolution.status is ResolutionStatus.MATCH:
                        continue
                    issues.append(
                        DiagnosticIssue(
                            entry.entry_id,
                            course_path.parent.name,
                            f"[{resolution.status.value}] {resolution.detail or 'Abweichung erkannt.'}",
                        )
                    )
        return issues
