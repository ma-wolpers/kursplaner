from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.export_expected_horizon_usecase import (
    ExpectedHorizonDocument,
    ExportExpectedHorizonUseCase,
)
from tests.day_column_factory import make_day_column


class _RendererSpy:
    def __init__(self):
        self.calls: list[tuple[ExpectedHorizonDocument, Path]] = []

    def render(self, document: ExpectedHorizonDocument, output_path: Path) -> None:
        self.calls.append((document, output_path))


def _table() -> PlanTableData:
    return PlanTableData(
        markdown_path=Path("A:/7thCloud/Unterricht/INF lila-5 25-2/INF lila-5 25-2.md"),
        headers=["Datum", "Stunden", "Inhalt"],
        rows=[],
        start_line=1,
        end_line=1,
        source_lines=[],
        had_trailing_newline=True,
        metadata={"Kursfach": "Informatik", "Lerngruppe": "[[lila-5]]", "Stufe": "5"},
    )


def _day(
    tmp_path,
    *,
    row_index: int,
    datum: str,
    kind: str,
    obert: str,
    ziel: str,
    teilziele: list[str],
    group_name: str = "lila-5",
):
    lesson_dir = tmp_path / "Einheiten"
    lesson_dir.mkdir(exist_ok=True)
    link = lesson_dir / f"unit-{row_index}.md"
    link.write_text(f"---\nStundentyp: {kind}\n---\n", encoding="utf-8")
    return make_day_column(
        row_index=row_index,
        datum=datum,
        link=link,
        group_name=group_name,
        yaml={
            "Stundentyp": kind,
            "Oberthema": obert,
            "Stundenziel": ziel,
            "Teilziele": teilziele,
        },
    )


def test_expected_horizon_exports_only_unterricht_and_flattens_goals(tmp_path):
    renderer = _RendererSpy()
    usecase = ExportExpectedHorizonUseCase(renderer=renderer)

    day_columns = [
        _day(
            tmp_path,
            row_index=0,
            datum="01-09-25",
            kind="Unterricht",
            obert="Algorithmen",
            ziel="Sortierverfahren vergleichen",
            teilziele=["Bubble Sort erklären", "Merge Sort einordnen"],
        ),
        _day(
            tmp_path,
            row_index=1,
            datum="08-09-25",
            kind="LZK",
            obert="Algorithmen",
            ziel="LZK Sortieren",
            teilziele=["Aufgaben lösen"],
        ),
        _day(
            tmp_path,
            row_index=2,
            datum="15-09-25",
            kind="Unterricht",
            obert="Datenbanken",
            ziel="SELECT verstehen",
            teilziele=[],
        ),
    ]

    result = usecase.execute(
        table=_table(),
        day_columns=day_columns,
        selected_day_index=1,
        output_path=Path("A:/7thCloud/Kompetenzhorizont.pdf"),
        export_date=date(2026, 4, 1),
    )

    assert result.row_count == 3
    assert result.title == "Kompetenzhorizont: Algorithmen"
    assert len(renderer.calls) == 1

    document, _ = renderer.calls[0]
    assert document.subtitle == "Informatik lila-5 2025/26 Hj. 2"
    assert [row.datum for row in document.rows] == ["01.09.25", "", ""]
    assert [row.ich_kann for row in document.rows] == [
        "... Sortierverfahren vergleichen",
        "... Bubble Sort erklären",
        "... Merge Sort einordnen",
    ]
    assert [row.is_main_goal for row in document.rows] == [True, False, False]


def test_expected_horizon_matches_wiki_linked_and_plain_text_oberthema(tmp_path):
    """Ein bewusst als Wiki-Link gespeichertes Oberthema (Obsidian-Verlinkung) darf beim
    Export nicht faelschlich als eigenes Thema behandelt werden."""
    renderer = _RendererSpy()
    usecase = ExportExpectedHorizonUseCase(renderer=renderer)

    day_columns = [
        _day(
            tmp_path,
            row_index=0,
            datum="01-09-25",
            kind="Unterricht",
            obert="[[lila-5 Algorithmen]]",
            ziel="Sortierverfahren vergleichen",
            teilziele=[],
        ),
        _day(
            tmp_path,
            row_index=1,
            datum="08-09-25",
            kind="Unterricht",
            obert="Algorithmen",
            ziel="LZK Sortieren",
            teilziele=[],
        ),
    ]

    result = usecase.execute(
        table=_table(),
        day_columns=day_columns,
        selected_day_index=1,
        output_path=Path("A:/7thCloud/Kompetenzhorizont.pdf"),
        export_date=date(2026, 4, 1),
    )

    assert result.row_count == 2
    assert result.title == "Kompetenzhorizont: Algorithmen"


def test_expected_horizon_rejects_selection_without_oberthema(tmp_path):
    renderer = _RendererSpy()
    usecase = ExportExpectedHorizonUseCase(renderer=renderer)

    day_columns = [
        _day(
            tmp_path,
            row_index=0,
            datum="01-09-25",
            kind="Unterricht",
            obert="",
            ziel="Sortieren",
            teilziele=[],
        )
    ]

    with pytest.raises(RuntimeError, match="kein Oberthema"):
        usecase.execute(
            table=_table(),
            day_columns=day_columns,
            selected_day_index=0,
            output_path=Path("A:/7thCloud/fail.pdf"),
            export_date=date(2026, 4, 1),
        )


def test_expected_horizon_filters_competency_prefixes_from_goals(tmp_path):
    renderer = _RendererSpy()
    usecase = ExportExpectedHorizonUseCase(renderer=renderer)

    day_columns = [
        _day(
            tmp_path,
            row_index=0,
            datum="01-09-25",
            kind="Unterricht",
            obert="Algorithmen",
            ziel="I 1.1 Sortierverfahren vergleichen",
            teilziele=["I 2.3: Bubble Sort erklären", "M 3.2 - Merge Sort einordnen"],
        )
    ]

    usecase.execute(
        table=_table(),
        day_columns=day_columns,
        selected_day_index=0,
        output_path=Path("A:/7thCloud/Kompetenzhorizont.pdf"),
        export_date=date(2026, 4, 1),
    )

    document, _ = renderer.calls[0]
    assert [row.ich_kann for row in document.rows] == [
        "... Sortierverfahren vergleichen",
        "... Bubble Sort erklären",
        "... Merge Sort einordnen",
    ]
