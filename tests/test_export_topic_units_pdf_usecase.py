from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.export_topic_units_pdf_usecase import ExportTopicUnitsPdfUseCase, TopicUnitsPdfDocument
from kursplaner.core.usecases.sync_sequence_export_table_usecase import SyncSequenceExportTableUseCase
from kursplaner.infrastructure.repositories.sequence_plan_repository import FileSystemSequencePlanRepository
from tests.day_column_factory import make_day_column


class _RendererSpy:
    def __init__(self):
        self.calls: list[tuple[TopicUnitsPdfDocument, Path]] = []

    def render(self, document: TopicUnitsPdfDocument, output_path: Path) -> None:
        self.calls.append((document, output_path))


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


def _day(
    tmp_path: Path,
    *,
    row_index: int,
    datum: str = "01-09-25",
    stunden: str = "2",
    kind: str,
    obert: str = "",
    thema: str = "",
    ziel: str = "",
    kompetenzen: list[str] | None = None,
):
    """Baut einen Tages-Eintrag in der jeweils realistischen Form.

    Ausfall-Tage haben in der echten Anwendung keine verlinkte Stundendatei,
    daher bleibt `yaml` leer und der Typ ergibt sich nur aus dem
    Thema/Ausfall-Textmarker (siehe `row_lesson_type()`), nicht aus
    `yaml.Stundentyp`. LZK/Hospitation brauchen dagegen einen echten,
    existierenden Link in einem verwalteten Einheitenverzeichnis, da
    `DayColumn.stundentyp()` nur darüber auflöst (siehe
    `is_valid_unterricht_file`).
    """
    yaml_data = {
        "Stundentyp": kind,
        "Oberthema": obert,
        "Stundenthema": thema,
        "Stundenziel": ziel,
        "Kompetenzen": kompetenzen or [],
    }
    if kind == "Ausfall":
        return make_day_column(row_index=row_index, datum=datum, thema_ausfall="X Ausfall")

    lesson_dir = tmp_path / "Einheiten"
    lesson_dir.mkdir(exist_ok=True)
    link = lesson_dir / f"unit-{row_index}.md"
    link.write_text(f"---\nStundentyp: {kind}\n---\n", encoding="utf-8")
    return make_day_column(row_index=row_index, datum=datum, link=link, yaml=yaml_data)


def _make_usecase() -> tuple[ExportTopicUnitsPdfUseCase, _RendererSpy]:
    renderer = _RendererSpy()
    sync = SyncSequenceExportTableUseCase(sequence_plan_repo=FileSystemSequencePlanRepository())
    return ExportTopicUnitsPdfUseCase(renderer=renderer, sequence_export_sync=sync), renderer


def test_export_builds_expected_title_and_rows_for_selected_run(tmp_path):
    usecase, renderer = _make_usecase()
    table = _table(tmp_path)

    day_columns = [
        _day(
            tmp_path,
            row_index=0,
            datum="01-09-25",
            kind="Unterricht",
            obert="Algorithmen",
            thema="Sortieren",
            ziel="Sortierverfahren vergleichen",
            kompetenzen=["PK1", "PK2"],
        ),
        _day(
            tmp_path,
            row_index=1,
            datum="08-09-25",
            kind="LZK",
            obert="Algorithmen",
            thema="LZK Sortieren",
            ziel="Verfahren anwenden",
            kompetenzen=["PK3"],
        ),
        _day(
            tmp_path,
            row_index=2,
            datum="15-09-25",
            kind="Unterricht",
            obert="Datenbanken",
            thema="SQL Einstieg",
            ziel="SELECT verstehen",
            kompetenzen=["PK4"],
        ),
    ]

    output_path = tmp_path / "export.pdf"
    result = usecase.execute(
        table=table,
        day_columns=day_columns,
        selected_row_index=0,
        output_path=output_path,
        export_date=date(2026, 3, 31),
    )

    assert result.output_path == output_path
    assert result.row_count == 2
    assert result.title == "Informatik lila-5 2025/26 Hj. 2"
    assert result.sequenzziel == ""
    assert result.leitkompetenz == ""
    assert result.sequence_path.exists()
    assert len(renderer.calls) == 1

    document, rendered_path = renderer.calls[0]
    assert rendered_path == output_path
    assert document.title == "Informatik lila-5 2025/26 Hj. 2"
    assert document.subtitle == '"Algorithmen"'
    assert document.export_date_text == "31.03.2026"
    assert len(document.rows) == 2
    assert document.rows[0].datum == "01.09.2025"
    assert document.rows[0].prozesskompetenzen == "PK1; PK2"


def test_export_title_uses_requested_halfyear_format(tmp_path):
    usecase, _renderer = _make_usecase()

    day_columns = [
        _day(tmp_path, row_index=0, datum="01-09-25", kind="Unterricht", obert="Thema A", thema="A1"),
        _day(tmp_path, row_index=1, datum="08-09-25", kind="Unterricht", obert="Thema B", thema="B1"),
        _day(tmp_path, row_index=2, datum="15-09-25", kind="LZK", obert="Thema C", thema="C1"),
    ]

    result = usecase.execute(
        table=_table(tmp_path),
        day_columns=day_columns,
        selected_row_index=1,
        output_path=tmp_path / "export-c.pdf",
        export_date=date(2026, 3, 31),
    )

    assert result.title == "Informatik lila-5 2025/26 Hj. 2"


def test_export_rejects_selection_without_oberthema(tmp_path):
    usecase, _renderer = _make_usecase()

    day_columns = [
        _day(tmp_path, row_index=0, datum="01-09-25", kind="Unterricht", obert="", thema="Sortieren"),
    ]

    with pytest.raises(RuntimeError, match="kein Oberthema"):
        usecase.execute(
            table=_table(tmp_path),
            day_columns=day_columns,
            selected_row_index=0,
            output_path=tmp_path / "fail.pdf",
            export_date=date(2026, 3, 31),
        )


def test_export_does_not_merge_non_adjacent_occurrences_of_same_oberthema(tmp_path):
    usecase, renderer = _make_usecase()

    day_columns = [
        _day(tmp_path, row_index=0, datum="01-09-25", kind="Unterricht", obert="Funktionen", thema="Einstieg"),
        _day(tmp_path, row_index=1, datum="08-09-25", kind="Unterricht", obert="Geometrie", thema="Dreiecke"),
        _day(tmp_path, row_index=2, datum="15-09-25", kind="Unterricht", obert="Funktionen", thema="Vertiefung"),
    ]

    result = usecase.execute(
        table=_table(tmp_path),
        day_columns=day_columns,
        selected_row_index=0,
        output_path=tmp_path / "export.pdf",
        export_date=date(2026, 3, 31),
    )

    assert result.row_count == 1
    document, _rendered_path = renderer.calls[0]
    assert document.rows[0].thema == "Einstieg"


def test_export_includes_hospitation_in_chain_but_not_as_table_row(tmp_path):
    usecase, renderer = _make_usecase()

    day_columns = [
        _day(tmp_path, row_index=0, datum="01-09-25", kind="Unterricht", obert="Optik", thema="Linsen"),
        _day(tmp_path, row_index=1, datum="08-09-25", kind="Hospitation", obert="Optik", thema="Hospitation"),
        _day(tmp_path, row_index=2, datum="15-09-25", kind="Unterricht", obert="Optik", thema="Brennweite"),
    ]

    result = usecase.execute(
        table=_table(tmp_path),
        day_columns=day_columns,
        selected_row_index=0,
        output_path=tmp_path / "export.pdf",
        export_date=date(2026, 3, 31),
    )

    assert result.row_count == 2
    document, _rendered_path = renderer.calls[0]
    assert [row.thema for row in document.rows] == ["Linsen", "Brennweite"]


def test_export_ausfall_does_not_break_the_chain(tmp_path):
    usecase, _renderer = _make_usecase()

    day_columns = [
        _day(tmp_path, row_index=0, datum="01-09-25", kind="Unterricht", obert="Chemie", thema="Saeuren"),
        _day(tmp_path, row_index=1, datum="08-09-25", kind="Ausfall"),
        _day(tmp_path, row_index=2, datum="15-09-25", kind="Unterricht", obert="Chemie", thema="Basen"),
    ]

    result = usecase.execute(
        table=_table(tmp_path),
        day_columns=day_columns,
        selected_row_index=0,
        output_path=tmp_path / "export.pdf",
        export_date=date(2026, 3, 31),
    )

    assert result.row_count == 2


def test_export_updates_sequence_file_export_table(tmp_path):
    usecase, _renderer = _make_usecase()
    table = _table(tmp_path)

    day_columns = [
        _day(tmp_path, row_index=0, datum="01-09-25", kind="Unterricht", obert="Mechanik", thema="Kraft"),
        _day(tmp_path, row_index=1, datum="08-09-25", kind="Unterricht", obert="Mechanik", thema="Impuls"),
    ]

    result = usecase.execute(
        table=table,
        day_columns=day_columns,
        selected_row_index=0,
        output_path=tmp_path / "export.pdf",
        export_date=date(2026, 3, 31),
    )

    sequence_text = result.sequence_path.read_text(encoding="utf-8")
    assert "| Datum | Std. | Thema | Stundenziel | Kompetenzen |" in sequence_text
    assert "Kraft" in sequence_text
    assert "Impuls" in sequence_text
