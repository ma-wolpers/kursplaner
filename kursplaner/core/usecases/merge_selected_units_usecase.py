from __future__ import annotations

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.ports.repositories import PlanRepository
from kursplaner.core.usecases.plan_commands_usecase import MergeResult, PlanCommandsUseCase


class MergeSelectedUnitsUseCase:
    """Verbindet Datums-Einheiten und persistiert die geänderte Planung."""

    def __init__(self, plan_repo: PlanRepository, plan_commands: PlanCommandsUseCase):
        """Initialisiert Merge-Use-Case mit Planpersistenz und Command-Logik."""
        self.plan_repo = plan_repo
        self.plan_commands = plan_commands

    def preview(self, table: PlanTableData, row_index: int) -> MergeResult:
        """Liefert eine fachliche Vorschau der Merge-Auswirkung."""
        return self.plan_commands.merge_preview(table, row_index)

    def can_merge(self, table: PlanTableData, row_index: int) -> bool:
        """Prüft fachlich, ob eine Datumsgruppe zusammengeführt werden kann."""
        return self.plan_commands.can_merge_date_units(table, row_index)

    def execute(self, table: PlanTableData, row_index: int) -> MergeResult:
        """Führt Merge aus und speichert die geänderte Plan-Datei.

        Invariante:
        - Datumsgruppe ist zu einer Einheit konsolidiert.
        - Die geänderte Planung ist persistiert.
        """
        result = self.plan_commands.merge_units(table, row_index)
        self.plan_repo.save_plan_table(table)
        return result
