from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData, sanitize_hour_title
from kursplaner.core.domain.wiki_links import strip_wiki_link
from kursplaner.core.ports.repositories import PlanRepository
from kursplaner.core.usecases.lesson_commands_usecase import LessonCommandsUseCase
from kursplaner.core.usecases.lesson_transfer_usecase import LessonTransferUseCase
from kursplaner.core.usecases.plan_commands_usecase import PlanCommandsUseCase


@dataclass(frozen=True)
class LzkConflictResolution:
    """Beschreibt die Konfliktauflösung für Lzk Conflict Resolution.

    Die Instanz hält Benutzerentscheidung und optionale Zielzeile für den Konfliktfall.
    """

    proceed: bool
    error_message: str | None = None
    shadow_link: Path | None = None
    delete_link: Path | None = None


@dataclass(frozen=True)
class ConvertToLzkWriteResult:
    """Ergebnis eines vollständigen LZK-Write-Flows."""

    proceed: bool
    link: Path | None = None
    shadow_link: Path | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class ConvertToLzkDialogContext:
    """Fachlicher Vorabkontext für den LZK-Dialogflow."""

    row_index: int
    current_content: str
    existing_link: Path | None
    existing_existing_link: Path | None
    title: str
    default_hours: int


class ConvertToLzkUseCase:
    """Orchestriert den fachlichen Ablauf für Convert To Lzk Use-Case.

    Die Klasse bündelt Anwendungslogik zwischen Domain-Regeln und Port-basiertem I/O.
    """

    def __init__(
        self,
        plan_commands: PlanCommandsUseCase,
        lesson_commands: LessonCommandsUseCase,
        plan_repo: PlanRepository,
        lesson_transfer: LessonTransferUseCase,
    ):
        """Initialisiert den LZK-Konvertierungsablauf mit Plan- und Lesson-Kommandos.

        Args:
            plan_commands: Operationen auf Planzeilen.
            lesson_commands: Operationen auf Stunden-Dateien.
            plan_repo: Repository zum Persistieren der Planung.
            lesson_transfer: Dateioperationen für optionale Löschvorgänge.
        """
        self.plan_commands = plan_commands
        self.lesson_commands = lesson_commands
        self.plan_repo = plan_repo
        self.lesson_transfer = lesson_transfer

    @staticmethod
    def _existing_file(existing_link: Path | None) -> Path | None:
        """Validiert einen bestehenden Link auf eine tatsächlich vorhandene Datei.

        Args:
            existing_link: Potenzieller Dateilink aus der Planzeile.

        Returns:
            Dateipfad bei existierender Datei, sonst ``None``.
        """
        if isinstance(existing_link, Path) and existing_link.exists() and existing_link.is_file():
            return existing_link
        return None

    def resolve_conflict(
        self,
        table: PlanTableData,
        row_index: int,
        current_content: str,
        decision: str,
        existing_link: Path | None,
    ) -> LzkConflictResolution:
        """Bewertet Konflikte und liefert die konkrete LZK-Aktionsentscheidung.

        Args:
            table: Planungstabelle.
            row_index: Zielzeile für die LZK-Umwandlung.
            current_content: Aktueller Inhaltswert der Zielzeile.
            decision: Benutzerentscheidung für den Konfliktfall.
            existing_link: Bereits verlinkte Stunden-Datei der Zeile.

        Returns:
            Aufgelöste Konfliktstrategie inkl. Schatten-/Delete-Informationen.
        """
        if not current_content.strip():
            return LzkConflictResolution(proceed=True)

        normalized = (decision or "cancel").strip().lower()
        if normalized == "cancel":
            return LzkConflictResolution(proceed=False)

        existing_file = self._existing_file(existing_link)

        if normalized == "move":
            shifted = self.plan_commands.shift_existing_lessons_forward(table, start_row_index=row_index)
            if not shifted:
                return LzkConflictResolution(
                    proceed=False,
                    error_message="Verschieben würde das Tabellenende überschreiten. Keine Änderung durchgeführt.",
                    shadow_link=existing_file,
                )
            return LzkConflictResolution(proceed=True)

        if normalized == "shadow":
            return LzkConflictResolution(proceed=True, shadow_link=existing_file)

        if normalized == "delete":
            return LzkConflictResolution(proceed=True, delete_link=existing_file)

        raise RuntimeError(f"Unbekannte Konfliktentscheidung: {decision}")

    def create_lzk_lesson(
        self,
        table: PlanTableData,
        row_index: int,
        title: str,
        default_hours: int,
    ) -> Path:
        """Erzeugt und verlinkt die LZK-Stundendatei für eine Zielzeile.

        Args:
            table: Planungstabelle.
            row_index: Zielzeile.
            title: Datei-/Anzeigetitel für die neue LZK-Stunde.
            default_hours: Voreinstellung für die Stundenzahl.

        Returns:
            Pfad der erzeugten LZK-Datei.
        """
        return self.lesson_commands.create_lzk_lesson(
            table=table,
            row_index=row_index,
            title=title,
            default_hours=default_hours,
        )

    @staticmethod
    def build_lzk_title(table: PlanTableData, next_no: int) -> str:
        """Erzeugt den fachlichen LZK-Titel aus Planmetadaten und laufender Nummer."""
        subject = sanitize_hour_title(str(table.metadata.get("Kursfach", "Fach"))) or "Fach"

        group = strip_wiki_link(str(table.metadata.get("Lerngruppe", "gruppe")))
        group = sanitize_hour_title(group) or "gruppe"

        stem = table.markdown_path.stem
        match = re.search(r"\b(\d{2}-[12])\b", stem)
        halfyear = match.group(1) if match else "??-?"

        return f"LZK {subject} {group} {halfyear} {next_no}"

    def build_dialog_context(
        self,
        *,
        table: PlanTableData,
        row_index: int,
        current_content: str,
        next_no: int,
        stunden_raw: str,
    ) -> ConvertToLzkDialogContext:
        """Ermittelt alle fachlichen Dialog-Eingaben für die LZK-Umwandlung."""
        existing_link = self.lesson_transfer.resolve_existing_link(table, row_index)
        existing_existing_link = self._existing_file(existing_link)
        default_hours = int(stunden_raw) if str(stunden_raw).strip().isdigit() else 2
        return ConvertToLzkDialogContext(
            row_index=row_index,
            current_content=str(current_content).strip(),
            existing_link=existing_link,
            existing_existing_link=existing_existing_link,
            title=self.build_lzk_title(table, next_no),
            default_hours=default_hours,
        )

    def execute(
        self,
        *,
        table: PlanTableData,
        row_index: int,
        current_content: str,
        decision: str,
        existing_link: Path | None,
        title: str,
        default_hours: int,
        allow_delete: bool,
    ) -> ConvertToLzkWriteResult:
        """Führt den vollständigen LZK-Write-Flow als eine Use-Case-Transaktion aus.

        Ablauf:
        1) Konflikt fachlich auflösen
        2) optional alte Datei löschen
        3) neue LZK-Datei erzeugen und verlinken
        4) Planung persistieren
        """
        resolution = self.resolve_conflict(
            table=table,
            row_index=row_index,
            current_content=current_content,
            decision=decision,
            existing_link=existing_link,
        )

        if not resolution.proceed:
            return ConvertToLzkWriteResult(
                proceed=False,
                shadow_link=resolution.shadow_link,
                error_message=resolution.error_message,
            )

        if isinstance(resolution.delete_link, Path):
            if not allow_delete:
                return ConvertToLzkWriteResult(
                    proceed=False,
                    shadow_link=resolution.shadow_link,
                    error_message="Löschen wurde nicht bestätigt. Keine Änderung durchgeführt.",
                )
            self.lesson_transfer.delete_lesson_file(resolution.delete_link)

        link = self.create_lzk_lesson(
            table=table,
            row_index=row_index,
            title=title,
            default_hours=default_hours,
        )
        self.plan_repo.save_plan_table(table)

        return ConvertToLzkWriteResult(
            proceed=True,
            link=link,
            shadow_link=resolution.shadow_link,
        )
