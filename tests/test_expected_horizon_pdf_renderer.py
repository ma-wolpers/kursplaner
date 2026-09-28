"""Tests für Section-Überschriften im PDF-Kompetenzhorizont."""

from __future__ import annotations

from pathlib import Path

import pytest

from kursplaner.core.domain.expected_horizon import ExpectedHorizonLine, ExpectedHorizonSection, GoalKind
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
