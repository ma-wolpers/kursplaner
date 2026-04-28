from pathlib import Path
from typing import Any, cast

from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData
from kursplaner.core.usecases.paste_lesson_usecase import PasteLessonUseCase
from kursplaner.core.usecases.plan_commands_usecase import PlanCommandsUseCase
from kursplaner.infrastructure.repositories.ub_repository import FileSystemUbRepository


class _PlanRepoStub:
    def save_plan_table(self, table: PlanTableData) -> None:
        return


class _LessonRepoStub:
    def __init__(self, by_stem: dict[str, Path], by_path: dict[Path, LessonYamlData]):
        self.by_stem = by_stem
        self.by_path = by_path
        self.saved: list[LessonYamlData] = []

    def resolve_row_link_path(self, table: PlanTableData, row_index: int) -> Path | None:
        cell = table.rows[row_index][2] if len(table.rows[row_index]) > 2 else ""
        raw = str(cell).strip().replace("[[", "").replace("]]", "")
        stem = raw.split("|", 1)[0].strip() if raw else ""
        return self.by_stem.get(stem)

    def load_lesson_yaml(self, path: Path) -> LessonYamlData:
        lesson = self.by_path[path]
        return LessonYamlData(lesson_path=lesson.lesson_path, data=dict(lesson.data))

    def save_lesson_yaml(self, lesson: LessonYamlData) -> None:
        self.saved.append(lesson)
        self.by_path[lesson.lesson_path] = LessonYamlData(lesson_path=lesson.lesson_path, data=dict(lesson.data))


class _LessonTransferStub:
    def __init__(self, lesson_repo: _LessonRepoStub):
        self.lesson_repo = lesson_repo

    def write_pasted_lesson(self, target_path: Path, content: str, source_stem: str, *, clear_ub_link: bool = True) -> Path:
        self.lesson_repo.save_lesson_yaml(
            LessonYamlData(
                lesson_path=target_path,
                data={
                    "Stundenthema": target_path.stem,
                    "Unterrichtsbesuch": "",
                },
            )
        )
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


def _table(markdown_path: Path, target_stem: str) -> PlanTableData:
    return PlanTableData(
        markdown_path=markdown_path,
        headers=["datum", "stunden", "inhalt"],
        rows=[["2026-05-14", "1", f"[[{target_stem}]]"]],
        start_line=1,
        end_line=1,
        source_lines=[],
        had_trailing_newline=True,
        metadata={},
    )


def test_paste_conflict_delete_removes_existing_target_ub_and_updates_overview(tmp_path):
    workspace_root = tmp_path / "7thCloud"
    plan_dir = workspace_root / "unterricht" / "Kurs D"
    plan_dir.mkdir(parents=True, exist_ok=True)

    target_existing = plan_dir / "Einheiten" / "Kurs D 01-01 Bestand.md"
    target_existing.parent.mkdir(parents=True, exist_ok=True)
    target_existing.write_text("---\nStundenthema: Bestand\n---\n", encoding="utf-8")

    ub_repo = FileSystemUbRepository()
    target_ub = ub_repo.ensure_ub_root(workspace_root) / "UB 26-05-14 Bestand.md"
    ub_repo.save_ub_markdown(
        target_ub,
        {
            "Bereich": ["Pädagogik"],
            "Langentwurf": False,
            "Beobachtungsschwerpunkt": "Fokus",
            "Einheit": "[[Kurs D 01-01 Bestand]]",
        },
        reflection_text="",
        professional_steps=[],
        usable_resources=[],
    )

    mapping = {target_existing.stem: target_existing}
    by_path = {
        target_existing: LessonYamlData(
            lesson_path=target_existing,
            data={"Unterrichtsbesuch": "[[UB 26-05-14 Bestand]]"},
        )
    }
    lesson_repo = _LessonRepoStub(mapping, by_path)
    lesson_transfer = _LessonTransferStub(lesson_repo)

    table = _table(plan_dir / "Kurs D.md", target_existing.stem)
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
        decision="delete",
        allow_delete=True,
        target_path=plan_dir / "Einheiten" / "Kurs D 01-02 Neu.md",
        content="---\nStundenthema: Neu\n---\n",
        source_stem="Kurs D 01-00 Quelle",
        ub_copy_mode="none",
    )

    assert result.proceed is True
    assert not target_existing.exists()
    assert not target_ub.exists()
    assert result.deleted_target_path == target_existing
    assert result.deleted_target_ub_path == target_ub
    assert isinstance(result.deleted_target_overview_path, Path)
    assert result.deleted_target_overview_path.exists()


def test_paste_conflict_delete_is_blocked_without_confirmation(tmp_path):
    workspace_root = tmp_path / "7thCloud"
    plan_dir = workspace_root / "unterricht" / "Kurs E"
    plan_dir.mkdir(parents=True, exist_ok=True)

    target_existing = plan_dir / "Einheiten" / "Kurs E 01-01 Bestand.md"
    target_existing.parent.mkdir(parents=True, exist_ok=True)
    target_existing.write_text("---\nStundenthema: Bestand\n---\n", encoding="utf-8")

    lesson_repo = _LessonRepoStub(
        {target_existing.stem: target_existing},
        {
            target_existing: LessonYamlData(
                lesson_path=target_existing,
                data={"Unterrichtsbesuch": ""},
            )
        },
    )
    lesson_transfer = _LessonTransferStub(lesson_repo)
    ub_repo = FileSystemUbRepository()

    table = _table(plan_dir / "Kurs E.md", target_existing.stem)
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
        decision="delete",
        allow_delete=False,
        target_path=plan_dir / "Einheiten" / "Kurs E 01-02 Neu.md",
        content="---\nStundenthema: Neu\n---\n",
        source_stem="Kurs E 01-00 Quelle",
        ub_copy_mode="none",
    )

    assert result.proceed is False
    assert target_existing.exists()
