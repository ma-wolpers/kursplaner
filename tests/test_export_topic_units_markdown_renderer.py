from __future__ import annotations

from datetime import date
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.export_topic_units_pdf_usecase import ExportTopicUnitsPdfUseCase
from kursplaner.core.usecases.sync_sequence_export_table_usecase import SyncSequenceExportTableUseCase
from kursplaner.infrastructure.export.topic_units_markdown_renderer import TopicUnitsMarkdownRenderer
from kursplaner.infrastructure.repositories.sequence_plan_repository import FileSystemSequencePlanRepository


def _table(tmp_path: Path) -> PlanTableData:
    plan_dir = tmp_path / "Unterricht" / "INF lila-5 25-2"
    plan_dir.mkdir(parents=True, exist_ok=True)
    return PlanTableData(
        markdown_path=plan_dir / "INF lila-5 25-2.md",
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
        "yaml": {
            "Stundentyp": kind,
            "Oberthema": obert,
            "Stundenthema": thema,
            "Stundenziel": ziel,
            "Kompetenzen": ["PK1"],
        },
        "link": Path(f"unit-{row_index}.md"),
        "is_cancel": False,
    }


def test_markdown_renderer_writes_topic_units_table(tmp_path: Path):
    output = tmp_path / "seq.md"
    sync = SyncSequenceExportTableUseCase(sequence_plan_repo=FileSystemSequencePlanRepository())
    usecase = ExportTopicUnitsPdfUseCase(renderer=TopicUnitsMarkdownRenderer(), sequence_export_sync=sync)

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
        table=_table(tmp_path),
        day_columns=day_columns,
        selected_row_index=0,
        output_path=output,
        export_date=date(2026, 4, 1),
    )

    text = output.read_text(encoding="utf-8")
    assert "| Datum | Stunden | Thema | Stundenziel | geförderte Prozesskompetenzen |" in text
    assert "| 01.09.2025 | 2 | Sortieren | Sortierverfahren vergleichen | PK1 |" in text
    assert "| 08.09.2025 | 1 | LZK Sortieren | Verfahren anwenden | PK1 |" in text
