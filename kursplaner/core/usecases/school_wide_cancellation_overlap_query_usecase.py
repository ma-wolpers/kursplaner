from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

from kursplaner.core.domain.plan_table import parse_plan_row_date
from kursplaner.core.domain.school_wide_cancellation import SchoolWideCancellationEntry, course_key_for_path


class SchoolWideCancellationOverlapQueryUseCase:
    """Read-only Abfrage: welche Tage eines Kurses sind durch einen aktiven schulweiten Ausfall beansprucht.

    Schmale, einseitige Read-Abhaengigkeit fuer `TimetableChangeDialog`/
    `TimetableChangeUseCase`, damit diese vor einer Stundenplanaenderung warnen
    koennen, ohne an Apply/Revert/Flow gekoppelt zu sein.
    """

    def __init__(self, store_load: Callable[[], list[SchoolWideCancellationEntry]]) -> None:
        """Nimmt die Lade-Funktion des Stores entgegen (kein direkter Store-Import noetig)."""
        self._store_load = store_load

    def find_active_cancellation_dates(self, *, markdown_path: Path, date_from: date, date_to: date) -> list[date]:
        """Liefert alle Tage im Bereich, die ein aktiver Entry fuer diesen Kurs bereits beansprucht."""
        course_key = course_key_for_path(markdown_path)
        claimed: set[str] = set()
        for entry in self._store_load():
            ledger = entry.course_ledgers.get(course_key)
            if ledger is not None:
                claimed |= ledger.cancelled_dates()

        result: list[date] = []
        for raw in claimed:
            parsed = parse_plan_row_date(raw)
            if parsed is not None and date_from <= parsed <= date_to:
                result.append(parsed)
        return sorted(result)
