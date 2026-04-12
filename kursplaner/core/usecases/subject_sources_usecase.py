from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.course_subject import normalize_course_subject
from kursplaner.core.ports.repositories import SubjectSourceRepository


class SubjectSourcesUseCase:
    """Orchestriert den fachlichen Ablauf für Subject Sources Use-Case.

    Die Klasse bündelt Anwendungslogik zwischen Domain-Regeln und Port-basiertem I/O.
    """

    def __init__(self, subject_source_repo: SubjectSourceRepository):
        """Initialisiert den Use Case mit einem Port für Baukasten-Quellen.

        Args:
            subject_source_repo: Repository für fachbezogene Inhalte-/Methodik-Quellen.
        """
        self.subject_source_repo = subject_source_repo

    def subject_folder_name(self, subject_raw: str) -> str:
        """Normalisiert Facheingaben auf den erwarteten Baukasten-Unterordnernamen."""
        return normalize_course_subject(subject_raw)

    def resolve_subject_sources(self, unterricht_dir: Path, subject_name: str) -> tuple[list[str], list[str]]:
        """Lädt verfügbare Inhalte-/Methodikquellen für ein Fach über den Subject-Source-Port."""
        fach = self.subject_folder_name(subject_name)
        return self.subject_source_repo.resolve_subject_sources(unterricht_dir, fach)
