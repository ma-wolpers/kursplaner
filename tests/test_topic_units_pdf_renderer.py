"""Smoke-Tests für den Sequenzplan-PDF-Renderer (synthetische Daten)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kursplaner.core.domain.topic_sequence_runs import TopicUnitExportRow
from kursplaner.core.usecases.export_topic_units_pdf_usecase import TopicUnitsPdfDocument
from tests.pdf_assertions import UNICODE_PROBE, assert_valid_pdf

pdf_renderer = pytest.importorskip("kursplaner.infrastructure.export.topic_units_pdf_renderer")
if not pdf_renderer.REPORTLAB_AVAILABLE:  # pragma: no cover - Umgebung ohne reportlab
    pytest.skip("reportlab fehlt", allow_module_level=True)


def test_renders_with_bundled_font_and_unicode(tmp_path: Path):
    rows = tuple(
        TopicUnitExportRow(
            datum=f"{idx + 1:02d}.09.2026",
            stunden="2",
            thema=f"Thema {idx} {UNICODE_PROBE}",
            stundenziel=f"Ziel {idx} ZZQ{idx}END",
            prozesskompetenzen="Modellieren",
        )
        for idx in range(3)
    )
    document = TopicUnitsPdfDocument(
        title="Mathe 7a 2026/27 Hj. 1",
        subtitle='"Funktionen"',
        export_date_text="06.10.2026",
        rows=rows,
        sequenzziel="",
        leitkompetenzen=("Modellieren",),
    )
    output = tmp_path / "sequenz.pdf"

    pdf_renderer.TopicUnitsPdfRenderer().render(document, output)

    assert_valid_pdf(output, pages=1, contains=[UNICODE_PROBE, "ZZQ0END", "ZZQ2END"])
