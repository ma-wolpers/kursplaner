from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.remove_unit_ub_link_usecase import RemoveUnitUbLinkUseCase
from kursplaner.infrastructure.repositories.lesson_repository import FileSystemLessonRepository
from kursplaner.infrastructure.repositories.ub_repository import FileSystemUbRepository


def _write_unterricht_lesson(path: Path, ub_link: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "Stundentyp: Unterricht\n"
        "Dauer: 2\n"
        "Stundenthema: Funktionen\n"
        "Oberthema: Analysis\n"
        'Stundenziel: ""\n'
        "Kompetenzen:\n"
        '  - ""\n'
        "Material:\n"
        '  - ""\n'
        f"Unterrichtsbesuch: {ub_link}\n"
        "---\n\n"
        "# Inhalt\n",
        encoding="utf-8",
    )


def _table(plan_path: Path, lesson_stem: str) -> PlanTableData:
    return PlanTableData(
        markdown_path=plan_path,
        headers=["Datum", "Stunden", "Inhalt"],
        rows=[["31-03-26", "2", f"[[{lesson_stem}]]"]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={"Kursfach": "Mathematik", "Lerngruppe": "[[gruen-6]]"},
    )


def test_remove_unit_ub_link_clears_lesson_reference_and_keeps_ub_file(tmp_path):
    workspace_root = tmp_path / "7thCloud"
    plan_dir = workspace_root / "7thVault" / "🏫 Pädagogik" / "10 Unterricht" / "Mathe Kurs"
    plan_dir.mkdir(parents=True)

    lesson_path = plan_dir / "Einheiten" / "gruen-6 03-31 Funktionen.md"
    ub_stem = "UB 26-03-31 Funktionen"
    _write_unterricht_lesson(lesson_path, f"[[{ub_stem}]]")

    ub_repo = FileSystemUbRepository()
    ub_path = ub_repo.ensure_ub_root(workspace_root) / f"{ub_stem}.md"
    ub_repo.save_ub_markdown(
        ub_path,
        yaml_data={
            "Bereich": ["Pädagogik"],
            "Langentwurf": False,
            "Beobachtungsschwerpunkt": "Aktivierung",
            "Einheit": "[[gruen-6 03-31 Funktionen]]",
        },
        reflection_text="",
        professional_steps=[],
        usable_resources=[],
    )

    table = _table(plan_dir / "Mathe Kurs.md", lesson_path.stem)
    usecase = RemoveUnitUbLinkUseCase(FileSystemLessonRepository(), ub_repo)

    result = usecase.execute(
        workspace_root=workspace_root,
        table=table,
        row_index=0,
        delete_ub_markdown=False,
    )

    assert result.proceed is True
    assert result.ub_file_deleted is False
    assert ub_path.exists()
    lesson_text = lesson_path.read_text(encoding="utf-8")
    assert "Unterrichtsbesuch:" in lesson_text
    assert f"[[{ub_stem}]]" not in lesson_text


def test_remove_unit_ub_link_can_delete_ub_file(tmp_path):
    workspace_root = tmp_path / "7thCloud"
    plan_dir = workspace_root / "7thVault" / "🏫 Pädagogik" / "10 Unterricht" / "Mathe Kurs"
    plan_dir.mkdir(parents=True)

    lesson_path = plan_dir / "Einheiten" / "gruen-6 03-31 Funktionen.md"
    ub_stem = "UB 26-03-31 Funktionen"
    _write_unterricht_lesson(lesson_path, f"[[{ub_stem}]]")

    ub_repo = FileSystemUbRepository()
    ub_path = ub_repo.ensure_ub_root(workspace_root) / f"{ub_stem}.md"
    ub_repo.save_ub_markdown(
        ub_path,
        yaml_data={
            "Bereich": ["Pädagogik"],
            "Langentwurf": False,
            "Beobachtungsschwerpunkt": "Aktivierung",
            "Einheit": "[[gruen-6 03-31 Funktionen]]",
        },
        reflection_text="",
        professional_steps=[],
        usable_resources=[],
    )

    table = _table(plan_dir / "Mathe Kurs.md", lesson_path.stem)
    usecase = RemoveUnitUbLinkUseCase(FileSystemLessonRepository(), ub_repo)

    result = usecase.execute(
        workspace_root=workspace_root,
        table=table,
        row_index=0,
        delete_ub_markdown=True,
    )

    assert result.proceed is True
    assert result.ub_file_deleted is True
    assert not ub_path.exists()
