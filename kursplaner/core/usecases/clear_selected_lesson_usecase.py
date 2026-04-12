from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.ports.repositories import PlanRepository
from kursplaner.core.usecases.plan_commands_usecase import PlanCommandsUseCase


@dataclass(frozen=True)
class ClearSelectedLessonResult:
    """Ergebnis der Aktion "Stunde leeren"."""

    shadow_link: Path | None


class ClearSelectedLessonUseCase:
    """Leert den Inhalt einer Planzeile und persistiert die Planänderung."""

    def __init__(self, plan_repo: PlanRepository, plan_commands: PlanCommandsUseCase):
        """Initialisiert Use Case mit Plan-Repository und Plan-Command-Funktionen."""
        self.plan_repo = plan_repo
        self.plan_commands = plan_commands

    def execute(self, table: PlanTableData, row_index: int) -> ClearSelectedLessonResult:
        """Leert die Zielzeile, speichert die Planung und liefert optionalen Schatten-Link.

        Invariante:
        - Nach Ausführung ist die Zelle `Inhalt` der Zielzeile leer.
        - Die Änderung ist in der Plan-Datei persistiert.
        """
        link = self.plan_commands.clear_selected_lesson(table, row_index)
        self.plan_repo.save_plan_table(table)

        shadow_link = link if isinstance(link, Path) and link.exists() and link.is_file() else None
        return ClearSelectedLessonResult(shadow_link=shadow_link)
