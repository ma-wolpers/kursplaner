from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from kursplaner.core.ports.repositories import KompetenzGraphRepository
from kursplaner.core.usecases.kompetenzgraph_load_usecase import KompetenzGraphLoadResult, LoadKompetenzGraphUseCase


class RebuildKompetenzGraphUseCase:
    """Orchestriert den expliziten Rebuild des Kompetenzgraph-Caches (kontrollierter Vollscan).

    Bildet den erlaubten Maintenance-Pfad für einen vollständigen
    Neu-Scan (analog `RebuildSubjectSourceIndexUseCase`) -- der normale
    `LoadKompetenzGraphUseCase`-Pfad scannt zwar bei jedem Aufruf flach
    über alle Dateien (mtime+size-Vergleich), liest aber nur geänderte
    Inhalte neu; dieser Use Case verwirft zusätzlich den kompletten Cache,
    bevor delegiert wird.
    """

    def __init__(self, kompetenzgraph_repo: KompetenzGraphRepository, load_usecase: LoadKompetenzGraphUseCase):
        """Initialisiert den Use Case mit dem Repository-Port und dem Load-Usecase, an den delegiert wird."""
        self.kompetenzgraph_repo = kompetenzgraph_repo
        self.load_usecase = load_usecase

    def execute(
        self, unterricht_dir: Path, subject_folders: Sequence[str] | None = None
    ) -> KompetenzGraphLoadResult:
        """Invalidiert den Cache vollständig und lädt den Kompetenzgraphen anschließend frisch."""
        self.kompetenzgraph_repo.invalidate_cache()
        return self.load_usecase.execute(unterricht_dir, subject_folders)
