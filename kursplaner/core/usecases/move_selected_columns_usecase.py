from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.lesson_naming import build_lesson_stem, row_mmdd
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.wiki_links import strip_wiki_link
from kursplaner.core.ports.repositories import PlanRepository
from kursplaner.core.usecases.lesson_transfer_usecase import LessonTransferUseCase
from kursplaner.core.usecases.plan_commands_usecase import PlanCommandsUseCase
from kursplaner.core.usecases.rename_linked_file_for_row_usecase import RenameLinkedFileForRowUseCase


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
        lesson_transfer: LessonTransferUseCase,
        rename_linked_file_for_row: RenameLinkedFileForRowUseCase,
    ):
        """Initialisiert Move-Use-Case mit Tauschlogik und Planpersistenz."""
        self.plan_repo = plan_repo
        self.plan_commands = plan_commands
        self.lesson_transfer = lesson_transfer
        self.rename_linked_file_for_row = rename_linked_file_for_row

    @staticmethod
    def _topic_from_stem(lesson_stem: str, group_name: str) -> str:
        stem = str(lesson_stem or "").strip()
        group = str(group_name or "").strip()
        if stem and group and stem.lower().startswith(f"{group} ".lower()):
            remainder = stem[len(group) :].strip()
            if len(remainder) > 6 and remainder[2:3] == "-" and remainder[5:6] == " ":
                topic = remainder[6:].strip()
                if topic:
                    return topic
        idx = stem.find(" ")
        while idx != -1:
            candidate = stem[idx + 1 :].strip()
            if len(candidate) > 6 and candidate[2:3] == "-" and candidate[5:6] == " ":
                topic = candidate[6:].strip()
                if topic:
                    return topic
            idx = stem.find(" ", idx + 1)
        return stem

    @staticmethod
    def _validate_row_index(table: PlanTableData, row_index: int) -> bool:
        return 0 <= row_index < len(table.rows)

    def _require_existing_link(self, table: PlanTableData, row_index: int) -> Path | None:
        link = self.lesson_transfer.resolve_existing_link(table, row_index)
        if not isinstance(link, Path):
            return None
        if not link.exists() or not link.is_file():
            return None
        return link

    @dataclass(frozen=True)
    class _RenameStep:
        row_index: int
        desired_stem: str
        rollback_stem: str

    def execute(self, table: PlanTableData, row_a: int, row_b: int) -> MoveColumnsResult:
        """Führt den inhaltlichen Tausch zweier Zeilen aus und speichert die Planung.

        Invariante:
        - Nur die Spalte `Inhalt` der beiden Zielzeilen wird getauscht.
        - Die geänderte Planung ist persistiert.
        """
        if not self._validate_row_index(table, row_a) or not self._validate_row_index(table, row_b):
            return MoveColumnsResult(proceed=False, error_message="Verschieben abgebrochen: Ungültige Zeilenauswahl.")
        if row_a == row_b:
            return MoveColumnsResult(proceed=True)

        link_a = self._require_existing_link(table, row_a)
        link_b = self._require_existing_link(table, row_b)

        group_name = strip_wiki_link(str(table.metadata.get("Lerngruppe", "gruppe")))
        stem_a = link_a.stem if isinstance(link_a, Path) else ""
        stem_b = link_b.stem if isinstance(link_b, Path) else ""

        self.plan_commands.swap_contents(table, row_a, row_b)

        rename_steps: list[MoveSelectedColumnsUseCase._RenameStep] = []
        if isinstance(link_b, Path):
            rename_steps.append(
                MoveSelectedColumnsUseCase._RenameStep(
                    row_index=row_a,
                    desired_stem=build_lesson_stem(
                        group_name,
                        row_mmdd(table, row_a),
                        self._topic_from_stem(stem_b, group_name),
                    ),
                    rollback_stem=stem_b,
                )
            )
        if isinstance(link_a, Path):
            rename_steps.append(
                MoveSelectedColumnsUseCase._RenameStep(
                    row_index=row_b,
                    desired_stem=build_lesson_stem(
                        group_name,
                        row_mmdd(table, row_b),
                        self._topic_from_stem(stem_a, group_name),
                    ),
                    rollback_stem=stem_a,
                )
            )

        applied_steps: list[MoveSelectedColumnsUseCase._RenameStep] = []
        for step in rename_steps:
            rename_result = self.rename_linked_file_for_row.execute(
                table=table,
                row_index=step.row_index,
                desired_stem=step.desired_stem,
                allow_rename=True,
                allow_plan_save=False,
                allow_conflict_suffix=False,
            )
            if not rename_result.proceed:
                rollback_ok = True
                for applied in reversed(applied_steps):
                    rollback = self.rename_linked_file_for_row.execute(
                        table=table,
                        row_index=applied.row_index,
                        desired_stem=applied.rollback_stem,
                        allow_rename=True,
                        allow_plan_save=False,
                        allow_conflict_suffix=False,
                    )
                    if not rollback.proceed:
                        rollback_ok = False
                        break
                self.plan_commands.swap_contents(table, row_a, row_b)
                if not rollback_ok:
                    return MoveColumnsResult(
                        proceed=False,
                        error_message=("Verschieben abgebrochen und Rollback unvollständig. Bitte Dateinamen prüfen."),
                    )
                return MoveColumnsResult(proceed=False, error_message=rename_result.error_message)
            applied_steps.append(step)

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
