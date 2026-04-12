from __future__ import annotations

from pathlib import Path

from kursplaner.core.ports.repositories import SubjectSourceRepository


class RebuildSubjectSourceIndexUseCase:
    """Orchestriert den expliziten Rebuild des Subject-Source-Index.

    Der Use Case bildet den erlaubten Maintenance-Pfad für kontrollierte Vollscans.
    """

    def __init__(self, subject_source_repo: SubjectSourceRepository):
        """Initialisiert den Use Case mit einem SubjectSourceRepository-Port."""
        self.subject_source_repo = subject_source_repo

    def execute(self, unterricht_dir: Path, subject_folder: str | None = None) -> int:
        """Baut den Subject-Source-Index explizit neu auf.

        Args:
            unterricht_dir: Unterrichts-Basisverzeichnis.
            subject_folder: Optionaler Fachordner für gezielten Rebuild.

        Returns:
            Anzahl neu geschriebener Manifest-Dateien.
        """
        resolved = unterricht_dir.expanduser().resolve()
        if not resolved.exists() or not resolved.is_dir():
            return 0
        return self.subject_source_repo.rebuild_index(resolved, subject_folder=subject_folder)
