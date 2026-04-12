from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.ports.repositories import PlanRepository
from kursplaner.core.usecases.lesson_transfer_usecase import LessonTransferUseCase


@dataclass(frozen=True)
class FindMarkdownForSelectedResult:
    """Ergebnis des Write-Flows für "Markdown finden"."""

    proceed: bool
    linked_path: Path | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class FindMarkdownSelectionPlan:
    """Vorabplanung für den Write-Flow "Markdown finden"."""

    source_valid: bool
    source_error: str | None
    target_dir: Path
    target: Path
    requires_target_dir_creation: bool
    requires_move: bool
    has_target_conflict: bool


class FindMarkdownForSelectedUseCase:
    """Verlinkt eine ausgewählte Markdown-Datei auf die Zielzeile und persistiert die Planung."""

    def __init__(self, plan_repo: PlanRepository, lesson_transfer: LessonTransferUseCase):
        """Initialisiert Use Case mit Planpersistenz und Datei-Transferlogik."""
        self.plan_repo = plan_repo
        self.lesson_transfer = lesson_transfer

    def build_selection_plan(self, *, table: PlanTableData, source: Path) -> FindMarkdownSelectionPlan:
        """Leitet alle fachlichen Entscheidungen für den Auswahl-Dialog ab."""
        source_valid = True
        source_error: str | None = None
        try:
            self.lesson_transfer.validate_lesson_markdown(source)
        except Exception as exc:
            source_valid = False
            source_error = str(exc)

        target_dir = self.lesson_transfer.lesson_dir_for_table(table)
        target = self.lesson_transfer.find_markdown_target(table, source)
        requires_move = target.resolve() != source.resolve()
        has_target_conflict = bool(target.exists() and target.resolve() != source.resolve())
        requires_target_dir_creation = bool(requires_move and not target_dir.exists())
        return FindMarkdownSelectionPlan(
            source_valid=source_valid,
            source_error=source_error,
            target_dir=target_dir,
            target=target,
            requires_target_dir_creation=requires_target_dir_creation,
            requires_move=requires_move,
            has_target_conflict=has_target_conflict,
        )

    def execute(
        self,
        *,
        table: PlanTableData,
        row_index: int,
        source: Path,
        allow_create_target_dir: bool,
        allow_move: bool,
        allow_plan_save: bool,
    ) -> FindMarkdownForSelectedResult:
        """Führt den vollständigen Write-Flow für "Markdown finden" aus."""
        target_dir = self.lesson_transfer.lesson_dir_for_table(table)
        target = self.lesson_transfer.find_markdown_target(table, source)

        if target.resolve() != source.resolve():
            if not target_dir.exists():
                if not allow_create_target_dir:
                    return FindMarkdownForSelectedResult(
                        proceed=False,
                        error_message="Erstellen des Zielordners abgebrochen.",
                    )
                self.lesson_transfer.ensure_directory(target_dir)

            if not allow_move:
                return FindMarkdownForSelectedResult(
                    proceed=False,
                    error_message="Verschieben der Markdown-Datei abgebrochen.",
                )

            target = self.lesson_transfer.move_markdown(source, target)

        self.lesson_transfer.relink_row_to_stem(table, row_index, target.stem)
        if not allow_plan_save:
            return FindMarkdownForSelectedResult(
                proceed=False,
                error_message="Speichern der Planungstabelle abgebrochen.",
            )

        self.plan_repo.save_plan_table(table)
        return FindMarkdownForSelectedResult(proceed=True, linked_path=target)
