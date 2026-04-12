from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from kursplaner.core.ports.repositories import LessonIndexRepository


@dataclass(frozen=True)
class InvalidateLessonIndexUseCase:
    """Maintenance-Use-Case zur gezielten oder vollständigen Index-Invalidierung."""

    lesson_index_repo: LessonIndexRepository

    def execute(self, unterricht_dir: Optional[Path] = None, subject_folder: Optional[str] = None) -> None:
        """Invalidiert den Lesson-Index.

        - ohne Parameter: kompletter Index
        - mit `unterricht_dir`: alle Einträge unterhalb dieses Roots
        - mit `subject_folder`: nur Einträge des Fachordners
        """
        self.lesson_index_repo.invalidate_index(unterricht_dir=unterricht_dir, subject_folder=subject_folder)
