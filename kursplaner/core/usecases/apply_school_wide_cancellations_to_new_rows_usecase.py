from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Callable

from kursplaner.core.domain.content_markers import build_ausfall_marker, resolve_row_cancel_state, resolve_row_ferien_state
from kursplaner.core.domain.plan_table import parse_plan_row_date
from kursplaner.core.domain.school_wide_cancellation import (
    CourseApplicationLedger,
    RowLocation,
    SchoolWideCancellationEntry,
    UnitMove,
    claims_for_grade,
    course_key_for_path,
)
from kursplaner.core.ports.repositories import PlanRepository

StoreLoad = Callable[[], list[SchoolWideCancellationEntry]]
StoreSave = Callable[[list[SchoolWideCancellationEntry]], None]


def _col_index(headers: list[str], name: str) -> int | None:
    """Liefert den Index einer Spaltenueberschrift (case-insensitiv); None falls fehlt."""
    lc = name.lower()
    for i, h in enumerate(headers):
        if str(h).strip().lower() == lc:
            return i
    return None


def _position_in_date(rows: list[list[str]], idx_datum: int, target_index: int, raw_datum: str) -> int:
    """Zaehlt, wie viele fruehere Zeilen exakt dasselbe Datum tragen (0-basierte Position)."""
    position = 0
    for i in range(target_index):
        row = rows[i]
        if idx_datum < len(row) and str(row[idx_datum]).strip() == raw_datum:
            position += 1
    return position


class ApplySchoolWideCancellationsToNewRowsUseCase:
    """Markiert frisch erzeugte Planzeilen (neuer Kurs / Plan-Erweiterung) wie Ferien/Feiertage direkt als Ausfall.

    Laeuft NACH `CreatePlanUseCase` (ueber `NewLessonUseCase`/
    `ExtendPlanToNextVacationUseCase`) als schlanker Nachbearbeitungsschritt -
    `CreatePlanUseCase` selbst bleibt neutral und kennt keine schulweiten
    Ausfaelle. Ruehrt ausschliesslich Zeilen an, die weder Ferien-/Feiertag-
    noch Ausfall-markiert sind und deren `Inhalt`-Zelle leer ist (frisch
    erzeugte Zeilen sind das immer - die Pruefung ist eine zusaetzliche
    Absicherung gegen versehentliches Ueberschreiben vorhandenen Inhalts).
    """

    def __init__(self, plan_repo: PlanRepository, store_load: StoreLoad, store_save: StoreSave) -> None:
        """Nimmt Plan-Repository und Store-Zugriff (Laden/Speichern) entgegen."""
        self._plan_repo = plan_repo
        self._store_load = store_load
        self._store_save = store_save

    def execute(self, *, markdown_path: Path, grade_level: int, date_from: date, date_to: date) -> None:
        """Markiert im Bereich alle Tage, die ein aktiver Entry fuer `grade_level` beansprucht.

        Reihenfolge des Schreibens bewusst umgekehrt gegenueber Apply/Revert:
        zuerst die Entry-Liste (Store), danach die Plantabelle. Schlaegt der
        Plantabellen-Schreibvorgang fehl, nachdem der Store bereits den neuen
        `UnitMove` referenziert, ist das ueber den Diagnose-Usecase erkennbar
        (`resolve_move` findet die erwartete Markierung nicht -> `ERROR`). In
        der umgekehrten Reihenfolge waere ein solcher Teilfehler unsichtbar,
        weil kein Ledger-Eintrag auf die verwaiste Markierung verweisen wuerde.
        """
        entries = self._store_load()
        claims = claims_for_grade(entries, grade_level=grade_level, date_from=date_from, date_to=date_to)
        if not claims:
            return

        table = self._plan_repo.load_plan_table(markdown_path)
        headers = table.headers
        idx_datum = _col_index(headers, "datum")
        idx_inhalt = _col_index(headers, "inhalt")
        idx_thema = _col_index(headers, "thema/ausfall")
        if idx_datum is None or idx_inhalt is None or idx_thema is None:
            return

        moves_by_entry_id: dict[str, list[UnitMove]] = {}
        for row_index, row in enumerate(table.rows):
            raw_datum = row[idx_datum] if idx_datum < len(row) else ""
            row_date = parse_plan_row_date(raw_datum)
            if row_date is None or row_date not in claims:
                continue
            if resolve_row_ferien_state(headers, row) or resolve_row_cancel_state(headers, row):
                continue
            inhalt = str(row[idx_inhalt]) if idx_inhalt < len(row) else ""
            if inhalt.strip():
                continue

            entry = claims[row_date]
            row[idx_thema] = build_ausfall_marker(entry.reason)
            position = _position_in_date(table.rows, idx_datum, row_index, raw_datum)
            move = UnitMove(source=RowLocation(date=raw_datum, position_in_date=position), reference=None, target=None)
            moves_by_entry_id.setdefault(entry.entry_id, []).append(move)

        if not moves_by_entry_id:
            return

        course_key = course_key_for_path(markdown_path)
        updated_entries: list[SchoolWideCancellationEntry] = []
        for entry in entries:
            extra_moves = moves_by_entry_id.get(entry.entry_id)
            if not extra_moves:
                updated_entries.append(entry)
                continue
            existing_ledger = entry.course_ledgers.get(course_key, CourseApplicationLedger())
            merged_ledger = CourseApplicationLedger(moves=existing_ledger.moves + tuple(extra_moves))
            updated_course_ledgers = dict(entry.course_ledgers)
            updated_course_ledgers[course_key] = merged_ledger
            updated_entries.append(replace(entry, course_ledgers=updated_course_ledgers))

        self._store_save(updated_entries)
        self._plan_repo.save_plan_table(table)
