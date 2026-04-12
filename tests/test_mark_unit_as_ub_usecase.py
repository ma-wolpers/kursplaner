from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.mark_unit_as_ub_usecase import MarkUnitAsUbUseCase
from kursplaner.infrastructure.repositories.lesson_repository import FileSystemLessonRepository
from kursplaner.infrastructure.repositories.ub_repository import FileSystemUbRepository


def _write_unterricht_lesson(path: Path, title: str = "Funktionen"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "Stundentyp: Unterricht\n"
        "Dauer: 2\n"
        f"Stundenthema: {title}\n"
        "Oberthema: Analysis\n"
        'Stundenziel: ""\n'
        "Kompetenzen:\n"
        '  - ""\n'
        "Material:\n"
        '  - ""\n'
        "Unterrichtsbesuch: \n"
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


def test_mark_unit_as_ub_creates_ub_file_updates_lesson_and_overview(tmp_path):
    workspace_root = tmp_path / "7thCloud"
    plan_dir = workspace_root / "7thVault" / "🏫 Pädagogik" / "10 Unterricht" / "Mathe Kurs"
    plan_dir.mkdir(parents=True)

    lesson_path = plan_dir / "Einheiten" / "gruen-6 03-31 Funktionen.md"
    _write_unterricht_lesson(lesson_path)

    table = _table(plan_dir / "Mathe Kurs.md", lesson_path.stem)

    usecase = MarkUnitAsUbUseCase(
        lesson_repo=FileSystemLessonRepository(),
        ub_repo=FileSystemUbRepository(),
    )

    result = usecase.execute(
        workspace_root=workspace_root,
        table=table,
        row_index=0,
        ub_kinds=["Pädagogik", "Fach"],
        langentwurf=True,
        beobachtungsschwerpunkt="Aktivierung",
    )

    assert result.proceed is True
    assert isinstance(result.ub_path, Path)
    assert result.ub_path.exists()
    assert isinstance(result.overview_path, Path)
    assert result.overview_path.exists()

    lesson_text = lesson_path.read_text(encoding="utf-8")
    assert 'Unterrichtsbesuch: "[[UB 26-03-31 Funktionen]]"' in lesson_text

    ub_text = result.ub_path.read_text(encoding="utf-8")
    assert "Bereich:" in ub_text
    assert '  - "Pädagogik"' in ub_text
    assert '  - "Mathematik"' in ub_text
    assert "Langentwurf: true" in ub_text
    assert "Beobachtungsschwerpunkt: Aktivierung" in ub_text
    assert 'Einheit: "[[gruen-6 03-31 Funktionen]]"' in ub_text

    overview_text = result.overview_path.read_text(encoding="utf-8")
    assert "# UB Übersicht" in overview_text
    assert "[[UB 26-03-31 Funktionen]]" in overview_text


def test_mark_unit_as_ub_rejects_non_unterricht(tmp_path):
    workspace_root = tmp_path / "7thCloud"
    plan_dir = workspace_root / "7thVault" / "🏫 Pädagogik" / "10 Unterricht" / "Mathe Kurs"
    plan_dir.mkdir(parents=True)

    lesson_path = plan_dir / "Einheiten" / "gruen-6 03-31 LZK.md"
    lesson_path.parent.mkdir(parents=True, exist_ok=True)
    lesson_path.write_text(
        "---\nStundentyp: LZK\nDauer: 2\nStundenthema: LZK 1\nKompetenzhorizont: \nInhaltsübersicht: \n---\n",
        encoding="utf-8",
    )

    table = _table(plan_dir / "Mathe Kurs.md", lesson_path.stem)
    usecase = MarkUnitAsUbUseCase(FileSystemLessonRepository(), FileSystemUbRepository())

    result = usecase.execute(
        workspace_root=workspace_root,
        table=table,
        row_index=0,
        ub_kinds=["Fach"],
        langentwurf=False,
        beobachtungsschwerpunkt="",
    )

    assert result.proceed is False
    assert result.error_message == "UB-Markierung ist nur für Unterricht erlaubt."


def test_mark_unit_as_ub_uses_lesson_file_title_for_ub_stem(tmp_path):
    workspace_root = tmp_path / "7thCloud"
    plan_dir = workspace_root / "7thVault" / "🏫 Pädagogik" / "10 Unterricht" / "Mathe Kurs"
    plan_dir.mkdir(parents=True)

    lesson_path = plan_dir / "Einheiten" / "gruen-6 02-06 Fach-Diagnose.md"
    _write_unterricht_lesson(lesson_path, title="Anderes Stundenthema")
    table = PlanTableData(
        markdown_path=plan_dir / "Mathe Kurs.md",
        headers=["Datum", "Stunden", "Inhalt"],
        rows=[["06-02-26", "2", f"[[{lesson_path.stem}]]"]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={"Kursfach": "Mathematik", "Lerngruppe": "[[gruen-6]]"},
    )

    usecase = MarkUnitAsUbUseCase(FileSystemLessonRepository(), FileSystemUbRepository())
    result = usecase.execute(
        workspace_root=workspace_root,
        table=table,
        row_index=0,
        ub_kinds=["Fach"],
        langentwurf=False,
        beobachtungsschwerpunkt="",
    )

    assert result.proceed is True
    assert isinstance(result.ub_path, Path)
    assert result.ub_path.stem == "UB 26-02-06 Fach-Diagnose"
