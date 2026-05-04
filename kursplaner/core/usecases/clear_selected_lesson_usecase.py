from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.config.path_store import infer_workspace_root_from_path
from kursplaner.core.domain.wiki_links import strip_wiki_link
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.ports.repositories import LessonFileRepository, LessonRepository, PlanRepository, UbRepository
from kursplaner.core.usecases.plan_commands_usecase import PlanCommandsUseCase
from kursplaner.core.usecases.ub_overview_builder import build_ub_overview_markdown


@dataclass(frozen=True)
class ClearSelectedLessonResult:
    """Ergebnis der Aktion "Stunde leeren"."""

    shadow_link: Path | None
    lesson_path: Path | None = None
    ub_path: Path | None = None
    overview_path: Path | None = None
    ub_stem: str = ""


class ClearSelectedLessonUseCase:
    """Leert den Inhalt einer Planzeile und persistiert die Planänderung."""

    def __init__(
        self,
        plan_repo: PlanRepository,
        plan_commands: PlanCommandsUseCase,
        lesson_repo: LessonRepository,
        lesson_file_repo: LessonFileRepository,
        ub_repo: UbRepository,
    ):
        """Initialisiert Use Case mit Plan-Repository und Plan-Command-Funktionen."""
        self.plan_repo = plan_repo
        self.plan_commands = plan_commands
        self.lesson_repo = lesson_repo
        self.lesson_file_repo = lesson_file_repo
        self.ub_repo = ub_repo

    @staticmethod
    def _workspace_root_from_markdown(path: Path) -> Path:
        """Leitet den Workspace-Stamm robust aus einem Projektpfad ab."""
        return infer_workspace_root_from_path(path)

    def execute(
        self,
        table: PlanTableData,
        row_index: int,
        *,
        workspace_root: Path | None = None,
        delete_lesson_markdown: bool = False,
        delete_ub_markdown: bool = False,
    ) -> ClearSelectedLessonResult:
        """Leert die Zielzeile, speichert die Planung und liefert optionalen Schatten-Link.

        Invariante:
        - Nach Ausführung ist die Zelle `Inhalt` der Zielzeile leer.
        - Die Änderung ist in der Plan-Datei persistiert.
        """
        link = self.plan_commands.clear_selected_lesson(table, row_index)
        lesson_path = link if isinstance(link, Path) else None
        ub_stem = ""
        ub_path: Path | None = None

        if isinstance(lesson_path, Path) and lesson_path.exists() and lesson_path.is_file():
            lesson = self.lesson_repo.load_lesson_yaml(lesson_path)
            lesson_data = lesson.data if isinstance(lesson.data, dict) else {}
            ub_stem = strip_wiki_link(str(lesson_data.get("Unterrichtsbesuch", "")).strip())

            active_workspace_root = workspace_root or self._workspace_root_from_markdown(table.markdown_path)
            if ub_stem:
                ub_path = self.ub_repo.ensure_ub_root(active_workspace_root) / f"{ub_stem}.md"

        self.plan_repo.save_plan_table(table)

        if delete_lesson_markdown and isinstance(lesson_path, Path):
            self.lesson_file_repo.delete_file(lesson_path)

        if delete_ub_markdown and isinstance(ub_path, Path) and ub_path.exists() and ub_path.is_file():
            self.ub_repo.delete_ub_markdown(ub_path)

        overview_path: Path | None = None
        if isinstance(ub_path, Path):
            active_workspace_root = workspace_root or self._workspace_root_from_markdown(table.markdown_path)
            overview_markdown = build_ub_overview_markdown(self.ub_repo, active_workspace_root)
            overview_path = self.ub_repo.save_ub_overview(active_workspace_root, overview_markdown)

        shadow_link = lesson_path if isinstance(lesson_path, Path) and lesson_path.exists() and lesson_path.is_file() else None
        return ClearSelectedLessonResult(
            shadow_link=shadow_link,
            lesson_path=lesson_path,
            ub_path=ub_path,
            overview_path=overview_path,
            ub_stem=ub_stem,
        )
