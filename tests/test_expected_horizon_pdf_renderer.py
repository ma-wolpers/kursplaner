"""Tests für Section-Überschriften im PDF-Kompetenzhorizont."""

from __future__ import annotations

from pathlib import Path

import pytest

from kursplaner.core.domain.expected_horizon import ExpectedHorizonLine, ExpectedHorizonSection, GoalKind
from kursplaner.core.domain.expected_horizon_pdf_layout import DEFAULT_FONT_SIZE, ExpectedHorizonPdfLayout
from kursplaner.core.usecases.export_expected_horizon_usecase import ExpectedHorizonDocument

pdf_renderer = pytest.importorskip("kursplaner.infrastructure.export.expected_horizon_pdf_renderer")
if not pdf_renderer.REPORTLAB_AVAILABLE:  # pragma: no cover - Umgebung ohne reportlab
    pytest.skip("reportlab fehlt", allow_module_level=True)


def _document(*topics: str) -> ExpectedHorizonDocument:
    sections = tuple(
        ExpectedHorizonSection(
            topic,
            (
                ExpectedHorizonLine("01.09.26", f"... {topic} 1", GoalKind.STUNDENZIEL),
                ExpectedHorizonLine("", f"... {topic} 2", GoalKind.TEILZIEL),
            ),
        )
        for topic in topics
    )
    return ExpectedHorizonDocument("Kompetenzhorizont", "Mathematik", "29.09.2026", sections)


def test_single_section_has_no_heading_rows():
    renderer = pdf_renderer.ExpectedHorizonPdfRenderer()
    document = _document("A")

    assert renderer._section_heading_rows(document) == []
    assert len(renderer._table_rows(document)) == 1 + 2


def test_multiple_sections_get_one_heading_row_each_and_render(tmp_path: Path):
    renderer = pdf_renderer.ExpectedHorizonPdfRenderer()
    document = _document("A", "B & C")
    output = tmp_path / "KH.pdf"

    assert renderer._section_heading_rows(document) == [1, 4]
    assert len(renderer._table_rows(document)) == 1 + 2 * (1 + 2)
    renderer.render(document, output)

    assert output.read_bytes().startswith(b"%PDF")


def test_default_layout_keeps_previous_font_size_and_five_columns():
    renderer = pdf_renderer.ExpectedHorizonPdfRenderer()

    assert renderer._cell_style.fontSize == DEFAULT_FONT_SIZE
    assert len(renderer._table_rows(_document("A"))[0]) == 5
    assert len(renderer._column_widths(500)) == 5


def test_task_column_and_font_size_are_applied(tmp_path: Path):
    renderer = pdf_renderer.ExpectedHorizonPdfRenderer()
    document = _document("A", "B")
    output = tmp_path / "KH.pdf"
    layout = ExpectedHorizonPdfLayout(with_task_column=True, font_size=14)

    renderer.render(document, output, layout=layout)

    assert renderer._cell_style.fontSize == 14
    rows = renderer._table_rows(document)
    assert all(len(row) == 6 for row in rows)
    widths = renderer._column_widths(500)
    assert widths[-1] == pytest.approx(100)  # breite, leere Aufgaben-Spalte
    assert widths[0] >= 3.9 * 14 + 12  # Datum bricht bei großer Schrift nicht um
    assert sum(widths) == pytest.approx(500)
    assert output.read_bytes().startswith(b"%PDF")


def test_font_size_is_clamped():
    assert ExpectedHorizonPdfLayout(font_size=2).font_size == 6
    assert ExpectedHorizonPdfLayout(font_size=40).font_size == 16
