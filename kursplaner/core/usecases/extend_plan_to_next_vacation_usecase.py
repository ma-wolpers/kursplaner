from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

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

    @staticmethod
    def _parse_plan_date(value: str):
        """Parst DD-MM-YY strikt in ein date-Objekt."""
        return datetime.strptime(str(value).strip(), "%d-%m-%y").date()

    @classmethod
    def _infer_day_hours(cls, rows: list[list[str]]) -> dict[int, int]:
        """Leitet den Unterrichtsrhythmus robust aus bestehenden Planzeilen ab."""
        day_hours: dict[int, int] = {}
        for row in rows:
            if len(row) < 2:
                continue
            date_obj = cls._parse_plan_date(row[0])
            hours_text = str(row[1]).strip()
            if not hours_text.isdigit():
                continue
            hours = int(hours_text)
            if hours <= 0:
                continue
            day_hours[date_obj.weekday()] = hours
        return dict(sorted(day_hours.items()))

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

        try:
            last_date = max(self._parse_plan_date(row[0]) for row in table.rows if row)
        except ValueError as exc:
            raise RuntimeError("Konnte kein gueltiges Enddatum aus dem Kursplan lesen.") from exc

        takeover_start = last_date + timedelta(days=1)
        day_hours = self._infer_day_hours(table.rows)
        if not day_hours:
            raise RuntimeError("Keine unterrichtbaren Wochentage im bestehenden Plan gefunden.")

        plan_result: PlanResult = self._create_plan_usecase.execute(
            target_markdown=markdown_path,
            term=None,
            day_hours=day_hours,
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
