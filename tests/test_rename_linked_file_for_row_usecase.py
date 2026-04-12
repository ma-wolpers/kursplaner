from pathlib import Path
from typing import Any, cast

from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData
from kursplaner.core.usecases.rename_linked_file_for_row_usecase import RenameLinkedFileForRowUseCase
from kursplaner.infrastructure.repositories.lesson_repository import FileSystemLessonRepository
from kursplaner.infrastructure.repositories.ub_repository import FileSystemUbRepository


class _StubPlanRepository:
    def __init__(self):
        self.save_calls = 0

    def save_plan_table(self, _table: PlanTableData) -> None:
        self.save_calls += 1


class _StubLessonTransfer:
    def __init__(self, lesson_path: Path):
        self.lesson_path = lesson_path

    def resolve_existing_link(self, _table: PlanTableData, _row_index: int) -> Path | None:
        return self.lesson_path

    @staticmethod
    def compute_rename_target(link: Path, desired_stem: str) -> Path:
        return link.with_name(f"{desired_stem}.md")

    @staticmethod
    def rename_lesson_file(source: Path, target: Path) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        return source.rename(target)

    @staticmethod
    def relink_row_to_stem(table: PlanTableData, row_index: int, stem: str, preserve_alias: bool = True) -> None:
        _ = preserve_alias
        table.rows[row_index][2] = f"[[{stem}]]"


def _write_lesson(path: Path, ub_link: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lesson = LessonYamlData(
        lesson_path=path,
        data={
            "Stundentyp": "Unterricht",
            "Dauer": "2",
            "Stundenthema": "Funktionen",
            "Oberthema": "Analysis",
            "Stundenziel": "",
            "Kompetenzen": [],
            "Material": [],
            "Unterrichtsbesuch": ub_link,
        },
    )
    FileSystemLessonRepository().save_lesson_yaml(lesson)


def test_rename_updates_ub_file_backlink_and_lesson_ub_link(tmp_path):
    workspace_root = tmp_path / "7thCloud"
    plan_dir = workspace_root / "7thVault" / "🏫 Pädagogik" / "10 Unterricht" / "Mathe Kurs"
    plan_dir.mkdir(parents=True)

    lesson_path = plan_dir / "Einheiten" / "gruen-6 03-31 Funktionen.md"
    _write_lesson(lesson_path, "[[UB 26-03-31 Funktionen]]")

    ub_repo = FileSystemUbRepository()
    ub_path = ub_repo.unique_ub_markdown_path(workspace_root, "UB 26-03-31 Funktionen")
    ub_repo.save_ub_markdown(
        ub_path,
        {
            "Bereich": ["Pädagogik", "Mathematik"],
            "Langentwurf": True,
            "Beobachtungsschwerpunkt": "Aktivierung",
            "Einheit": "[[gruen-6 03-31 Funktionen]]",
        },
        reflection_text="Reflexion",
        professional_steps=["Schritt 1"],
        usable_resources=["Ressource 1"],
    )

    table = PlanTableData(
        markdown_path=plan_dir / "Mathe Kurs.md",
        headers=["Datum", "Stunden", "Inhalt"],
        rows=[["31-03-26", "2", "[[gruen-6 03-31 Funktionen]]"]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={"Kursfach": "Mathematik", "Lerngruppe": "[[gruen-6]]"},
    )

    usecase = RenameLinkedFileForRowUseCase(
        plan_repo=cast(Any, _StubPlanRepository()),
        lesson_transfer=cast(Any, _StubLessonTransfer(lesson_path)),
        lesson_repo=FileSystemLessonRepository(),
        ub_repo=ub_repo,
    )

    result = usecase.execute(
        table=table,
        row_index=0,
        desired_stem="gruen-6 03-31 Neue Funktionen",
        allow_rename=True,
        allow_plan_save=True,
    )

    assert result.proceed is True
    assert result.target_path is not None
    assert result.target_path.name == "gruen-6 03-31 Neue Funktionen.md"
    assert result.target_path.exists()

    expected_ub = ub_repo.ensure_ub_root(workspace_root) / "UB 26-03-31 Neue Funktionen.md"
    assert expected_ub.exists()

    lesson_after = FileSystemLessonRepository().load_lesson_yaml(result.target_path)
    assert lesson_after.data.get("Unterrichtsbesuch") == "[[UB 26-03-31 Neue Funktionen]]"

    ub_yaml, ub_body = ub_repo.load_ub_markdown(expected_ub)
    assert ub_yaml.get("Einheit") == "[[gruen-6 03-31 Neue Funktionen]]"
    assert "Schritt 1" in ub_body
    assert "Ressource 1" in ub_body

    overview = ub_repo.load_ub_overview(workspace_root)
    assert "[[UB 26-03-31 Neue Funktionen]]" in overview


def test_rename_without_plan_save_succeeds_for_intermediate_flow(tmp_path):
    lesson_path = tmp_path / "Einheiten" / "gruen-6 02-06 Fach-Diagnose.md"
    _write_lesson(lesson_path, "")

    table = PlanTableData(
        markdown_path=tmp_path / "Plan.md",
        headers=["Datum", "Stunden", "Inhalt"],
        rows=[["06.02.2026", "2", "[[gruen-6 02-06 Fach-Diagnose]]"]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={"Lerngruppe": "[[gruen-6]]"},
    )

    plan_repo = _StubPlanRepository()
    usecase = RenameLinkedFileForRowUseCase(
        plan_repo=cast(Any, plan_repo),
        lesson_transfer=cast(Any, _StubLessonTransfer(lesson_path)),
        lesson_repo=FileSystemLessonRepository(),
    )

    result = usecase.execute(
        table=table,
        row_index=0,
        desired_stem="gruen-6 02-06 Supertrumpf Kodierung",
        allow_rename=True,
        allow_plan_save=False,
    )

    assert result.proceed is True
    assert result.error_message is None
    assert result.target_path is not None
    assert result.target_path.name == "gruen-6 02-06 Supertrumpf Kodierung.md"
    assert result.target_path.exists()
    assert table.rows[0][2] == "[[gruen-6 02-06 Supertrumpf Kodierung]]"
    assert plan_repo.save_calls == 0
