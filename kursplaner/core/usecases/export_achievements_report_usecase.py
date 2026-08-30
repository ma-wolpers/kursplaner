from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

from kursplaner.core.usecases.query_ub_achievements_usecase import (
    AchievementDomainGroup,
    UbAchievementsResult,
    group_achievements_by_domain,
)


@dataclass(frozen=True)
class AchievementsReportDocument:
    """Vollstaendige Renderdaten fuer den Achievement-Report-PDF-Export.

    `groups` ist bereits fertig gruppiert/sortiert (siehe `group_achievements_by_domain`)
    -- der Renderer berechnet weder Stufen noch Fortschritt noch Reihenfolge neu, sondern
    stellt nur dar, was hier ankommt.
    """

    title: str
    export_date_text: str
    groups: tuple[AchievementDomainGroup, ...]


@dataclass(frozen=True)
class ExportAchievementsReportResult:
    """Rueckgabe des Use Cases mit Zielpfad und Umfang des exportierten Stands."""

    output_path: Path
    group_count: int
    item_count: int


class AchievementsReportRendererPort(Protocol):
    """Port zum Rendern eines fachlich vorbereiteten Achievement-Reports als PDF."""

    def render(self, document: AchievementsReportDocument, output_path: Path) -> None:
        """Schreibt das PDF-Dokument an den angegebenen Zielpfad."""


class ExportAchievementsReportUseCase:
    """Exportiert den aktuell angezeigten UB-Achievement-Fortschritt als PDF-Report.

    Nimmt bewusst ein bereits berechnetes `UbAchievementsResult` entgegen (dasselbe,
    das auch die Ringe im Achievements-Tab zeichnet), statt Fortschritt oder Stufen
    selbst neu abzufragen -- der Export bildet damit deterministisch genau das ab,
    was die Ansicht zum Exportzeitpunkt zeigt.
    """

    def __init__(self, *, renderer: AchievementsReportRendererPort):
        self._renderer = renderer

    def execute(
        self,
        *,
        achievements: UbAchievementsResult,
        output_path: Path,
        export_date: date,
    ) -> ExportAchievementsReportResult:
        groups = group_achievements_by_domain(achievements.items)
        document = AchievementsReportDocument(
            title="UB-Achievement-Report",
            export_date_text=export_date.strftime("%d.%m.%Y"),
            groups=groups,
        )
        self._renderer.render(document, output_path)
        return ExportAchievementsReportResult(
            output_path=output_path,
            group_count=len(groups),
            item_count=sum(len(group.items) for group in groups),
        )
