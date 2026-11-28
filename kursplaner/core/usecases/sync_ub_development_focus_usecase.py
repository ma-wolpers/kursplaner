from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from kursplaner.core.domain.unterrichtsbesuch_policy import with_ub_development_list
from kursplaner.core.ports.repositories import LessonRepository, UbRepository
from kursplaner.core.usecases.ub_files import existing_ub_path


class SyncUbDevelopmentFocusUseCase:
    """Schreibt eine UB-Entwicklungsliste (``Baustellen``/``Ressourcen``) aus dem Grid in die UB-Datei."""

    def __init__(self, lesson_repo: LessonRepository, ub_repo: UbRepository):
        self.lesson_repo = lesson_repo
        self.ub_repo = ub_repo

    def _lesson_data(self, lesson_path: Path) -> dict[str, object]:
        lesson = self.lesson_repo.load_lesson_yaml(lesson_path)
        return lesson.data if isinstance(lesson.data, dict) else {}

    def save_list(self, *, workspace_root: Path, lesson_path: Path, field: str, entries: Sequence[str]) -> bool:
        """Ersetzt eine Entwicklungsliste im Frontmatter der verknüpften UB-Datei.

        Die andere Liste, die übrigen Schlüssel und der Body (Reflexion, eigener
        Text) bleiben unverändert.

        Args:
            workspace_root: Workspace-Stamm (für den UB-Ordner).
            lesson_path: Stunden-Datei mit ``Unterrichtsbesuch``-Link.
            field: ``UB_STEPS_FIELD`` oder ``UB_RESOURCES_FIELD``.
            entries: Neue Einträge (bereits über `parse_list_cell` zerlegt).

        Returns:
            ``False``, wenn die Einheit keine existierende UB-Datei hat.

        Raises:
            ValueError: *field* ist keine Entwicklungsliste.
            ListFieldViolationError: Ein Eintrag verletzt die Listen-Invariante.
        """
        ub_path = existing_ub_path(self.ub_repo, workspace_root, self._lesson_data(lesson_path))
        if ub_path is None:
            return False

        yaml_data, body = self.ub_repo.load_ub_markdown(ub_path)
        self.ub_repo.save_ub_markdown(ub_path, with_ub_development_list(yaml_data, field, entries), body)
        return True
