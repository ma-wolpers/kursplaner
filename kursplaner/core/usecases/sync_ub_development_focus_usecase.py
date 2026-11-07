from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.ports.repositories import LessonRepository, UbRepository
from kursplaner.core.usecases.ub_files import existing_ub_path, load_development_lists
from kursplaner.core.usecases.ub_markdown_sections import text_to_list_entries, with_development_lists


@dataclass(frozen=True)
class UbDevelopmentFocus:
    """Geladene UB-Entwicklungsfelder für die Grid-Synchronisierung."""

    professional_steps: list[str]
    usable_resources: list[str]


class SyncUbDevelopmentFocusUseCase:
    """Synchronisiert UB-Bullets für Professionalisierungsschritte und Ressourcen."""

    def __init__(self, lesson_repo: LessonRepository, ub_repo: UbRepository):
        self.lesson_repo = lesson_repo
        self.ub_repo = ub_repo

    def _lesson_data(self, lesson_path: Path) -> dict[str, object]:
        lesson = self.lesson_repo.load_lesson_yaml(lesson_path)
        return lesson.data if isinstance(lesson.data, dict) else {}

    def load(self, *, workspace_root: Path, lesson_path: Path) -> UbDevelopmentFocus:
        """Lädt die zwei UB-Entwicklungslisten für eine Einheit (`ub_files.load_development_lists`)."""
        steps, resources = load_development_lists(self.ub_repo, workspace_root, self._lesson_data(lesson_path))
        return UbDevelopmentFocus(professional_steps=steps, usable_resources=resources)

    def save(
        self,
        *,
        workspace_root: Path,
        lesson_path: Path,
        professional_steps_text: str,
        usable_resources_text: str,
    ) -> bool:
        """Ersetzt nur die zwei Listen-Abschnitte der UB-Datei; Reflexion und übriger Text bleiben wörtlich."""
        ub_path = existing_ub_path(self.ub_repo, workspace_root, self._lesson_data(lesson_path))
        if ub_path is None:
            return False

        yaml_data, body = self.ub_repo.load_ub_markdown(ub_path)
        steps = text_to_list_entries(professional_steps_text)
        resources = text_to_list_entries(usable_resources_text)
        self.ub_repo.save_ub_markdown(ub_path, yaml_data, with_development_lists(body, steps, resources))
        return True
