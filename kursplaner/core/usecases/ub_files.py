"""UB-Datei einer Einheit finden und ihre Entwicklungslisten lesen – je eine Stelle.

Stamm aus dem Lesson-YAML: `unterrichtsbesuch_policy.ub_link_stem`; Dateiname:
`UbRepository.ub_markdown_path`; Listen im Frontmatter:
`unterrichtsbesuch_policy.ub_development_lists`.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from kursplaner.core.domain.unterrichtsbesuch_policy import ub_development_lists, ub_link_stem
from kursplaner.core.ports.repositories import UbRepository


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
    """``(Baustellen, Ressourcen)`` der verknüpften UB-Datei; leer ohne lesbare Datei.

    Ein Eintrag, der die Listen-Invariante verletzt, gilt wie eine nicht lesbare
    Datei (`ListFieldViolationError` ist ein `RuntimeError`): die Einheit bleibt
    ladbar, die UB-Zellen bleiben leer.
    """
    path = existing_ub_path(ub_repo, workspace_root, lesson_data)
    if path is None:
        return [], []
    try:
        ub_yaml, _body = ub_repo.load_ub_markdown(path)
        return ub_development_lists(ub_yaml, source_label=str(path))
    except (OSError, RuntimeError, ValueError):
        return [], []
