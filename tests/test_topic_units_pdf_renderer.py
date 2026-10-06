"""Tests für den Sequenzplan-PDF-Renderer (synthetische Daten)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kursplaner.core.usecases.export_topic_units_pdf_usecase import TopicUnitsPdfDocument
from tests.pdf_assertions import UNICODE_PROBE, assert_valid_pdf

pdf_renderer = pytest.importorskip("kursplaner.infrastructure.export.topic_units_pdf_renderer")
if not pdf_renderer.REPORTLAB_AVAILABLE:  # pragma: no cover - Umgebung ohne reportlab
    pytest.skip("reportlab fehlt", allow_module_level=True)

# „Datum und Stunde“ bricht in der schmalen Spalte um; „Kompetenzbezug“ steht
# zusammenhängend und markiert deshalb den (wiederholten) Tabellenkopf.
HEADER_MARKER = "Kompetenzbezug"


def _row(idx: int, goal: str = "Ziel") -> tuple:
    return (
        (f"Mo 0{idx % 9 + 1}.09.2026", "08:00 · 2 Std."),
        ("Modellieren", "Argumentieren"),
        (f"Thema {idx}",),
        (goal,),
        ("AB 1",),
    )


def _document(rows: tuple, *, focus: tuple[str, ...] = ("Modellieren",)) -> TopicUnitsPdfDocument:
    return TopicUnitsPdfDocument(
        document_title="Sequenzplan",
        export_date_text="06.10.2026",
        course_line="Mathematik 7a 2026/27 Hj. 1",
        sequence_topic="Lineare Funktionen",
        leitkompetenzen=focus,
        rows=rows,
    )


def test_header_meta_block_and_special_characters(tmp_path: Path):
    rows = (
        (
            ("Mo 07.09.2026",),
            ("A & B", "x < y > z"),
            (f"Thema {UNICODE_PROBE}",),
            ("Ziel ZZQ0END",),
            ("AB & Co <1>",),
        ),
    )
    output = tmp_path / "sequenz.pdf"

    pdf_renderer.TopicUnitsPdfRenderer().render(_document(rows, focus=("Modellieren", "Problemlösen")), output)

    assert_valid_pdf(
        output,
        pages=1,
        contains=[
            "Sequenzplan",
            "06.10.2026",
            "Mathematik 7a 2026/27 Hj. 1",
            "Thema der Sequenz:",
            "Lineare Funktionen",
            "Problemlösen",
            "A & B",
            "x < y > z",
            "AB & Co <1>",
            UNICODE_PROBE,
            "ZZQ0END",
        ],
    )


def test_empty_focus_and_material_render(tmp_path: Path):
    rows = ((("Mo 07.09.2026",), (), (), (), ()),)
    output = tmp_path / "leer.pdf"

    pdf_renderer.TopicUnitsPdfRenderer().render(_document(rows, focus=()), output)

    assert_valid_pdf(output, pages=1, contains=["(nicht gesetzt)", "Mo 07.09.2026"])


def test_short_rows_have_min_height_and_long_rows_grow():
    renderer = pdf_renderer.TopicUnitsPdfRenderer()
    long_goal = "Langes Stundenziel " * 40
    table = renderer._data_table(_document((_row(0), _row(1, goal=long_goal))), 700)

    table.wrap(700, 100_000)
    header_height, short_height, long_height = table._rowHeights

    assert short_height == pytest.approx(pdf_renderer.MIN_ROW_HEIGHT)
    assert long_height > pdf_renderer.MIN_ROW_HEIGHT
    assert header_height < pdf_renderer.MIN_ROW_HEIGHT  # Kopf ohne Mindesthöhe


def test_many_rows_span_pages_with_repeated_header(tmp_path: Path):
    rows = tuple(_row(idx, goal=f"Ziel ZZQ{idx:02d}END") for idx in range(20))
    output = tmp_path / "viele.pdf"

    pdf_renderer.TopicUnitsPdfRenderer().render(_document(rows), output)

    sentinels = [f"ZZQ{idx:02d}END" for idx in range(20)]
    assert_valid_pdf(output, min_pages=2, contains=sentinels, on_every_page=[HEADER_MARKER])


def test_single_extremely_long_row_is_split_across_pages(tmp_path: Path):
    """Eine einzelne Zeile länger als eine Seite: kein LayoutError, Kopf wiederholt, nichts abgeschnitten."""
    huge_goal = " ".join(f"Satz ZZQ{idx:03d}END mit Text" for idx in range(300))
    rows = (_row(0, goal=huge_goal), _row(1, goal="danach"))
    output = tmp_path / "riesig.pdf"

    pdf_renderer.TopicUnitsPdfRenderer().render(_document(rows), output)

    sentinels = [f"ZZQ{idx:03d}END" for idx in range(300)]
    assert_valid_pdf(output, min_pages=2, contains=[*sentinels, "danach"], on_every_page=[HEADER_MARKER])


def test_cell_markup_escapes_each_line_before_joining():
    assert pdf_renderer.cell_markup(("a & b", "<c>")) == "a &amp; b<br/>&lt;c&gt;"
    assert pdf_renderer.cell_markup(()) == ""


def test_date_column_never_wraps_the_date_and_rest_keeps_ratio():
    from reportlab.pdfbase.pdfmetrics import stringWidth

    renderer = pdf_renderer.TopicUnitsPdfRenderer()
    widths = renderer._column_widths(777.9)
    needed = stringWidth("Mo 00.00.0000", renderer._fonts.regular, renderer._cell_style.fontSize) + 10

    assert sum(widths) == pytest.approx(777.9)
    assert widths[0] >= max(777.9 * 0.10, needed)
    rest = widths[1:]
    assert [w / sum(rest) for w in rest] == pytest.approx([f / 0.90 for f in (0.27, 0.21, 0.25, 0.17)])
    # breite Satzbreite: Mindestanteil 10 % greift unverändert
    assert renderer._column_widths(5000)[0] == pytest.approx(500)
