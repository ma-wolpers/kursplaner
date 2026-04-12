from __future__ import annotations

from pathlib import Path

from kursplaner.core.ports.repositories import PlanRepository


class RebuildPlanIndexUseCase:
    """Orchestriert einen expliziten Rebuild des Plan-Index.

    Der Use Case bildet den erlaubten Fallback-Pfad für kontrollierte Vollscans.
    """

    def __init__(self, plan_repo: PlanRepository):
        """Initialisiert den Use Case mit einem PlanRepository-Port.

        Args:
            plan_repo: Repository mit Index-Invalidierung und Planlistenabfrage.
        """
        self.plan_repo = plan_repo

    def execute(self, base_dir: Path) -> int:
        """Invalidiert den Plan-Index und baut ihn für ein Basisverzeichnis neu auf.

        Args:
            base_dir: Unterrichts-Basisverzeichnis.

        Returns:
            Anzahl gefundener Plan-Markdown-Dateien nach Rebuild.
        """
        if not base_dir.exists() or not base_dir.is_dir():
            return 0

        self.plan_repo.invalidate_cache(base_dir)
        return len(self.plan_repo.list_plan_markdown_files(base_dir))
