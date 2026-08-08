from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from kursplaner.core.domain.planner import PlanRow, generate_rows
from kursplaner.core.ports.repositories import CalendarRepository

# ---------------------------------------------------------------------------
# Predicate wrappers for day_column classification
# ---------------------------------------------------------------------------


def column_is_ferien(day: dict[str, object]) -> bool:
    """Ferientag/Feiertag: Stunden == 0 (kalender-generiert, kein Unterricht).

    Wraps the raw stunden comparison to avoid inline heuristics at call sites.
    """
    raw = str(day.get("stunden", "0") or "0").strip()
    try:
        return int(raw) == 0
    except ValueError:
        return True


def column_is_manual_ausfall(day: dict[str, object]) -> bool:
    """Manuell markierter Ausfall: Stunden > 0 und is_cancel True.

    Distinct from Ferien (which are stunden=0). Use for week-comparison logic.
    """
    return not column_is_ferien(day) and bool(day.get("is_cancel", False))


def column_is_stattfindend(day: dict[str, object]) -> bool:
    """Stattfindende Einheit: Stunden > 0 und nicht storniert."""
    return not column_is_ferien(day) and not bool(day.get("is_cancel", False))


def _new_row_is_ferien(row: PlanRow) -> bool:
    """PlanRow-Tupel aus generate_rows mit stunden=0 → Ferien-/Feiertagsslot."""
    return row[1] == 0


def _new_row_is_stattfindend(row: PlanRow) -> bool:
    """PlanRow-Tupel aus generate_rows, das einen regulären Unterrichtstag darstellt."""
    return not _new_row_is_ferien(row)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class DraftSlot:
    """Repräsentiert einen Slot im Entwurf des neuen Stundenplans.

    Lebt ausschließlich im Dialog; wird nach Übernehmen in Tabellenzeilen
    konvertiert und danach verworfen.

    Spalten-Zuordnung beim Zurückschreiben (siehe `ApplyTimetableChangeUseCase._build_row`):
    - `content` → Spalte "Inhalt", nur im Normalfall (weder Ferien noch Ausfall).
    - `ausfall_reason` → Spalte "Thema/Ausfall" bei Ferien/Ausfall, transformiert
      über `format_outage_note`/`build_ausfall_marker` (editierbarer Freitext).
    - `oberthema_cell` → Spalte "Thema/Ausfall" im Normalfall, unverändert aus
      der alten Einheit übernommen (roher Zellwert, kein Freitext).
    """

    datum: date
    stunden: int
    is_ferien: bool
    is_user_ausfall: bool
    ausfall_reason: str
    content: str
    was_recovered_week: bool
    oberthema_cell: str


@dataclass
class TimetableChangeResult:
    """Rückgabe von TimetableChangeUseCase.compute().

    old_units: gefilterte day_column-Dicts im gewählten Datumsbereich
    draft_slots: vorgeschlagene neue Planung (editierbar im Dialog)
    """

    old_units: list[dict[str, object]]
    draft_slots: list[DraftSlot]


# ---------------------------------------------------------------------------
# Use case
# ---------------------------------------------------------------------------


class TimetableChangeUseCase:
    """Berechnet den Entwurf für eine Stundenplanänderung.

    Verteilt bestehende Einheiten auf einen neuen Stundenrhythmus und
    kennzeichnet Wochen, die zuvor manuell als Ausfall markiert waren.
    """

    def __init__(self, calendar_repo: CalendarRepository) -> None:
        """Nimmt das Kalender-Repository für Ferien-/Feiertagsdaten entgegen."""
        self._calendar_repo = calendar_repo

    @staticmethod
    def _parse_datum(value: str) -> date:
        """Parst DD-MM-YY strikt in ein date-Objekt."""
        return datetime.strptime(str(value).strip(), "%d-%m-%y").date()

    def compute(
        self,
        *,
        day_columns: list[dict[str, object]],
        date_from: date,
        date_to: date,
        new_day_hours: dict[int, int],
        calendar_dir: Path,
    ) -> TimetableChangeResult:
        """Berechnet old_units und draft_slots für den gewählten Bereich.

        Args:
            day_columns: Alle Planzeilen des geladenen Kursplans.
            date_from: Erster Tag des Änderungsbereichs.
            date_to: Letzter Tag des Änderungsbereichs.
            new_day_hours: Neuer Stundenrhythmus als {weekday: hours} (Mo=0…Fr=4).
            calendar_dir: Kalenderordner für Ferien-/Feiertagsdaten.

        Returns:
            TimetableChangeResult mit old_units und vorgeschlagenen draft_slots.
        """
        old_units = self._filter_old_units(day_columns, date_from, date_to)
        weeks_with_manual_ausfall = self._collect_ausfall_weeks(old_units)

        years = {date_from.year, date_to.year}
        events, _blocks, _warnings = self._calendar_repo.load_calendar_data(calendar_dir, years)

        new_rows = generate_rows(date_from, date_to, new_day_hours, events)
        draft_slots = self._build_draft_slots(old_units, new_rows, weeks_with_manual_ausfall)

        return TimetableChangeResult(old_units=old_units, draft_slots=draft_slots)

    def _filter_old_units(
        self,
        day_columns: list[dict[str, object]],
        date_from: date,
        date_to: date,
    ) -> list[dict[str, object]]:
        """Filtert day_columns auf den gegebenen Datumsbereich."""
        result = []
        for day in day_columns:
            raw_datum = str(day.get("datum", "")).strip()
            if not raw_datum:
                continue
            try:
                d = self._parse_datum(raw_datum)
            except ValueError:
                continue
            if date_from <= d <= date_to:
                result.append(day)
        return result

    def _collect_ausfall_weeks(
        self, old_units: list[dict[str, object]]
    ) -> set[tuple[int, int]]:
        """Sammelt ISO-Kalenderwochen, in denen ein manueller Ausfall liegt.

        Gibt ein Set von (year, isoweek)-Tupeln zurück.
        """
        weeks: set[tuple[int, int]] = set()
        for day in old_units:
            if not column_is_manual_ausfall(day):
                continue
            raw = str(day.get("datum", "")).strip()
            try:
                d = self._parse_datum(raw)
            except ValueError:
                continue
            iso = d.isocalendar()
            weeks.add((iso.year, iso.week))
        return weeks

    def _build_draft_slots(
        self,
        old_units: list[dict[str, object]],
        new_rows: list[PlanRow],
        weeks_with_manual_ausfall: set[tuple[int, int]],
    ) -> list[DraftSlot]:
        """Ordnet stattfindende alte Einheiten den neuen Slots zu.

        Ferien-Slots bekommen kein Content. Stattfindende neue Slots erhalten
        der Reihe nach Inhalt und Thema/Ausfall-Zellwert (u. a. das Oberthema
        noch nicht angelegter Einheiten, siehe `DraftSlot`) alter stattfindender
        Einheiten.
        """
        pending_contents = [
            (str(day.get("inhalt", "")), str(day.get("thema_ausfall", "")))
            for day in old_units
            if column_is_stattfindend(day)
        ]

        slots: list[DraftSlot] = []
        content_index = 0

        for row in new_rows:
            row_date, stunden, note = row
            iso = row_date.isocalendar()

            if _new_row_is_ferien(row):
                slots.append(
                    DraftSlot(
                        datum=row_date,
                        stunden=0,
                        is_ferien=True,
                        is_user_ausfall=False,
                        ausfall_reason=note,
                        content="",
                        was_recovered_week=False,
                        oberthema_cell="",
                    )
                )
            else:
                content = ""
                oberthema_cell = ""
                if content_index < len(pending_contents):
                    content, oberthema_cell = pending_contents[content_index]
                    content_index += 1

                was_recovered = (iso.year, iso.week) in weeks_with_manual_ausfall
                slots.append(
                    DraftSlot(
                        datum=row_date,
                        stunden=stunden,
                        is_ferien=False,
                        is_user_ausfall=False,
                        ausfall_reason="",
                        content=content,
                        was_recovered_week=was_recovered,
                        oberthema_cell=oberthema_cell,
                    )
                )

        return slots
