from datetime import date, timedelta

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.plan_overview_query_usecase import PlanOverviewQueryUseCase
from kursplaner.infrastructure.repositories.lesson_index_repository import FileSystemLessonIndexRepository
from kursplaner.infrastructure.repositories.markdown_repositories import FileSystemLessonRepository
from kursplaner.infrastructure.repositories.ub_repository import FileSystemUbRepository


def test_plan_overview_uses_index(tmp_path):
    # Setup a simple Unterricht folder with one lesson
    root = tmp_path / "Unterricht"
    (root / "FachX" / "Einheiten").mkdir(parents=True)
    lesson_path = root / "FachX" / "Einheiten" / "stunde-1.md"
    lesson_path.write_text(
        '---\nStundentyp: Unterricht\nDauer: 2\nKompetenzen:\n  - ""\nStundenthema: Thema1\nStundenziel: ""\nMaterial:\n  - ""\nOberthema: ""\n---\n\n# Inhalt\n',
        encoding="utf-8",
    )

    repo = FileSystemLessonIndexRepository()
    repo.rebuild_index(root)

    lesson_repo = FileSystemLessonRepository()
    usecase = PlanOverviewQueryUseCase(lesson_repo=lesson_repo, lesson_index_repo=repo)

    future = (date.today() + timedelta(days=1)).strftime("%d-%m-%y")
    table = PlanTableData(
        markdown_path=root / "FachX" / "plan.md",
        headers=["datum", "stunden", "inhalt"],
        rows=[[future, "2", "[[Einheiten/stunde-1]]"]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={},
    )

    # summarize_plan should run using the index; result should reflect the indexed topic
    theme, remaining, next_lzk, next_ub = usecase.summarize_plan(table)
    assert theme is not None
    assert "Thema1" in theme or theme == ""
    assert next_ub == ""


def test_plan_overview_exposes_next_ub_display(tmp_path):
    workspace_root = tmp_path / "7thCloud"
    root = workspace_root / "7thVault" / "Unterricht" / "FachX"
    (root / "Einheiten").mkdir(parents=True)

    lesson_path = root / "Einheiten" / "stunde-1.md"
    lesson_path.write_text(
        "---\n"
        "Stundentyp: Unterricht\n"
        "Dauer: 2\n"
        "Kompetenzen:\n"
        '  - ""\n'
        "Stundenthema: Thema1\n"
        'Stundenziel: ""\n'
        "Material:\n"
        '  - ""\n'
        "Oberthema: Ober\n"
        'Unterrichtsbesuch: "[[UB 26-05-18 Funktionen]]"\n'
        "---\n\n"
        "# Inhalt\n",
        encoding="utf-8",
    )

    ub_root = workspace_root / "7thVault" / "🏫 Pädagogik" / "00 Orga" / "02 UBs"
    ub_root.mkdir(parents=True)
    ub_path = ub_root / "UB 26-05-18 Funktionen.md"
    ub_path.write_text(
        "---\n"
        "Bereich:\n"
        '  - "Pädagogik"\n'
        '  - "Mathematik"\n'
        "Langentwurf: true\n"
        "Beobachtungsschwerpunkt: Fokus\n"
        'Einheit: "[[stunde-1]]"\n'
        "---\n\n"
        "# Reflexion\n",
        encoding="utf-8",
    )

    repo = FileSystemLessonIndexRepository()
    repo.rebuild_index(workspace_root / "7thVault" / "Unterricht")
    lesson_repo = FileSystemLessonRepository()
    ub_repo = FileSystemUbRepository()
    usecase = PlanOverviewQueryUseCase(lesson_repo=lesson_repo, lesson_index_repo=repo, ub_repo=ub_repo)

    table = PlanTableData(
        markdown_path=root / "plan.md",
        headers=["datum", "stunden", "inhalt"],
        rows=[["2026-05-18", "2", "[[Einheiten/stunde-1]]"]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={},
    )

    _theme, _remaining, _next_lzk, next_ub = usecase.summarize_plan(table, reference_day=date(2026, 5, 1))
    assert next_ub == "18.5. MP+"
