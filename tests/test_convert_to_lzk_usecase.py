from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.convert_to_lzk_usecase import ConvertToLzkUseCase


def test_build_lzk_title_uses_subject_short_form():
    table = PlanTableData(
        markdown_path=Path("Inf lila-5 26-2.md"),
        headers=["datum", "stunden", "inhalt"],
        rows=[],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={"Kursfach": "Informatik", "Lerngruppe": "[[lila-5]]"},
    )

    title = ConvertToLzkUseCase.build_lzk_title(table, next_no=3)

    assert title == "LZK Inf lila-5 26-2 3"
