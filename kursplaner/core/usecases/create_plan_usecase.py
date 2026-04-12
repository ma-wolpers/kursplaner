from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable, Literal

from kursplaner.core.domain.models import PlanResult
from kursplaner.core.domain.planner import create_plan_result, relevant_years
from kursplaner.core.ports.repositories import CalendarRepository, PlanRepository

ConfirmChange = Callable[[str, str], bool]


class CreatePlanUseCase:
    """Orchestriert Kalenderdaten-Laden, Planberechnung und Persistenz der Planzeilen."""

    def __init__(self, plan_repo: PlanRepository, calendar_repo: CalendarRepository):
        """Bindet Repository-Ports für Planpersistenz und Kalenderdatenzugriff."""
        self._plan_repo = plan_repo
        self._calendar_repo = calendar_repo

    def execute(
        self,
        target_markdown: Path,
        term: str | None,
        day_hours: dict[int, int],
        calendar_dir: Path,
        takeover_start: date | None = None,
        stop_at_next_break: bool = False,
        vacation_break_horizon: int = 1,
        write_mode: Literal["append", "replace"] = "append",
        confirm_change: ConfirmChange | None = None,
    ) -> PlanResult:
        """Erzeugt und speichert den Terminplan über Port-basierte I/O-Zugriffe."""
        if stop_at_next_break:
            if takeover_start is None:
                raise RuntimeError("Für den Übernahme-Modus wird ein Startdatum benötigt.")
            years = {takeover_start.year, takeover_start.year + 1, takeover_start.year + 2}
        else:
            if not term:
                raise RuntimeError("Für Halbjahres-Modus ist ein Halbjahr erforderlich.")
            years = relevant_years(term)

        events, blocks, warnings = self._calendar_repo.load_calendar_data(calendar_dir, years)
        rows, result = create_plan_result(
            term=term,
            day_hours=day_hours,
            events=events,
            blocks=blocks,
            warnings=warnings,
            takeover_start=takeover_start,
            stop_at_next_break=stop_at_next_break,
            vacation_break_horizon=vacation_break_horizon,
        )
        if write_mode == "replace":
            self._plan_repo.write_plan_rows(target_markdown, rows, confirm_change=confirm_change)
        else:
            self._plan_repo.append_plan_rows(target_markdown, rows, confirm_change=confirm_change)
        return result
