from __future__ import annotations

from pathlib import Path

LESSON_DIR_PRIMARY = "Einheiten"


def is_lesson_dir_name(name: str) -> bool:
    """Checks whether a directory name is a managed lesson directory."""
    lowered = str(name or "").strip().lower()
    if not lowered:
        return False
    return lowered == LESSON_DIR_PRIMARY.lower()


def managed_lesson_dir_names() -> tuple[str, ...]:
    """Returns known lesson directory names in preference order."""
    return (LESSON_DIR_PRIMARY,)


def resolve_lesson_dir(plan_dir: Path, *, create_if_missing: bool = False) -> Path:
    """Resolves the managed lesson directory for a plan (`Einheiten`)."""
    primary = plan_dir / LESSON_DIR_PRIMARY
    if create_if_missing:
        primary.mkdir(parents=True, exist_ok=True)
    return primary
