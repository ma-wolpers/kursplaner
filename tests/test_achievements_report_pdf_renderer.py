"""Smoke-/Regressionstests für den Achievement-Report-PDF-Renderer (synthetische Daten)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kursplaner.core.usecases.export_achievements_report_usecase import AchievementsReportDocument
from kursplaner.core.usecases.query_ub_achievements_usecase import AchievementDomainGroup, AchievementProgress
from tests.pdf_assertions import UNICODE_PROBE, assert_valid_pdf

pdf_renderer = pytest.importorskip("kursplaner.infrastructure.export.achievements_report_pdf_renderer")
if not pdf_renderer.REPORTLAB_AVAILABLE:  # pragma: no cover - Umgebung ohne reportlab
    pytest.skip("reportlab fehlt", allow_module_level=True)


def _document(items_per_domain: int) -> AchievementsReportDocument:
    groups = tuple(
        AchievementDomainGroup(
            domain=f"{domain} {UNICODE_PROBE}",
            items=tuple(
                AchievementProgress(
                    key=f"{domain}-{idx}",
                    domain=domain,
                    category="c",
                    symbol="*",
                    title=f"Achievement {idx} mit längerem Titel " * 3 + f"ZZQ{domain}{idx}END",
                    current=idx % 3,
                    target=2,
                    tooltip="",
                    is_fulfilled=idx % 3 >= 2,
                )
                for idx in range(items_per_domain)
            ),
        )
        for domain in ("Mathe", "Info", "Paed")
    )
    return AchievementsReportDocument("UB-Achievements", "06.10.2026", groups)


def test_short_report_is_one_page_with_dejavu_and_unicode(tmp_path: Path):
    output = tmp_path / "achievements.pdf"

    pdf_renderer.AchievementsReportPdfRenderer().render(_document(1), output)

    assert_valid_pdf(output, pages=1, contains=[UNICODE_PROBE, "ZZQMathe0END", "offen"])


def test_long_report_spans_pages_without_losing_content(tmp_path: Path):
    output = tmp_path / "achievements.pdf"

    pdf_renderer.AchievementsReportPdfRenderer().render(_document(15), output)

    sentinels = [f"ZZQ{domain}{idx}END" for domain in ("Mathe", "Info", "Paed") for idx in range(15)]
    assert_valid_pdf(output, min_pages=2, contains=sentinels, on_every_page=["Achievement"])
