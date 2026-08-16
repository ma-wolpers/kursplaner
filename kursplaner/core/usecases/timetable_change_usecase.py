from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from kursplaner.core.domain.content_markers import is_ferien_marker
from kursplaner.core.domain.course_rhythm import WeekdayRhythm, active_weekdays, hours_for_date
from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.plan_table import parse_plan_row_date
from kursplaner.core.domain.planner import PlanRow, generate_rows
from kursplaner.core.ports.repositories import CalendarRepository

# ---------------------------------------------------------------------------
# Predicate wrappers for day_column classification
# ---------------------------------------------------------------------------


def column_is_ferien(day: DayColumn) -> bool:
    """Ferientag/Feiertag: Zeile traegt einen Ferien-Marker (siehe `content_markers.is_ferien_marker`)."""
    return day.is_ferien()


def column_is_manual_ausfall(day: DayColumn) -> bool:
    """Manuell markierter Ausfall: is_cancel True, aber keine Ferien.

    Distinct from Ferien. Use for week-comparison logic.
    """
    return not column_is_ferien(day) and day.is_cancel()


def column_is_stattfindend(day: DayColumn) -> bool:
    """Stattfindende Einheit: nicht storniert (weder Ferien noch manueller Ausfall)."""
    return not day.is_cancel()


def _new_row_is_ferien(row: PlanRow) -> bool:
    """PlanRow-Tupel aus generate_rows mit Ferien-Marker → Ferien-/Feiertagsslot."""
    return is_ferien_marker(row[1])


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

    `datum` ist `None` für einen datumslosen Slot: entsteht, wenn verdrängter
    Inhalt keine freie Lücke mehr findet und stattdessen angehängt wird (siehe
    `TimetableChangeDialog._place_displaced_content`). Datumslose Slots werden
    im Grid rot umrandet dargestellt (siehe `DayColumn.is_dateless`).
    """

    datum: date | None
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

    old_units: gefilterte DayColumn-Einträge im gewählten Datumsbereich
    draft_slots: vorgeschlagene neue Planung (editierbar im Dialog)
    """

    old_units: list[DayColumn]
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

    def compute(
        self,
        *,
        day_columns: list[DayColumn],
        date_from: date,
        date_to: date,
        new_rhythm: tuple[WeekdayRhythm, ...],
        calendar_dir: Path,
    ) -> TimetableChangeResult:
        """Berechnet old_units und draft_slots für den gewählten Bereich.

        Args:
            day_columns: Alle Planzeilen des geladenen Kursplans.
            date_from: Erster Tag des Änderungsbereichs.
            date_to: Letzter Tag des Änderungsbereichs.
            new_rhythm: Neuer Wochentags-Rhythmus (Startzeit + Stunden je Wochentag).
            calendar_dir: Kalenderordner für Ferien-/Feiertagsdaten.

        Returns:
            TimetableChangeResult mit old_units und vorgeschlagenen draft_slots.
        """
        old_units = self._filter_old_units(day_columns, date_from, date_to)
        weeks_with_manual_ausfall = self._collect_ausfall_weeks(old_units)

        years = {date_from.year, date_to.year}
        events, _blocks, _warnings = self._calendar_repo.load_calendar_data(calendar_dir, years)

        new_rows = generate_rows(date_from, date_to, active_weekdays(new_rhythm), events)
        draft_slots = self._build_draft_slots(old_units, new_rows, weeks_with_manual_ausfall, new_rhythm)

        return TimetableChangeResult(old_units=old_units, draft_slots=draft_slots)

    def _filter_old_units(
        self,
        day_columns: list[DayColumn],
        date_from: date,
        date_to: date,
    ) -> list[DayColumn]:
        """Filtert day_columns auf den gegebenen Datumsbereich."""
        result = []
        for day in day_columns:
            d = parse_plan_row_date(day.datum)
            if d is None:
                continue
            if date_from <= d <= date_to:
                result.append(day)
        return result

    def _collect_ausfall_weeks(self, old_units: list[DayColumn]) -> set[tuple[int, int]]:
        """Sammelt ISO-Kalenderwochen, in denen ein manueller Ausfall liegt.

        Gibt ein Set von (year, isoweek)-Tupeln zurück.
        """
        weeks: set[tuple[int, int]] = set()
        for day in old_units:
            if not column_is_manual_ausfall(day):
                continue
            d = parse_plan_row_date(day.datum)
            if d is None:
                continue
            iso = d.isocalendar()
            weeks.add((iso.year, iso.week))
        return weeks

    def _build_draft_slots(
        self,
        old_units: list[DayColumn],
        new_rows: list[PlanRow],
        weeks_with_manual_ausfall: set[tuple[int, int]],
        new_rhythm: tuple[WeekdayRhythm, ...],
    ) -> list[DraftSlot]:
        """Ordnet stattfindende alte Einheiten den neuen Slots zu.

        Ferien-Slots bekommen kein Content. Stattfindende neue Slots erhalten
        der Reihe nach Inhalt und Thema/Ausfall-Zellwert (u. a. das Oberthema
        noch nicht angelegter Einheiten, siehe `DraftSlot`) alter stattfindender
        Einheiten.
        """
        pending_contents = [(day.inhalt, day.thema_ausfall) for day in old_units if column_is_stattfindend(day)]

        slots: list[DraftSlot] = []
        content_index = 0

        for row in new_rows:
            row_date, note = row
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
                        stunden=hours_for_date(new_rhythm, row_date),
                        is_ferien=False,
                        is_user_ausfall=False,
                        ausfall_reason="",
                        content=content,
                        was_recovered_week=was_recovered,
                        oberthema_cell=oberthema_cell,
                    )
                )

        return slots
