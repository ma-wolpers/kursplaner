from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.config.path_store import infer_workspace_root_from_path
from kursplaner.core.domain.file_relation_registry import (
    CourseFileRelations,
    FileRelationRegistrySnapshot,
    unique_sorted_paths,
    utc_timestamp,
)
from kursplaner.core.domain.sequence_planning import SEQUENCE_DIR_NAME
from kursplaner.core.domain.unterrichtsbesuch_policy import UB_ROOT_RELATIVE_PARTS
from kursplaner.core.domain.wiki_links import strip_wiki_link
from kursplaner.core.ports.repositories import (
    FileRelationRegistryRepository,
    LessonRepository,
    PlanRepository,
)


@dataclass(frozen=True)
class RebuildFileRelationRegistryResult:
    """Summary information for one complete relation-registry rebuild run."""

    plan_count: int
    lesson_count: int
    ub_count: int
    sequence_count: int
    failed_plan_count: int


class RebuildFileRelationRegistryUseCase:
    """Rebuild the persistent file relation registry by scanning course plans."""

    def __init__(
        self,
        *,
        plan_repo: PlanRepository,
        lesson_repo: LessonRepository,
        relation_registry_repo: FileRelationRegistryRepository,
    ):
        self._plan_repo = plan_repo
        self._lesson_repo = lesson_repo
        self._relation_registry_repo = relation_registry_repo

    @staticmethod
    def _sequence_paths_for_plan(plan_markdown_path: Path) -> list[Path]:
        sequence_dir = plan_markdown_path.parent / SEQUENCE_DIR_NAME
        if not sequence_dir.exists() or not sequence_dir.is_dir():
            return []
        return sorted(
            [path.resolve() for path in sequence_dir.glob("*.md") if path.is_file()],
            key=lambda item: item.name.lower(),
        )

    @staticmethod
    def _ub_path_from_stem(*, plan_markdown_path: Path, ub_stem: str) -> Path:
        workspace_root = infer_workspace_root_from_path(plan_markdown_path)
        return workspace_root.joinpath(*UB_ROOT_RELATIVE_PARTS) / f"{ub_stem}.md"

    def execute(self, base_dir: Path) -> RebuildFileRelationRegistryResult:
        """Scan all plans beneath ``base_dir`` and persist an updated registry snapshot."""
        resolved_base_dir = base_dir.expanduser().resolve()
        plan_paths = self._plan_repo.list_plan_markdown_files(resolved_base_dir)

        relations: list[CourseFileRelations] = []
        lesson_count = 0
        ub_count = 0
        sequence_count = 0
        failed_plan_count = 0

        for plan_path in plan_paths:
            try:
                table = self._plan_repo.load_plan_table(plan_path)
            except Exception:
                failed_plan_count += 1
                continue

            lesson_paths: list[Path] = []
            ub_paths: list[Path] = []
            for row_index in range(len(table.rows)):
                lesson_path = self._lesson_repo.resolve_row_link_path(table, row_index)
                if not isinstance(lesson_path, Path):
                    continue
                resolved_lesson_path = lesson_path.expanduser().resolve()
                lesson_paths.append(resolved_lesson_path)

                try:
                    lesson_yaml = self._lesson_repo.load_lesson_yaml(resolved_lesson_path)
                except Exception:
                    continue

                ub_stem = strip_wiki_link(str(lesson_yaml.data.get("Unterrichtsbesuch", "")).strip())
                if ub_stem:
                    ub_paths.append(self._ub_path_from_stem(plan_markdown_path=table.markdown_path, ub_stem=ub_stem))

            sequence_paths = self._sequence_paths_for_plan(table.markdown_path)

            dedup_lessons = unique_sorted_paths(lesson_paths)
            dedup_ubs = unique_sorted_paths(ub_paths)
            dedup_sequences = unique_sorted_paths(sequence_paths)

            lesson_count += len(dedup_lessons)
            ub_count += len(dedup_ubs)
            sequence_count += len(dedup_sequences)

            relations.append(
                CourseFileRelations(
                    course_plan_path=table.markdown_path.expanduser().resolve(),
                    lesson_paths=dedup_lessons,
                    ub_paths=dedup_ubs,
                    sequence_paths=dedup_sequences,
                )
            )

        snapshot = FileRelationRegistrySnapshot(
            version=1,
            generated_at=utc_timestamp(),
            courses=tuple(sorted(relations, key=lambda item: str(item.course_plan_path).lower())),
        )
        self._relation_registry_repo.save_snapshot(snapshot)

        return RebuildFileRelationRegistryResult(
            plan_count=len(relations),
            lesson_count=lesson_count,
            ub_count=ub_count,
            sequence_count=sequence_count,
            failed_plan_count=failed_plan_count,
        )
