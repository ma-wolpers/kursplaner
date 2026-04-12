from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.ports.repositories import LessonRepository, PlanRepository
from kursplaner.core.usecases.plan_commands_usecase import PlanCommandsUseCase


@dataclass(frozen=True)
class ConvertToAusfallResult:
    """Beschreibt die Datenstruktur für Convert To Ausfall Result.

    Die Instanz transportiert strukturierte Fachdaten zwischen Schichten und Verarbeitungsschritten.
    """

    shadow_link: Path | None


class ConvertToAusfallUseCase:
    """Orchestriert den fachlichen Ablauf für Convert To Ausfall Use-Case.

    Die Klasse bündelt Anwendungslogik zwischen Domain-Regeln und Port-basiertem I/O.
    """

    def __init__(
        self,
        plan_commands: PlanCommandsUseCase,
        lesson_repo: LessonRepository,
        plan_repo: PlanRepository,
    ):
        """Initialisiert den Ablauf zur Umwandlung einer Zeile in Ausfall.

        Args:
            plan_commands: Kommandos zum Ändern der Planzeile.
            lesson_repo: Zugriff auf ggf. verlinkte Stunden-Dateien.
            plan_repo: Repository zum Persistieren der Planung.
        """
        self.plan_commands = plan_commands
        self.lesson_repo = lesson_repo
        self.plan_repo = plan_repo

    def execute(self, table: PlanTableData, row_index: int, reason_text: str) -> ConvertToAusfallResult:
        """Setzt den Ausfallgrund und meldet eine ggf. zu archivierende Schattenstunde.

        Args:
            table: Planungstabelle.
            row_index: Zielzeile der Umwandlung.
            reason_text: Sichtbarer Ausfalltext.

        Returns:
            Ergebnis mit optionalem Link auf die bisherige Stunden-Datei.
        """
        existing_link = self.lesson_repo.resolve_row_link_path(table, row_index)
        shadow_link: Path | None = None
        if isinstance(existing_link, Path) and existing_link.exists() and existing_link.is_file():
            shadow_link = existing_link
            lesson = self.lesson_repo.load_lesson_yaml(existing_link)
            lesson.data["Stundentyp"] = "Ausfall"
            self.lesson_repo.save_lesson_yaml(lesson)

        self.plan_commands.convert_to_ausfall(table, row_index, reason_text)
        self.plan_repo.save_plan_table(table)
        return ConvertToAusfallResult(shadow_link=shadow_link)
