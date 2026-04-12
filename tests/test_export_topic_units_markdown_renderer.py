from __future__ import annotations

from datetime import date
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.export_topic_units_pdf_usecase import ExportTopicUnitsPdfUseCase
from kursplaner.infrastructure.export.topic_units_markdown_renderer import TopicUnitsMarkdownRenderer


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


def _day(*, row_index: int, datum: str, stunden: str, kind: str, obert: str, thema: str, ziel: str):
    return {
        "row_index": row_index,
        "datum": datum,
        "stunden": stunden,
        "Stundentyp": kind,
        "yaml": {
            "Stundentyp": kind,
            "Oberthema": obert,
            "Stundenthema": thema,
            "Stundenziel": ziel,
            "Kompetenzen": ["PK1"],
        },
        "link": Path(f"A:/7thCloud/unit-{row_index}.md"),
        "is_cancel": False,
    }


def test_markdown_renderer_writes_topic_units_table(tmp_path: Path):
    output = tmp_path / "seq.md"
    usecase = ExportTopicUnitsPdfUseCase(renderer=TopicUnitsMarkdownRenderer())

    day_columns = [
        _day(
            row_index=0,
            datum="01-09-25",
            stunden="2",
            kind="Unterricht",
            obert="Algorithmen",
            thema="Sortieren",
            ziel="Sortierverfahren vergleichen",
        ),
        _day(
            row_index=1,
            datum="08-09-25",
            stunden="1",
            kind="LZK",
            obert="Algorithmen",
            thema="LZK Sortieren",
            ziel="Verfahren anwenden",
        ),
    ]

    usecase.execute(
        table=_table(),
        day_columns=day_columns,
        selected_day_index=0,
        output_path=output,
        export_date=date(2026, 4, 1),
    )

    text = output.read_text(encoding="utf-8")
    assert "| Datum | Stunden | Thema | Stundenziel | geförderte Prozesskompetenzen |" in text
    assert "| 01.09.2025 | 2 | Sortieren | Sortierverfahren vergleichen | PK1 |" in text
    assert "| 08.09.2025 | 1 | LZK Sortieren | Verfahren anwenden | PK1 |" in text
