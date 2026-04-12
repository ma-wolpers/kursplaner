from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.wiki_links import strip_wiki_link
from kursplaner.core.ports.repositories import LessonRepository, UbRepository
from kursplaner.core.usecases.ub_overview_builder import build_ub_overview_markdown


@dataclass(frozen=True)
class RemoveUnitUbLinkResult:
    """Ergebnis des Entlinkens einer UB-Verknüpfung an einer Einheit."""

    proceed: bool
    lesson_path: Path | None = None
    ub_path: Path | None = None
    overview_path: Path | None = None
    ub_file_deleted: bool = False
    error_message: str | None = None


class RemoveUnitUbLinkUseCase:
    """Entfernt eine UB-Verknüpfung aus der Einheit und synchronisiert die UB-Übersicht."""

    def __init__(self, lesson_repo: LessonRepository, ub_repo: UbRepository):
        self.lesson_repo = lesson_repo
        self.ub_repo = ub_repo

    def execute(
        self,
        *,
        workspace_root: Path,
        table: PlanTableData,
        row_index: int,
        delete_ub_markdown: bool,
    ) -> RemoveUnitUbLinkResult:
        """Löst den UB-Link der Zielzeile und löscht optional die verknüpfte UB-Datei."""
        if row_index < 0 or row_index >= len(table.rows):
            return RemoveUnitUbLinkResult(proceed=False, error_message="Zeilenindex außerhalb der Planungstabelle.")

        lesson_path = self.lesson_repo.resolve_row_link_path(table, row_index)
        if not isinstance(lesson_path, Path) or not lesson_path.exists() or not lesson_path.is_file():
            return RemoveUnitUbLinkResult(
                proceed=False,
                error_message="Keine verlinkte Einheit für die gewählte Zeile.",
            )

        lesson = self.lesson_repo.load_lesson_yaml(lesson_path)
        lesson_data = lesson.data if isinstance(lesson.data, dict) else {}
        ub_stem = strip_wiki_link(str(lesson_data.get("Unterrichtsbesuch", "")).strip())
        if not ub_stem:
            return RemoveUnitUbLinkResult(
                proceed=False,
                lesson_path=lesson_path,
                error_message="Für die ausgewählte Einheit ist kein Unterrichtsbesuch verlinkt.",
            )

        ub_path = self.ub_repo.ensure_ub_root(workspace_root) / f"{ub_stem}.md"

        lesson_data["Unterrichtsbesuch"] = ""
        lesson.data = lesson_data
        self.lesson_repo.save_lesson_yaml(lesson)

        ub_file_deleted = False
        if delete_ub_markdown and ub_path.exists() and ub_path.is_file():
            self.ub_repo.delete_ub_markdown(ub_path)
            ub_file_deleted = True

        overview_markdown = build_ub_overview_markdown(self.ub_repo, workspace_root)
        overview_path = self.ub_repo.save_ub_overview(workspace_root, overview_markdown)

        return RemoveUnitUbLinkResult(
            proceed=True,
            lesson_path=lesson_path,
            ub_path=ub_path,
            overview_path=overview_path,
            ub_file_deleted=ub_file_deleted,
        )
