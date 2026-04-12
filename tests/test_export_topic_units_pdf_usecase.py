from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.export_topic_units_pdf_usecase import ExportTopicUnitsPdfUseCase, TopicUnitsPdfDocument


class _RendererSpy:
    def __init__(self):
        self.calls: list[tuple[TopicUnitsPdfDocument, Path]] = []

    def render(self, document: TopicUnitsPdfDocument, output_path: Path) -> None:
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
    *, row_index: int, datum: str, stunden: str, kind: str, obert: str, thema: str, ziel: str, kompetenzen: list[str]
):
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
            "Kompetenzen": kompetenzen,
        },
        "link": Path(f"A:/7thCloud/unit-{row_index}.md"),
        "is_cancel": False,
    }


def test_export_builds_expected_title_and_rows_for_selected_oberthema():
    renderer = _RendererSpy()
    usecase = ExportTopicUnitsPdfUseCase(renderer=renderer)
    table = _table()

    day_columns = [
        _day(
            row_index=0,
            datum="01-09-25",
            stunden="2",
            kind="Unterricht",
            obert="Algorithmen",
            thema="Sortieren",
            ziel="Sortierverfahren vergleichen",
            kompetenzen=["PK1", "PK2"],
        ),
        _day(
            row_index=1,
            datum="08-09-25",
            stunden="1",
            kind="LZK",
            obert="Algorithmen",
            thema="LZK Sortieren",
            ziel="Verfahren anwenden",
            kompetenzen=["PK3"],
        ),
        _day(
            row_index=2,
            datum="15-09-25",
            stunden="2",
            kind="Unterricht",
            obert="Datenbanken",
            thema="SQL Einstieg",
            ziel="SELECT verstehen",
            kompetenzen=["PK4"],
        ),
    ]

    output_path = Path("A:/7thCloud/export.pdf")
    result = usecase.execute(
        table=table,
        day_columns=day_columns,
        selected_day_index=0,
        output_path=output_path,
        export_date=date(2026, 3, 31),
    )

    assert result.output_path == output_path
    assert result.row_count == 2
    assert result.title == "Informatik lila-5 2025/26 Hj. 2"
    assert len(renderer.calls) == 1

    document, rendered_path = renderer.calls[0]
    assert rendered_path == output_path
    assert document.title == "Informatik lila-5 2025/26 Hj. 2"
    assert document.subtitle == '"Algorithmen"'
    assert document.export_date_text == "31.03.2026"
    assert len(document.rows) == 2
    assert document.rows[0].datum == "01.09.2025"
    assert document.rows[0].prozesskompetenzen == "PK1; PK2"


def test_export_title_uses_requested_halfyear_format():
    renderer = _RendererSpy()
    usecase = ExportTopicUnitsPdfUseCase(renderer=renderer)

    day_columns = [
        _day(
            row_index=0,
            datum="01-09-25",
            stunden="1",
            kind="Unterricht",
            obert="Thema A",
            thema="A1",
            ziel="",
            kompetenzen=[],
        ),
        _day(
            row_index=1,
            datum="08-09-25",
            stunden="1",
            kind="Unterricht",
            obert="Thema B",
            thema="B1",
            ziel="",
            kompetenzen=[],
        ),
        _day(
            row_index=2,
            datum="15-09-25",
            stunden="1",
            kind="LZK",
            obert="Thema C",
            thema="C1",
            ziel="",
            kompetenzen=[],
        ),
    ]

    result = usecase.execute(
        table=_table(),
        day_columns=day_columns,
        selected_day_index=1,
        output_path=Path("A:/7thCloud/export-c.pdf"),
        export_date=date(2026, 3, 31),
    )

    assert result.title == "Informatik lila-5 2025/26 Hj. 2"


def test_export_rejects_selection_without_oberthema():
    renderer = _RendererSpy()
    usecase = ExportTopicUnitsPdfUseCase(renderer=renderer)

    day_columns = [
        _day(
            row_index=0,
            datum="01-09-25",
            stunden="2",
            kind="Unterricht",
            obert="",
            thema="Sortieren",
            ziel="",
            kompetenzen=[],
        )
    ]

    with pytest.raises(RuntimeError, match="kein Oberthema"):
        usecase.execute(
            table=_table(),
            day_columns=day_columns,
            selected_day_index=0,
            output_path=Path("A:/7thCloud/fail.pdf"),
            export_date=date(2026, 3, 31),
        )
