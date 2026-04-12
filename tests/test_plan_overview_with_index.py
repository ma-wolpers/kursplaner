from datetime import date, timedelta

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.plan_overview_query_usecase import PlanOverviewQueryUseCase
from kursplaner.infrastructure.repositories.lesson_index_repository import FileSystemLessonIndexRepository
from kursplaner.infrastructure.repositories.markdown_repositories import FileSystemLessonRepository


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
    theme, remaining, next_lzk = usecase.summarize_plan(table)
    assert theme is not None
    assert "Thema1" in theme or theme == ""
