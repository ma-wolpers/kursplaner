from pathlib import Path
from typing import Any, cast

from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData
from kursplaner.core.usecases.clear_selected_lesson_usecase import ClearSelectedLessonUseCase
from kursplaner.core.usecases.plan_commands_usecase import PlanCommandsUseCase
from kursplaner.infrastructure.repositories.lesson_file_repository import FileSystemLessonFileRepository
from kursplaner.infrastructure.repositories.ub_repository import FileSystemUbRepository


class _PlanRepoStub:
    def __init__(self):
        self.saved_tables: list[PlanTableData] = []

    def save_plan_table(self, table: PlanTableData) -> None:
        self.saved_tables.append(table)


class _LessonRepoStub:
    def __init__(self, lesson_path: Path, lesson_yaml: LessonYamlData):
        self.lesson_path = lesson_path
        self.lesson_yaml = lesson_yaml

    def resolve_row_link_path(self, table: PlanTableData, row_index: int) -> Path | None:
        return self.lesson_path

    def load_lesson_yaml(self, path: Path) -> LessonYamlData:
        return LessonYamlData(lesson_path=path, data=dict(self.lesson_yaml.data))


def _build_table(markdown_path: Path, lesson_stem: str) -> PlanTableData:
    return PlanTableData(
        markdown_path=markdown_path,
        headers=["datum", "stunden", "inhalt"],
        rows=[["2026-04-28", "1", f"[[{lesson_stem}]]"]],
        start_line=1,
        end_line=1,
        source_lines=[],
        had_trailing_newline=True,
        metadata={},
    )


def test_clear_selected_lesson_deletes_lesson_and_ub_when_requested(tmp_path):
    workspace_root = tmp_path / "7thCloud"
    plan_dir = workspace_root / "unterricht" / "Kurs A"
    plan_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = plan_dir / "Kurs A.md"
    lesson_path = plan_dir / "Einheiten" / "Kurs A 01-01 Thema.md"
    lesson_path.parent.mkdir(parents=True, exist_ok=True)
    lesson_path.write_text("---\nStundenthema: Thema\n---\n", encoding="utf-8")

    ub_repo = FileSystemUbRepository()
    ub_path = ub_repo.ensure_ub_root(workspace_root) / "UB 26-04-28 Thema.md"
    ub_repo.save_ub_markdown(
        ub_path,
        {
            "Bereich": ["Pädagogik"],
            "Langentwurf": False,
            "Beobachtungsschwerpunkt": "Diagnose",
            "Einheit": "[[Kurs A 01-01 Thema]]",
        },
        reflection_text="",
        professional_steps=[],
        usable_resources=[],
    )

    lesson_repo = _LessonRepoStub(
        lesson_path=lesson_path,
        lesson_yaml=LessonYamlData(
            lesson_path=lesson_path,
            data={"Unterrichtsbesuch": "[[UB 26-04-28 Thema]]"},
        ),
    )

    table = _build_table(markdown_path, lesson_path.stem)
    usecase = ClearSelectedLessonUseCase(
        plan_repo=cast(Any, _PlanRepoStub()),
        plan_commands=PlanCommandsUseCase(lesson_repo=cast(Any, lesson_repo)),
        lesson_repo=cast(Any, lesson_repo),
        lesson_file_repo=cast(Any, FileSystemLessonFileRepository()),
        ub_repo=cast(Any, ub_repo),
    )

    result = usecase.execute(
        table,
        0,
        workspace_root=workspace_root,
        delete_lesson_markdown=True,
        delete_ub_markdown=True,
    )

    assert table.rows[0][2] == ""
    assert not lesson_path.exists()
    assert not ub_path.exists()
    assert result.lesson_path == lesson_path
    assert result.ub_path == ub_path
    assert isinstance(result.overview_path, Path)
    assert result.overview_path.exists()


def test_clear_selected_lesson_can_keep_ub_file(tmp_path):
    workspace_root = tmp_path / "7thCloud"
    plan_dir = workspace_root / "unterricht" / "Kurs B"
    plan_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = plan_dir / "Kurs B.md"
    lesson_path = plan_dir / "Einheiten" / "Kurs B 01-01 Thema.md"
    lesson_path.parent.mkdir(parents=True, exist_ok=True)
    lesson_path.write_text("---\nStundenthema: Thema\n---\n", encoding="utf-8")

    ub_repo = FileSystemUbRepository()
    ub_path = ub_repo.ensure_ub_root(workspace_root) / "UB 26-04-28 Thema B.md"
    ub_repo.save_ub_markdown(
        ub_path,
        {
            "Bereich": ["Pädagogik"],
            "Langentwurf": True,
            "Beobachtungsschwerpunkt": "Fokus",
            "Einheit": "[[Kurs B 01-01 Thema]]",
        },
        reflection_text="",
        professional_steps=[],
        usable_resources=[],
    )

    lesson_repo = _LessonRepoStub(
        lesson_path=lesson_path,
        lesson_yaml=LessonYamlData(
            lesson_path=lesson_path,
            data={"Unterrichtsbesuch": "[[UB 26-04-28 Thema B]]"},
        ),
    )

    table = _build_table(markdown_path, lesson_path.stem)
    usecase = ClearSelectedLessonUseCase(
        plan_repo=cast(Any, _PlanRepoStub()),
        plan_commands=PlanCommandsUseCase(lesson_repo=cast(Any, lesson_repo)),
        lesson_repo=cast(Any, lesson_repo),
        lesson_file_repo=cast(Any, FileSystemLessonFileRepository()),
        ub_repo=cast(Any, ub_repo),
    )

    result = usecase.execute(
        table,
        0,
        workspace_root=workspace_root,
        delete_lesson_markdown=True,
        delete_ub_markdown=False,
    )

    assert table.rows[0][2] == ""
    assert not lesson_path.exists()
    assert ub_path.exists()
    assert result.ub_path == ub_path
    assert isinstance(result.overview_path, Path)
    assert result.overview_path.exists()
