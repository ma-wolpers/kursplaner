from pathlib import Path
from typing import Any, cast

from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData
from kursplaner.core.usecases.rebuild_file_relation_registry_usecase import (
    RebuildFileRelationRegistryUseCase,
)


class _PlanRepoStub:
    def __init__(self, tables: dict[Path, PlanTableData], additional_paths: list[Path] | None = None):
        self._tables = tables
        self._paths = list(tables.keys()) + list(additional_paths or [])

    def list_plan_markdown_files(self, _base_dir: Path) -> list[Path]:
        return list(self._paths)

    def load_plan_table(self, markdown_path: Path) -> PlanTableData:
        table = self._tables.get(markdown_path)
        if table is None:
            raise RuntimeError("missing table")
        return table


class _LessonRepoStub:
    def __init__(self, row_links: dict[tuple[Path, int], Path], yaml_by_path: dict[Path, LessonYamlData]):
        self._row_links = row_links
        self._yaml_by_path = yaml_by_path

    def resolve_row_link_path(self, table: PlanTableData, row_index: int) -> Path | None:
        return self._row_links.get((table.markdown_path, row_index))

    def load_lesson_yaml(self, path: Path) -> LessonYamlData:
        yaml_data = self._yaml_by_path.get(path)
        if yaml_data is None:
            raise RuntimeError("missing lesson")
        return yaml_data


class _RelationRegistryRepoStub:
    def __init__(self):
        self.saved_snapshot = None

    def save_snapshot(self, snapshot) -> None:
        self.saved_snapshot = snapshot


def _build_table(plan_path: Path) -> PlanTableData:
    return PlanTableData(
        markdown_path=plan_path,
        headers=["Datum", "Stunden", "Inhalt"],
        rows=[
            ["10-03-26", "2", "[[M GK blau-1 0310 Einheit]]"],
            ["17-03-26", "2", "[[M GK blau-1 0317 Einheit]]"],
        ],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=True,
        metadata={"Lerngruppe": "[[GK blau-1]]"},
    )


def test_rebuild_file_relation_registry_collects_plan_links_and_sequences(tmp_path):
    workspace_root = tmp_path / "workspace"
    (workspace_root / "7thVault").mkdir(parents=True, exist_ok=True)

    plan_path = workspace_root / "Unterricht" / "M GK blau-1 26-2" / "M GK blau-1 26-2.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text("# Plan\n", encoding="utf-8")

    sequence_dir = plan_path.parent / "Sequenzen"
    sequence_dir.mkdir(parents=True, exist_ok=True)
    sequence_a = sequence_dir / "Analysis GK blau-1 26-2.md"
    sequence_b = sequence_dir / "Algebra GK blau-1 26-2.md"
    sequence_a.write_text("# A\n", encoding="utf-8")
    sequence_b.write_text("# B\n", encoding="utf-8")

    lesson_a = plan_path.parent / "Einheiten" / "M GK blau-1 0310 Einheit.md"
    lesson_b = plan_path.parent / "Einheiten" / "M GK blau-1 0317 Einheit.md"
    lesson_a.parent.mkdir(parents=True, exist_ok=True)
    lesson_a.write_text("---\nStundenthema: A\n---\n", encoding="utf-8")
    lesson_b.write_text("---\nStundenthema: B\n---\n", encoding="utf-8")

    table = _build_table(plan_path)
    broken_plan = workspace_root / "Unterricht" / "broken" / "broken.md"

    plan_repo = _PlanRepoStub({plan_path: table}, additional_paths=[broken_plan])
    lesson_repo = _LessonRepoStub(
        row_links={(plan_path, 0): lesson_a, (plan_path, 1): lesson_b},
        yaml_by_path={
            lesson_a: LessonYamlData(
                lesson_path=lesson_a,
                data={"Unterrichtsbesuch": "[[UB 26-03-10 Funktionen]]"},
            ),
            lesson_b: LessonYamlData(
                lesson_path=lesson_b,
                data={},
            ),
        },
    )
    registry_repo = _RelationRegistryRepoStub()

    usecase = RebuildFileRelationRegistryUseCase(
        plan_repo=cast(Any, plan_repo),
        lesson_repo=cast(Any, lesson_repo),
        relation_registry_repo=cast(Any, registry_repo),
    )

    result = usecase.execute(workspace_root / "Unterricht")

    assert result.plan_count == 1
    assert result.lesson_count == 2
    assert result.ub_count == 1
    assert result.sequence_count == 2
    assert result.failed_plan_count == 1

    snapshot = registry_repo.saved_snapshot
    assert snapshot is not None
    assert len(snapshot.courses) == 1

    entry = snapshot.courses[0]
    assert entry.course_plan_path == plan_path.resolve()
    assert set(entry.lesson_paths) == {lesson_a.resolve(), lesson_b.resolve()}
    assert set(entry.sequence_paths) == {sequence_a.resolve(), sequence_b.resolve()}

    expected_ub = (
        workspace_root
        / "7thVault"
        / "🏫 Pädagogik"
        / "00 Orga"
        / "02 UBs"
        / "UB 26-03-10 Funktionen.md"
    )
    assert entry.ub_paths == (expected_ub.resolve(),)
