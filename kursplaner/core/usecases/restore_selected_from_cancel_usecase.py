from __future__ import annotations

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.ports.repositories import PlanRepository
from kursplaner.core.usecases.plan_commands_usecase import PlanCommandsUseCase


class RestoreSelectedFromCancelUseCase:
    """Hebt eine Ausfall-Markierung auf und persistiert die Planänderung."""

    def __init__(self, plan_repo: PlanRepository, plan_commands: PlanCommandsUseCase):
        """Initialisiert Use Case mit Rücksetzlogik und Planpersistenz."""
        self.plan_repo = plan_repo
        self.plan_commands = plan_commands

    def execute(self, table: PlanTableData, row_index: int) -> None:
        """Setzt den Inhalt der Zielzeile zurück und speichert die Planung."""
        self.plan_commands.restore_from_cancel(table, row_index)
        self.plan_repo.save_plan_table(table)
