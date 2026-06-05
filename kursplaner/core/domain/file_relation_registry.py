from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class CourseFileRelations:
    """Aggregated file relations for a single course plan markdown file."""

    course_plan_path: Path
    lesson_paths: tuple[Path, ...]
    ub_paths: tuple[Path, ...]
    sequence_paths: tuple[Path, ...]


@dataclass(frozen=True)
class FileRelationRegistrySnapshot:
    """Immutable relation snapshot persisted to disk."""

    version: int
    generated_at: str
    courses: tuple[CourseFileRelations, ...]


def utc_timestamp() -> str:
    """Return an ISO UTC timestamp used in relation snapshots."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def unique_sorted_paths(paths: list[Path]) -> tuple[Path, ...]:
    """Normalize paths to unique absolute values with stable ordering."""
    normalized = {path.expanduser().resolve() for path in paths}
    return tuple(sorted(normalized, key=lambda item: str(item).lower()))


def empty_relation_registry(*, version: int = 1) -> FileRelationRegistrySnapshot:
    """Return an empty relation snapshot."""
    return FileRelationRegistrySnapshot(version=version, generated_at=utc_timestamp(), courses=())
