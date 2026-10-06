from __future__ import annotations

from datetime import date
from pathlib import Path

from kursplaner.core.domain.course_rhythm import WeekdayRhythm
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.export_topic_units_pdf_usecase import ExportTopicUnitsPdfUseCase
from kursplaner.core.usecases.sync_sequence_export_table_usecase import SyncSequenceExportTableUseCase
from kursplaner.infrastructure.export.topic_units_markdown_renderer import TopicUnitsMarkdownRenderer
from kursplaner.infrastructure.repositories.sequence_plan_repository import FileSystemSequencePlanRepository
from tests.day_column_factory import make_day_column

# 01-09-25 und 08-09-25 sind beide Montag (7 Tage auseinander) -> ein Segment-
# Wechsel ab 08-09-25 ist noetig, um den beiden Zeilen unterschiedliche
# Stundenzahlen zu geben (siehe day_column.stunden(), live aus dem Rhythmus).
_RHYTHM = (
    WeekdayRhythm(weekday=0, start_time="08:00", hours=2),
    WeekdayRhythm(weekday=0, start_time="08:00", hours=1, valid_from=date(2025, 9, 8)),
)


def _table(tmp_path: Path) -> PlanTableData:
    plan_dir = tmp_path / "Unterricht" / "INF lila-5 25-2"
    plan_dir.mkdir(parents=True, exist_ok=True)
    return PlanTableData(
        markdown_path=plan_dir / "INF lila-5 25-2.md",
        headers=["Datum", "Inhalt", "Thema/Ausfall"],
        rows=[],
        start_line=1,
        end_line=1,
        source_lines=[],
        had_trailing_newline=True,
        metadata={"Kursfach": "Informatik", "Lerngruppe": "[[lila-5]]", "Stufe": "5"},
    )


def _day(tmp_path: Path, *, row_index: int, datum: str, kind: str, obert: str, thema: str, ziel: str):
    lesson_dir = tmp_path / "Einheiten"
    lesson_dir.mkdir(exist_ok=True)
    link = lesson_dir / f"unit-{row_index}.md"
    link.write_text(f"---\nStundentyp: {kind}\n---\n", encoding="utf-8")
    return make_day_column(
        row_index=row_index,
        datum=datum,
        link=link,
        rhythm=_RHYTHM,
        yaml={
            "Stundentyp": kind,
            "Oberthema": obert,
            "Stundenthema": thema,
            "Stundenziel": ziel,
            "Kompetenzen": ["PK1"],
        },
    )


def test_markdown_renderer_writes_topic_units_table(tmp_path: Path):
    output = tmp_path / "seq.md"
    sync = SyncSequenceExportTableUseCase(sequence_plan_repo=FileSystemSequencePlanRepository())
    usecase = ExportTopicUnitsPdfUseCase(renderer=TopicUnitsMarkdownRenderer(), sequence_export_sync=sync)

    day_columns = [
        _day(
            tmp_path,
            row_index=0,
            datum="01-09-25",
            kind="Unterricht",
            obert="Algorithmen",
            thema="Sortieren",
            ziel="Sortierverfahren vergleichen",
        ),
        _day(
            tmp_path,
            row_index=1,
            datum="08-09-25",
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
    assert text.startswith("# Sequenzplan\n")
    assert "Exportdatum: 01.04.2026" in text
    assert "Kurs: Informatik lila-5 2025/26 Hj. 2" in text
    assert "**Thema der Sequenz:** Algorithmen" in text
    assert "**Vorrangig geförderte Kompetenz(en):** _(nicht gesetzt)_" in text
    assert "Sequenzziel" not in text
    assert "| Datum und Stunde | Kompetenzbezug | Stundenthema | Stundenziel | Material |" in text
    assert "| Mo 01.09.2025<br>08:00 · 2 Std. | PK1 | Sortieren | Sortierverfahren vergleichen |  |" in text
    assert "| Mo 08.09.2025<br>08:00 · 1 Std. | PK1 | LZK Sortieren | Verfahren anwenden |  |" in text


def test_meta_values_are_html_neutral_and_pipe_stays_literal(tmp_path: Path):
    from kursplaner.core.usecases.export_topic_units_pdf_usecase import TopicUnitsPdfDocument

    document = TopicUnitsPdfDocument(
        document_title="Sequenzplan",
        export_date_text="06.10.2026",
        course_line="Mathe <7a> & Co",
        sequence_topic="A | B <i>",
        leitkompetenzen=("[[K/Modellieren|Modellieren]]", "x & y"),
        rows=(),
    )
    output = tmp_path / "seq.md"

    TopicUnitsMarkdownRenderer().render(document, output)

    text = output.read_text(encoding="utf-8")
    assert "Kurs: Mathe &lt;7a&gt; &amp; Co" in text
    assert "**Thema der Sequenz:** A | B &lt;i&gt;" in text
    assert "**Vorrangig geförderte Kompetenz(en):** [[K/Modellieren|Modellieren]]<br>x &amp; y" in text
