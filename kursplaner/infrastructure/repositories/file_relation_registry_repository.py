from __future__ import annotations

import json
from pathlib import Path

from bw_libs.app_paths import atomic_write_json
from kursplaner.core.config.settings import SCRIPT_DIR
from kursplaner.core.domain.file_relation_registry import (
    CourseFileRelations,
    FileRelationRegistrySnapshot,
    empty_relation_registry,
)


class FileSystemFileRelationRegistryRepository:
    """Persist file relation snapshots in one JSON file under config."""

    def __init__(self, registry_path: Path | None = None):
        self._registry_path = registry_path or (SCRIPT_DIR / "config" / "file_relation_registry.json")

    def registry_path(self) -> Path:
        """Return the absolute registry file path."""
        return self._registry_path.expanduser().resolve()

    def load_snapshot(self) -> FileRelationRegistrySnapshot:
        """Load and deserialize the relation snapshot from disk."""
        path = self.registry_path()
        if not path.exists() or not path.is_file():
            return empty_relation_registry()

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return empty_relation_registry()

        if not isinstance(payload, dict):
            return empty_relation_registry()

        version = int(payload.get("version", 1) or 1)
        generated_at = str(payload.get("generated_at", "") or "")
        courses_raw = payload.get("courses", [])
        if not isinstance(courses_raw, list):
            courses_raw = []

        courses: list[CourseFileRelations] = []
        for item in courses_raw:
            if not isinstance(item, dict):
                continue
            plan_text = str(item.get("course_plan_path", "")).strip()
            if not plan_text:
                continue
            lesson_paths_raw = item.get("lesson_paths", [])
            ub_paths_raw = item.get("ub_paths", [])
            sequence_paths_raw = item.get("sequence_paths", [])

            lesson_paths = tuple(
                sorted(
                    {
                        Path(str(path_text)).expanduser().resolve()
                        for path_text in lesson_paths_raw
                        if str(path_text).strip()
                    },
                    key=lambda value: str(value).lower(),
                )
            )
            ub_paths = tuple(
                sorted(
                    {
                        Path(str(path_text)).expanduser().resolve()
                        for path_text in ub_paths_raw
                        if str(path_text).strip()
                    },
                    key=lambda value: str(value).lower(),
                )
            )
            sequence_paths = tuple(
                sorted(
                    {
                        Path(str(path_text)).expanduser().resolve()
                        for path_text in sequence_paths_raw
                        if str(path_text).strip()
                    },
                    key=lambda value: str(value).lower(),
                )
            )

            courses.append(
                CourseFileRelations(
                    course_plan_path=Path(plan_text).expanduser().resolve(),
                    lesson_paths=lesson_paths,
                    ub_paths=ub_paths,
                    sequence_paths=sequence_paths,
                )
            )

        return FileRelationRegistrySnapshot(
            version=max(1, version),
            generated_at=generated_at,
            courses=tuple(sorted(courses, key=lambda item: str(item.course_plan_path).lower())),
        )

    def save_snapshot(self, snapshot: FileRelationRegistrySnapshot) -> None:
        """Persist one complete relation snapshot to disk."""
        payload = {
            "version": int(snapshot.version),
            "generated_at": str(snapshot.generated_at),
            "courses": [
                {
                    "course_plan_path": str(entry.course_plan_path.expanduser().resolve()),
                    "lesson_paths": [str(path.expanduser().resolve()) for path in entry.lesson_paths],
                    "ub_paths": [str(path.expanduser().resolve()) for path in entry.ub_paths],
                    "sequence_paths": [str(path.expanduser().resolve()) for path in entry.sequence_paths],
                }
                for entry in snapshot.courses
            ],
        }
        atomic_write_json(self.registry_path(), payload)
