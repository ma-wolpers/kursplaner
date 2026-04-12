from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.wiki_links import strip_wiki_link
from kursplaner.core.ports.repositories import LessonRepository, UbRepository
from kursplaner.core.usecases.ub_markdown_sections import parse_list_section, parse_reflection, text_to_list_entries


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

    @staticmethod
    def _resolve_ub_path(workspace_root: Path, lesson_data: dict[str, object], ub_repo: UbRepository) -> Path | None:
        raw_link = strip_wiki_link(str(lesson_data.get("Unterrichtsbesuch", "")).strip())
        if not raw_link:
            return None
        root = ub_repo.ensure_ub_root(workspace_root)
        path = root / f"{raw_link}.md"
        if path.exists() and path.is_file():
            return path
        return None

    def load(self, *, workspace_root: Path, lesson_path: Path) -> UbDevelopmentFocus:
        """Lädt die zwei UB-Entwicklungslisten für eine Einheit."""
        lesson = self.lesson_repo.load_lesson_yaml(lesson_path)
        data = lesson.data if isinstance(lesson.data, dict) else {}
        ub_path = self._resolve_ub_path(workspace_root, data, self.ub_repo)
        if ub_path is None:
            return UbDevelopmentFocus(professional_steps=[], usable_resources=[])

        try:
            _, body = self.ub_repo.load_ub_markdown(ub_path)
        except Exception:
            return UbDevelopmentFocus(professional_steps=[], usable_resources=[])

        return UbDevelopmentFocus(
            professional_steps=parse_list_section(body, "Professionalisierungsschritte"),
            usable_resources=parse_list_section(body, "Nutzbare Ressourcen"),
        )

    def save(
        self,
        *,
        workspace_root: Path,
        lesson_path: Path,
        professional_steps_text: str,
        usable_resources_text: str,
    ) -> bool:
        """Speichert Grid-Text in die passenden UB-Bulletlisten."""
        lesson = self.lesson_repo.load_lesson_yaml(lesson_path)
        data = lesson.data if isinstance(lesson.data, dict) else {}
        ub_path = self._resolve_ub_path(workspace_root, data, self.ub_repo)
        if ub_path is None:
            return False

        yaml_data, body = self.ub_repo.load_ub_markdown(ub_path)
        reflection = parse_reflection(body)
        steps = text_to_list_entries(professional_steps_text)
        resources = text_to_list_entries(usable_resources_text)
        self.ub_repo.save_ub_markdown(
            ub_path,
            yaml_data,
            reflection_text=reflection,
            professional_steps=steps,
            usable_resources=resources,
        )
        return True
