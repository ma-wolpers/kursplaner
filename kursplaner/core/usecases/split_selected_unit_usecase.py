from __future__ import annotations

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.ports.repositories import PlanRepository
from kursplaner.core.usecases.plan_commands_usecase import PlanCommandsUseCase


class SplitSelectedUnitUseCase:
    """Teilt eine Mehrstunden-Einheit und persistiert die geänderte Planung."""

    def __init__(self, plan_repo: PlanRepository, plan_commands: PlanCommandsUseCase):
        """Initialisiert Split-Use-Case mit Command-Logik und Planpersistenz."""
        self.plan_repo = plan_repo
        self.plan_commands = plan_commands

    def preview_hours(self, table: PlanTableData, row_index: int) -> int:
        """Liefert die zu splittende Stundenanzahl oder wirft bei ungültiger Einheit."""
        return self.plan_commands.split_hour_count(table, row_index)

    def execute(self, table: PlanTableData, row_index: int) -> int:
        """Führt den Split aus und speichert die geänderte Plan-Datei.

        Invariante:
        - Die ursprüngliche Mehrstunden-Zeile ist in Einzelstunden aufgeteilt.
        - Die Plan-Tabelle ist nach der Änderung persistiert.
        """
        hour_count = self.plan_commands.split_unit(table, row_index)
        self.plan_repo.save_plan_table(table)
        return hour_count
