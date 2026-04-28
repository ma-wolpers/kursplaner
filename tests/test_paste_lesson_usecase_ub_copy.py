from pathlib import Path
from typing import Any, cast

from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData
from kursplaner.core.usecases.paste_lesson_usecase import PasteLessonUseCase
from kursplaner.core.usecases.plan_commands_usecase import PlanCommandsUseCase
from kursplaner.infrastructure.repositories.ub_repository import FileSystemUbRepository


class _PlanRepoStub:
    def __init__(self):
        self.saved = 0

    def save_plan_table(self, table: PlanTableData) -> None:
        self.saved += 1


class _LessonRepoStub:
    def __init__(self):
        self.lessons: dict[Path, LessonYamlData] = {}

    def resolve_row_link_path(self, table: PlanTableData, row_index: int) -> Path | None:
        return None

    def load_lesson_yaml(self, path: Path) -> LessonYamlData:
        lesson = self.lessons[path]
        return LessonYamlData(lesson_path=lesson.lesson_path, data=dict(lesson.data))

    def save_lesson_yaml(self, lesson: LessonYamlData) -> None:
        self.lessons[lesson.lesson_path] = LessonYamlData(lesson_path=lesson.lesson_path, data=dict(lesson.data))


class _LessonTransferStub:
    def __init__(self, lesson_repo: _LessonRepoStub, source_ub_link: str):
        self.lesson_repo = lesson_repo
        self.source_ub_link = source_ub_link

    def write_pasted_lesson(self, target_path: Path, content: str, source_stem: str, *, clear_ub_link: bool = True) -> Path:
        lesson_data = {
            "Stundenthema": target_path.stem,
            "Unterrichtsbesuch": "" if clear_ub_link else self.source_ub_link,
        }
        self.lesson_repo.save_lesson_yaml(LessonYamlData(lesson_path=target_path, data=lesson_data))
        return target_path

    def relink_row_to_stem(self, table: PlanTableData, row_index: int, stem: str, *, preserve_alias: bool = False) -> None:
        table.rows[row_index][2] = f"[[{stem}]]"

    def delete_lesson_file(self, path: Path) -> None:
        path.unlink(missing_ok=True)

    def next_unique_stem_path(self, target_dir: Path, preferred_stem: str) -> Path:
        return target_dir / f"{preferred_stem}.md"

    def lesson_dir_for_table(self, table: PlanTableData) -> Path:
        return table.markdown_path.parent / "Einheiten"

    def read_lesson_content(self, source: Path) -> str:
        return "---\nStundenthema: Demo\n---\n"


def _table(markdown_path: Path) -> PlanTableData:
    return PlanTableData(
        markdown_path=markdown_path,
        headers=["datum", "stunden", "inhalt"],
        rows=[["2026-05-12", "1", ""]],
        start_line=1,
        end_line=1,
        source_lines=[],
        had_trailing_newline=True,
        metadata={},
    )


def test_paste_usecase_copies_linked_ub_when_requested(tmp_path):
    workspace_root = tmp_path / "7thCloud"
    plan_dir = workspace_root / "unterricht" / "Kurs C"
    plan_dir.mkdir(parents=True, exist_ok=True)

    ub_repo = FileSystemUbRepository()
    source_ub_path = ub_repo.ensure_ub_root(workspace_root) / "UB 26-04-28 Thema.md"
    ub_repo.save_ub_markdown(
        source_ub_path,
        {
            "Bereich": ["Pädagogik"],
            "Langentwurf": False,
            "Beobachtungsschwerpunkt": "Fokus",
            "Einheit": "[[Kurs C 01-01 Thema]]",
        },
        reflection_text="Reflexion",
        professional_steps=["Schritt"],
        usable_resources=["Ressource"],
    )

    lesson_repo = _LessonRepoStub()
    lesson_transfer = _LessonTransferStub(lesson_repo, source_ub_link="[[UB 26-04-28 Thema]]")
    table = _table(plan_dir / "Kurs C.md")
    target_path = plan_dir / "Einheiten" / "Kurs C 01-02 Thema.md"

    usecase = PasteLessonUseCase(
        lesson_repo=cast(Any, lesson_repo),
        plan_repo=cast(Any, _PlanRepoStub()),
        plan_commands=PlanCommandsUseCase(lesson_repo=cast(Any, lesson_repo)),
        lesson_transfer=cast(Any, lesson_transfer),
        ub_repo=cast(Any, ub_repo),
    )

    result = usecase.execute(
        table=table,
        row_index=0,
        decision="move",
        allow_delete=False,
        target_path=target_path,
        content="---\nStundenthema: Demo\n---\n",
        source_stem="Kurs C 01-01 Thema",
        ub_copy_mode="copy",
    )

    assert result.proceed is True
    assert isinstance(result.created_path, Path)
    assert isinstance(result.ub_path, Path)
    assert result.ub_path != source_ub_path
    assert result.ub_path.exists()
    saved_target = lesson_repo.load_lesson_yaml(target_path)
    assert str(saved_target.data.get("Unterrichtsbesuch", "")).startswith("[[UB ")
    assert saved_target.data.get("Unterrichtsbesuch") != "[[UB 26-04-28 Thema]]"
    assert isinstance(result.overview_path, Path)
    assert result.overview_path.exists()
