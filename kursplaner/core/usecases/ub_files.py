"""UB-Datei einer Einheit finden und ihre Entwicklungslisten lesen – je eine Stelle.

Stamm aus dem Lesson-YAML: `unterrichtsbesuch_policy.ub_link_stem`; Dateiname:
`UbRepository.ub_markdown_path`; Body-Struktur: `ub_markdown_sections`.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from kursplaner.core.domain.unterrichtsbesuch_policy import ub_link_stem
from kursplaner.core.ports.repositories import UbRepository
from kursplaner.core.usecases.ub_markdown_sections import parse_development_lists


def existing_ub_path(ub_repo: UbRepository, workspace_root: Path, lesson_data: Mapping[str, object]) -> Path | None:
    """Pfad der verknüpften UB-Datei, wenn die Einheit eine hat und die Datei existiert."""
    stem = ub_link_stem(lesson_data)
    if not stem:
        return None
    path = ub_repo.ub_markdown_path(workspace_root, stem)
    return path if path.exists() and path.is_file() else None


def load_development_lists(
    ub_repo: UbRepository, workspace_root: Path, lesson_data: Mapping[str, object]
) -> tuple[list[str], list[str]]:
    """``(Professionalisierungsschritte, Nutzbare Ressourcen)`` der verknüpften UB-Datei; leer ohne lesbare Datei."""
    path = existing_ub_path(ub_repo, workspace_root, lesson_data)
    if path is None:
        return [], []
    try:
        _yaml, body = ub_repo.load_ub_markdown(path)
    except (OSError, RuntimeError, ValueError):
        return [], []
    return parse_development_lists(body)
