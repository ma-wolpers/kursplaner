from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.ports.repositories import LessonIndexRepository


@dataclass(frozen=True)
class RebuildLessonIndexUseCase:
    """Maintenance-Use-Case für den expliziten Voll-Rebuild des Lesson-Index.

    Gehört bewusst nicht in den normalen interaktiven Read-Pfad, sondern wird
    nur durch UI/CLI-Wartungsaktionen ausgelöst.
    """

    lesson_index_repo: LessonIndexRepository

    def execute(self, unterricht_dir: Path) -> None:
        """Führt den vollständigen Index-Neuaufbau für ein Unterrichts-Root aus."""
        if not isinstance(unterricht_dir, Path):
            raise RuntimeError("unterricht_dir must be a pathlib.Path")
        self.lesson_index_repo.rebuild_index(unterricht_dir)
