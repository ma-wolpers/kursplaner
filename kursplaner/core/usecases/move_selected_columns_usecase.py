from __future__ import annotations

from dataclasses import dataclass

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.ports.repositories import PlanRepository
from kursplaner.core.usecases.plan_commands_usecase import PlanCommandsUseCase


@dataclass(frozen=True)
class MoveColumnsPlan:
    """Fachliche Vorabplanung für das Verschieben einer ausgewählten Spalte."""

    partner_index: int
    row_a: int
    row_b: int


@dataclass(frozen=True)
class MoveColumnsResult:
    """Ergebnisobjekt für das Verschieben zweier Einheiten."""

    proceed: bool
    error_message: str | None = None


class MoveSelectedColumnsUseCase:
    """Tauscht zwei Inhalte in der Planung und persistiert die Änderung."""

    def __init__(
        self,
        plan_repo: PlanRepository,
        plan_commands: PlanCommandsUseCase,
    ):
        """Initialisiert Move-Use-Case mit Tauschlogik und Planpersistenz."""
        self.plan_repo = plan_repo
        self.plan_commands = plan_commands

    @staticmethod
    def _validate_row_index(table: PlanTableData, row_index: int) -> bool:
        return 0 <= row_index < len(table.rows)

    def execute(self, table: PlanTableData, row_a: int, row_b: int) -> MoveColumnsResult:
        """Führt den inhaltlichen Tausch zweier Zeilen aus und speichert die Planung.

        Invariante:
        - Nur die Spalte `Inhalt` der beiden Zielzeilen wird getauscht.
        - Die verlinkten Stunden-Dateien behalten ihren Dateinamen (Zufallscode);
          es wird nur getauscht, welche Datei mit welcher Zeile verlinkt ist.
        - Die geänderte Planung ist persistiert.
        """
        if not self._validate_row_index(table, row_a) or not self._validate_row_index(table, row_b):
            return MoveColumnsResult(proceed=False, error_message="Verschieben abgebrochen: Ungültige Zeilenauswahl.")
        if row_a == row_b:
            return MoveColumnsResult(proceed=True)

        self.plan_commands.swap_contents(table, row_a, row_b)
        self.plan_repo.save_plan_table(table)
        return MoveColumnsResult(proceed=True)

    def find_swap_partner(self, day_columns: list[dict[str, object]], start_index: int, direction: int) -> int | None:
        """Sucht die nächste verschiebbare Spalte in gegebener Bewegungsrichtung."""
        probe = start_index + direction
        while 0 <= probe < len(day_columns):
            day = day_columns[probe]
            if not bool(day.get("is_cancel", False)):
                return probe
            probe += direction
        return None

    def build_move_plan(
        self,
        day_columns: list[dict[str, object]],
        selected_index: int,
        direction: int,
    ) -> MoveColumnsPlan | None:
        """Ermittelt Partner- und Zielzeilen für den Move-Write-Flow."""
        partner_index = self.find_swap_partner(day_columns, selected_index, direction)
        if partner_index is None:
            return None
        row_a = int(day_columns[selected_index].get("row_index", selected_index))
        row_b = int(day_columns[partner_index].get("row_index", partner_index))
        return MoveColumnsPlan(
            partner_index=partner_index,
            row_a=row_a,
            row_b=row_b,
        )
