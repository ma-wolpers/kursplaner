from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from kursplaner.core.domain.content_markers import build_ausfall_marker
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.ports.repositories import PlanRepository
from kursplaner.core.usecases.timetable_change_usecase import DraftSlot


@dataclass(frozen=True)
class ApplyTimetableChangeResult:
    """Ergebnis von ApplyTimetableChangeUseCase.execute().

    dropped_contents: Wiki-Links aus dem alten Plan, die in keinem neuen
    Slot auftauchen (werden zu potenziellen Schatteneinheiten).
    """

    dropped_contents: list[str]


class ApplyTimetableChangeUseCase:
    """Schreibt den neuen Stundenplan-Entwurf zurück in die Planungstabelle.

    Spliced den alten Datumsblock heraus und ersetzt ihn durch die
    Zeilen aus draft_slots. Alles außerhalb des Bereichs bleibt unverändert.
    """

    def __init__(self, plan_repo: PlanRepository) -> None:
        """Nimmt das Plan-Repository für Lade- und Speicheroperationen."""
        self._plan_repo = plan_repo

    @staticmethod
    def _parse_datum(value: str) -> date | None:
        """Parst DD-MM-YY robust; liefert None bei ungültigem Format."""
        try:
            return datetime.strptime(str(value).strip(), "%d-%m-%y").date()
        except ValueError:
            return None

    def _col_index(self, headers: list[str], name: str) -> int | None:
        """Liefert den Index einer Spaltenüberschrift (case-insensitiv); None falls fehlt."""
        lc = name.lower()
        for i, h in enumerate(headers):
            if str(h).strip().lower() == lc:
                return i
        return None

    def _build_row(
        self,
        slot: DraftSlot,
        *,
        n_cols: int,
        idx_datum: int,
        idx_stunden: int,
        idx_inhalt: int | None,
        idx_thema_ausfall: int | None,
    ) -> list[str]:
        """Baut eine Tabellenzeile aus einem DraftSlot.

        Respektiert die tatsächliche Spaltenanzahl und -reihenfolge der Tabelle.
        Im Normalfall (weder Ferien noch Ausfall) wird zusätzlich zu `slot.content`
        auch ein gesetztes `slot.oberthema_cell` in die Thema/Ausfall-Spalte
        geschrieben — siehe `DraftSlot`-Docstring für die vollständige
        Spalten-Zuordnung aller Felder.
        """
        row = [""] * n_cols

        datum_str = slot.datum.strftime("%d-%m-%y")
        row[idx_datum] = datum_str
        row[idx_stunden] = str(slot.stunden)

        if slot.is_ferien:
            if idx_thema_ausfall is not None:
                row[idx_thema_ausfall] = slot.ausfall_reason
            elif idx_inhalt is not None:
                row[idx_inhalt] = slot.ausfall_reason
        elif slot.is_user_ausfall:
            if idx_inhalt is not None:
                row[idx_inhalt] = slot.content
            marker = build_ausfall_marker(slot.ausfall_reason)
            if idx_thema_ausfall is not None:
                row[idx_thema_ausfall] = marker
            elif idx_inhalt is not None:
                row[idx_inhalt] = marker
        else:
            if idx_inhalt is not None:
                row[idx_inhalt] = slot.content
            if idx_thema_ausfall is not None and slot.oberthema_cell:
                row[idx_thema_ausfall] = slot.oberthema_cell

        return row

    def execute(
        self,
        table: PlanTableData,
        *,
        date_from: date,
        date_to: date,
        draft_slots: list[DraftSlot],
    ) -> ApplyTimetableChangeResult:
        """Spliced draft_slots in die Planungstabelle und speichert das Ergebnis.

        Args:
            table: Geladene Planungstabelle (wird in-place modifiziert und gespeichert).
            date_from: Erster Tag des Änderungsbereichs.
            date_to: Letzter Tag des Änderungsbereichs.
            draft_slots: Endgültiger Entwurf aus dem Dialog.

        Returns:
            ApplyTimetableChangeResult mit den aus dem Plan herausgefallenen Inhalten.
        """
        headers = table.headers
        n_cols = max(len(headers), 4)

        idx_datum = self._col_index(headers, "datum") or 0
        idx_stunden = self._col_index(headers, "stunden") or 1
        idx_inhalt = self._col_index(headers, "inhalt")
        idx_thema_ausfall = self._col_index(headers, "thema/ausfall")

        old_contents = self._collect_old_contents(table, date_from, date_to)
        new_contents = {s.content for s in draft_slots if s.content}
        dropped = [c for c in old_contents if c not in new_contents]

        new_rows = [
            self._build_row(
                slot,
                n_cols=n_cols,
                idx_datum=idx_datum,
                idx_stunden=idx_stunden,
                idx_inhalt=idx_inhalt,
                idx_thema_ausfall=idx_thema_ausfall,
            )
            for slot in draft_slots
        ]

        table.rows = self._splice_rows(table.rows, date_from, date_to, new_rows, idx_datum)
        self._plan_repo.save_plan_table(table)

        return ApplyTimetableChangeResult(dropped_contents=dropped)

    def _collect_old_contents(
        self, table: PlanTableData, date_from: date, date_to: date
    ) -> list[str]:
        """Sammelt Inhalt-Zellwerte der alten Planzeilen im Datumsbereich."""
        idx_inhalt = self._col_index(table.headers, "inhalt")
        if idx_inhalt is None:
            return []
        result = []
        for row in table.rows:
            d = self._parse_datum(row[0] if row else "")
            if d is None or not (date_from <= d <= date_to):
                continue
            val = str(row[idx_inhalt]) if idx_inhalt < len(row) else ""
            if val.strip():
                result.append(val.strip())
        return result

    def _splice_rows(
        self,
        rows: list[list[str]],
        date_from: date,
        date_to: date,
        new_rows: list[list[str]],
        idx_datum: int,
    ) -> list[list[str]]:
        """Ersetzt den Zeilenblock im Datumsbereich durch new_rows.

        Zeilen vor date_from und nach date_to bleiben unverändert.
        """
        before: list[list[str]] = []
        after: list[list[str]] = []
        found_range = False

        for row in rows:
            raw = row[idx_datum] if idx_datum < len(row) else ""
            d = self._parse_datum(raw)
            if d is None:
                if not found_range:
                    before.append(row)
                else:
                    after.append(row)
                continue

            if d < date_from:
                before.append(row)
            elif d <= date_to:
                found_range = True
            else:
                after.append(row)

        return before + new_rows + after
