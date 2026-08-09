from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from kursplaner.core.domain.course_lifecycle import last_plan_date
from kursplaner.core.domain.course_rhythm import RHYTHM_YAML_KEY, current_segment, parse_rhythm
from kursplaner.core.domain.models import PlanResult
from kursplaner.core.ports.repositories import PlanRepository
from kursplaner.core.usecases.create_plan_usecase import ConfirmChange, CreatePlanUseCase


@dataclass(frozen=True)
class ExtendPlanToNextVacationResult:
    """Ergebnisobjekt fuer die Planerweiterung bis zur naechsten Ferienphase."""

    rows_added: int
    range_start: date
    range_end: date
    warnings: list[str]


class ExtendPlanToNextVacationUseCase:
    """Erweitert eine bestehende Planung ab Kursende bis zur naechsten Ferienphase."""

    def __init__(
        self,
        plan_repo: PlanRepository,
        create_plan_usecase: CreatePlanUseCase,
    ):
        """Bindet Port-basierte Abhaengigkeiten fuer Read/Write und Kalenderlogik."""
        self._plan_repo = plan_repo
        self._create_plan_usecase = create_plan_usecase

    def execute(
        self,
        *,
        markdown_path: Path,
        calendar_dir: Path,
        confirm_change: ConfirmChange | None = None,
    ) -> ExtendPlanToNextVacationResult:
        """Fuehrt die Planerweiterung als klaren Use-Case-Entry aus."""
        table = self._plan_repo.load_plan_table(markdown_path)
        if not table.rows:
            raise RuntimeError("Der Kursplan enthaelt keine Terminzeilen.")

        last_date = last_plan_date(table)
        if last_date is None:
            raise RuntimeError("Konnte kein gueltiges Enddatum aus dem Kursplan lesen.")

        takeover_start = last_date + timedelta(days=1)
        rhythm = parse_rhythm(table.metadata.get(RHYTHM_YAML_KEY, []))
        active_rhythm = current_segment(rhythm, takeover_start)
        if not active_rhythm:
            raise RuntimeError("Keine unterrichtbaren Wochentage im bestehenden Plan (Rhythmus) gefunden.")

        plan_result: PlanResult = self._create_plan_usecase.execute(
            target_markdown=markdown_path,
            term=None,
            rhythm=active_rhythm,
            calendar_dir=calendar_dir,
            takeover_start=takeover_start,
            stop_at_next_break=True,
            vacation_break_horizon=1,
            write_mode="append",
            confirm_change=confirm_change,
        )

        return ExtendPlanToNextVacationResult(
            rows_added=plan_result.rows_count,
            range_start=plan_result.range_start,
            range_end=plan_result.range_end,
            warnings=plan_result.warnings,
        )
