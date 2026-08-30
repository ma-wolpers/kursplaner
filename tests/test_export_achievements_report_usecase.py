from __future__ import annotations

from datetime import date
from pathlib import Path

from kursplaner.core.usecases.export_achievements_report_usecase import (
    AchievementsReportDocument,
    ExportAchievementsReportUseCase,
)
from kursplaner.core.usecases.query_ub_achievements_usecase import AchievementProgress, UbAchievementsResult


class _RendererSpy:
    def __init__(self):
        self.calls: list[tuple[AchievementsReportDocument, Path]] = []

    def render(self, document: AchievementsReportDocument, output_path: Path) -> None:
        self.calls.append((document, output_path))


def _item(*, key: str, domain: str, current: int, target: int) -> AchievementProgress:
    return AchievementProgress(
        key=key,
        domain=domain,
        category="half",
        symbol="?",
        title=key,
        current=current,
        target=target,
        tooltip="",
        is_fulfilled=current >= target,
    )


def test_export_achievements_report_groups_items_and_delegates_to_renderer(tmp_path):
    achievements = UbAchievementsResult(
        items=[
            _item(key="mat_low", domain="Mathematik", current=1, target=4),
            _item(key="paed_half", domain="Pädagogik", current=3, target=5),
            _item(key="mat_high", domain="Mathematik", current=4, target=4),
        ]
    )
    renderer = _RendererSpy()
    usecase = ExportAchievementsReportUseCase(renderer=renderer)
    output_path = tmp_path / "Achievement-Report.pdf"

    result = usecase.execute(achievements=achievements, output_path=output_path, export_date=date(2026, 8, 30))

    assert result.output_path == output_path
    assert result.group_count == 2
    assert result.item_count == 3

    assert len(renderer.calls) == 1
    document, rendered_path = renderer.calls[0]
    assert rendered_path == output_path
    assert document.export_date_text == "30.08.2026"
    assert [group.domain for group in document.groups] == ["Pädagogik", "Mathematik"]
    # Innerhalb "Mathematik" nach Erfuellungsgrad absteigend, wie von
    # `group_achievements_by_domain` vorgegeben -- der Renderer bekommt das
    # bereits fertig sortiert und sortiert selbst nichts nach.
    mathematik_group = next(group for group in document.groups if group.domain == "Mathematik")
    assert [item.key for item in mathematik_group.items] == ["mat_high", "mat_low"]
