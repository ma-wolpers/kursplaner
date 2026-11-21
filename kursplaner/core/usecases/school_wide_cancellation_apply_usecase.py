from __future__ import annotations

from datetime import date
from pathlib import Path

from kursplaner.core.domain.content_markers import build_ausfall_marker
from kursplaner.core.domain.plan_row_payload import PayloadColumns, RowPayload
from kursplaner.core.domain.plan_row_placement import (
    find_stattfindend_rows_in_range,
    plan_gap_placement,
    strip_empty_dateless_rows,
)
from kursplaner.core.domain.plan_table import (
    COLUMN_DATUM,
    COLUMN_INHALT,
    COLUMN_THEMA_AUSFALL,
    PlanTableData,
    header_index,
    parse_plan_row_date,
)
from kursplaner.core.domain.row_identity import extract_row_reference
from kursplaner.core.domain.school_wide_cancellation import (
    CourseApplicationLedger,
    RowLocation,
    UnitMove,
    UnitReference,
)
from kursplaner.core.ports.repositories import PlanRepository


def _position_in_date(rows: list[list[str]], idx_datum: int, target_index: int, raw_datum: str) -> int:
    """Zaehlt, wie viele fruehere Zeilen exakt dasselbe Datum tragen (0-basierte Position)."""
    position = 0
    for i in range(target_index):
        row = rows[i]
        if idx_datum < len(row) and str(row[idx_datum]).strip() == raw_datum:
            position += 1
    return position


class SchoolWideCancellationApplyUseCase:
    """Wendet einen schulweiten Ausfall auf einen einzelnen Kursplan an.

    Single-course, keine Orchestrierung ueber mehrere Kurse und keine
    Fehler-/Konflikt-Entscheidungslogik - das ist Aufgabe des
    `BulkCancellationCoordinator`. Markiert betroffene Zeilen als Ausfall,
    verschiebt vorhandenen Inhalt in die naechste freie Luecke oder haengt
    bei Bedarf eine neue datumslose Zeile an, und baut daraus das minimale
    Bewegungs-Ledger (siehe `core.domain.school_wide_cancellation`).
    """

    def __init__(self, plan_repo: PlanRepository) -> None:
        """Nimmt das Plan-Repository fuer Lade- und Speicheroperationen entgegen."""
        self._plan_repo = plan_repo

    def execute(
        self,
        *,
        markdown_path: Path,
        date_from: date,
        date_to: date,
        reason: str,
    ) -> CourseApplicationLedger:
        """Laedt den Kursplan, wendet den Ausfall an und speichert bei Aenderungen.

        Returns:
            Das Bewegungs-Ledger dieses Kurses (leer, wenn im Zeitraum keine
            stattfindende Einheit lag).
        """
        table = self._plan_repo.load_plan_table(markdown_path)
        ledger = self._apply_to_table(table, date_from=date_from, date_to=date_to, reason=reason)
        if ledger.moves:
            self._plan_repo.save_plan_table(table)
        return ledger

    def _apply_to_table(
        self,
        table: PlanTableData,
        *,
        date_from: date,
        date_to: date,
        reason: str,
    ) -> CourseApplicationLedger:
        headers = table.headers
        idx_datum = header_index(headers, COLUMN_DATUM)
        idx_inhalt = header_index(headers, COLUMN_INHALT)
        idx_thema = header_index(headers, COLUMN_THEMA_AUSFALL)
        if idx_datum is None or idx_inhalt is None or idx_thema is None:
            return CourseApplicationLedger(moves=())

        original_rows = [list(row) for row in table.rows]
        cancel_row_indices = find_stattfindend_rows_in_range(headers, original_rows, date_from, date_to)
        if not cancel_row_indices:
            return CourseApplicationLedger(moves=())
        cancel_row_indices_set = set(cancel_row_indices)

        moves: list[UnitMove] = []
        pending: list[tuple[RowLocation, UnitReference, RowPayload]] = []
        columns = PayloadColumns(idx_inhalt, idx_thema)

        marker = build_ausfall_marker(reason)
        for row_index in cancel_row_indices:
            row = original_rows[row_index]
            raw_datum = row[idx_datum] if idx_datum < len(row) else ""
            source_loc = RowLocation(
                date=raw_datum, position_in_date=_position_in_date(original_rows, idx_datum, row_index, raw_datum)
            )
            payload = columns.read(row)

            target_row = table.rows[row_index]
            columns.clear(target_row)
            if idx_thema < len(target_row):
                target_row[idx_thema] = marker  # Termin-Marker, keine Nutzlast

            if not payload.is_empty:
                reference = extract_row_reference(headers, row)
                pending.append((source_loc, reference, payload))
            else:
                moves.append(UnitMove(source=source_loc, reference=None, target=None))

        if pending:
            self._place_displaced_content(
                table,
                original_rows=original_rows,
                cancel_row_indices=cancel_row_indices_set,
                idx_datum=idx_datum,
                idx_inhalt=idx_inhalt,
                idx_thema=idx_thema,
                pending=pending,
                moves=moves,
            )

        table.rows = strip_empty_dateless_rows(headers, table.rows)
        return CourseApplicationLedger(moves=tuple(moves))

    def _place_displaced_content(
        self,
        table: PlanTableData,
        *,
        original_rows: list[list[str]],
        cancel_row_indices: set[int],
        idx_datum: int,
        idx_inhalt: int,
        idx_thema: int,
        pending: list[tuple[RowLocation, UnitReference, RowPayload]],
        moves: list[UnitMove],
    ) -> None:
        """Platziert verdraengten Inhalt in freien Luecken nach dem Ausfall-Block, sonst angehaengt.

        Link und Thema-Zelle wandern gemeinsam (`plan_row_payload`).
        """
        columns = PayloadColumns(idx_inhalt, idx_thema)

        def is_available_gap(index: int) -> bool:
            if index in cancel_row_indices or index >= len(original_rows):
                return False
            row = original_rows[index]
            raw = row[idx_datum] if idx_datum < len(row) else ""
            if parse_plan_row_date(raw) is None:
                return False
            return not columns.has_slot_marker(row) and columns.read(row).is_empty

        last_cancel_index = max(cancel_row_indices)
        placement = plan_gap_placement(
            is_available_gap=is_available_gap,
            slot_count=len(original_rows),
            start_after_index=last_cancel_index + 1,
            needed_count=len(pending),
        )
        gap_iter = iter(placement.gap_indices)

        for source_loc, reference, payload in pending:
            gap_index = next(gap_iter, None)
            if gap_index is not None:
                columns.write(table.rows[gap_index], payload)
                gap_raw_datum = original_rows[gap_index][idx_datum] if idx_datum < len(original_rows[gap_index]) else ""
                target_loc = RowLocation(
                    date=gap_raw_datum,
                    position_in_date=_position_in_date(original_rows, idx_datum, gap_index, gap_raw_datum),
                )
            else:
                new_row = [""] * len(table.headers)
                columns.write(new_row, payload)
                table.rows.append(new_row)
                target_loc = RowLocation(date=None, position_in_date=0)

            moves.append(UnitMove(source=source_loc, reference=reference, target=target_loc))
