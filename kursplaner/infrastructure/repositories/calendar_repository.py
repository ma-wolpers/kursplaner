from __future__ import annotations

from datetime import date
from pathlib import Path

from kursplaner.core.domain.planner import infer_term_from_ferien_blocks
from kursplaner.infrastructure.repositories.calendar_ics_repository import (
    find_ics_files_for_years,
    load_events_from_ics_files,
)


class FileSystemCalendarRepository:
    """Calendar repository - infer terms and load calendar events from ICS files."""

    def infer_term_from_date(self, start_date: date, calendar_dir: Path) -> str:
        """Leitet das Halbjahr aus Ferienblöcken rund um ein Datum ab."""
        years = {start_date.year - 1, start_date.year, start_date.year + 1}
        files, _ = find_ics_files_for_years(calendar_dir, years)
        _, blocks = load_events_from_ics_files(files)
        ferien_blocks = [item for item in blocks if "ferien" in item[0].lower()]
        return infer_term_from_ferien_blocks(start_date=start_date, ferien_blocks=ferien_blocks)

    def load_calendar_data(
        self, calendar_dir: Path, years: set[int]
    ) -> tuple[dict[date, str], list[tuple[str, date, date]], list[str]]:
        """Lädt Kalenderevents, Blocktermine und Warnungen für gegebene Jahre."""
        files, warnings = find_ics_files_for_years(calendar_dir, years)
        events, blocks = load_events_from_ics_files(files)
        return events, blocks, warnings
