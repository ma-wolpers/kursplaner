from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.models import LessonOverviewItem, ListLessonsResult
from kursplaner.core.ports.repositories import PlanRepository
from kursplaner.core.usecases.plan_overview_query_usecase import PlanOverviewQueryUseCase


class ListLessonsUseCase:
    """Lädt Unterrichtsübersicht robust und markiert fehlerhafte Einträge.

    Der Use Case verwirft fehlerhafte Pläne nicht mehr, sondern liefert sie als
    markierbare Overview-Items mit `load_error` zurück.
    """

    def __init__(self, plan_repo: PlanRepository, plan_overview_query: PlanOverviewQueryUseCase):
        """Initialisiert den Übersicht-Use-Case mit injizierter Query-Abhängigkeit.

        Args:
            plan_repo: Port für Zugriff auf verfügbare Plan-Markdown-Dateien.
            plan_overview_query: Read-Use-Case zur Berechnung der Kennzahlen je Plan.
        """
        self.plan_repo = plan_repo
        self.plan_overview_query = plan_overview_query

    def execute(self, base_dir: Path) -> ListLessonsResult:
        """Erzeugt die linke Unterrichtsübersicht inkl. nicht-fataler Lesewarnungen.

        Auch bei Fehlern einzelner Unterrichtsdateien wird der Rest vollständig
        geladen; fehlerhafte Einträge bleiben sichtbar und erhalten Markertext.
        """
        if not base_dir.exists() or not base_dir.is_dir():
            return ListLessonsResult(lessons=[], warnings=[])

        items: list[LessonOverviewItem] = []
        warnings: list[str] = []
        for markdown in self.plan_repo.list_plan_markdown_files(base_dir):
            try:
                table = self.plan_repo.load_plan_table(markdown)
            except Exception as exc:
                detail = f"{markdown.name}: {exc}"
                warnings.append(detail)
                items.append(
                    LessonOverviewItem(
                        folder_name=markdown.parent.name,
                        folder_path=markdown.parent,
                        markdown_path=markdown,
                        next_topic="⚠ nicht geladen",
                        remaining_hours=0,
                        next_lzk="—",
                        load_error=str(exc),
                    )
                )
                continue

            markdown = table.markdown_path
            folder_path = markdown.parent
            folder_name = folder_path.name

            try:
                next_topic, remaining_hours, next_lzk = self.plan_overview_query.summarize_plan(table)
            except Exception as exc:
                detail = f"{markdown.name}: {exc}"
                warnings.append(detail)
                items.append(
                    LessonOverviewItem(
                        folder_name=folder_name,
                        folder_path=folder_path,
                        markdown_path=markdown,
                        next_topic="⚠ nicht geladen",
                        remaining_hours=0,
                        next_lzk="—",
                        load_error=str(exc),
                    )
                )
                continue

            items.append(
                LessonOverviewItem(
                    folder_name=folder_name,
                    folder_path=folder_path,
                    markdown_path=markdown,
                    next_topic=next_topic,
                    remaining_hours=remaining_hours,
                    next_lzk=next_lzk,
                    load_error=None,
                )
            )

        return ListLessonsResult(lessons=items, warnings=warnings)
