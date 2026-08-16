"""Zeilenauswahl- und Platzierungslogik fuer Plantabellen-Operationen.

Arbeitet durchgehend auf rohen `(headers, rows)`-Paaren statt auf `DayColumn`,
damit teure YAML-/Link-Aufloesung (siehe `LoadPlanDetailUseCase.build_day_columns`)
fuer Massenoperationen ueber viele Kurse (z. B. Live-Vorschau schulweiter
Ausfaelle) vermieden wird. Wird sowohl vom Schulweite-Ausfall-Feature als auch
vom `TimetableChangeDialog` genutzt (siehe `plan_gap_placement`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from kursplaner.core.domain.content_markers import resolve_row_cancel_state
from kursplaner.core.domain.plan_table import parse_plan_row_date


def _col_index(headers: list[str], name: str) -> int | None:
    """Liefert den Index einer Spaltenueberschrift (case-insensitiv); None falls fehlt."""
    lc = name.lower()
    for i, h in enumerate(headers):
        if str(h).strip().lower() == lc:
            return i
    return None


def find_stattfindend_rows_in_range(
    headers: list[str],
    rows: list[list[str]],
    date_from: date,
    date_to: date,
) -> list[int]:
    """Liefert die Row-Indizes stattfindender (nicht bereits Ausfall/Ferien) Zeilen im Datumsbereich.

    Einzige gemeinsame Selektionslogik fuer "welche Einheiten waeren in diesem
    Zeitraum betroffen" - genutzt sowohl von der Live-Vorschau als auch vom
    tatsaechlichen Anwenden eines schulweiten Ausfalls, damit beide nicht
    unabhaengig voneinander driften.
    """
    idx_datum = _col_index(headers, "datum")
    if idx_datum is None:
        return []

    result: list[int] = []
    for row_index, row in enumerate(rows):
        raw_datum = row[idx_datum] if idx_datum < len(row) else ""
        row_date = parse_plan_row_date(raw_datum)
        if row_date is None or not (date_from <= row_date <= date_to):
            continue
        if resolve_row_cancel_state(headers, row):
            continue
        result.append(row_index)
    return result


@dataclass(frozen=True)
class GapPlacementPlan:
    """Ergebnis einer Lueckensuche: gefundene freie Slots plus verbleibender Anhaenge-Bedarf."""

    gap_indices: tuple[int, ...]
    append_count: int


def plan_gap_placement(
    *,
    is_available_gap: Callable[[int], bool],
    slot_count: int,
    start_after_index: int,
    needed_count: int,
) -> GapPlacementPlan:
    """Sucht ab `start_after_index` vorwaerts nach `needed_count` freien Slots.

    Was nicht unter den vorhandenen Slots gefunden wird, muss der Aufrufer
    als neue (bei Plantabellen: datumslose) Slots anhaengen - das ersetzt die
    frueher uebliche "kein Platz gefunden, Inhalt verwerfen"-Behandlung ueberall,
    wo diese Funktion genutzt wird.

    Args:
        is_available_gap: Prueft, ob der Slot am gegebenen Index frei ist.
        slot_count: Gesamtzahl vorhandener Slots (obere Schranke fuer die Suche).
        start_after_index: Erster zu pruefender Index (i. d. R. Cancel-Index + 1).
        needed_count: Anzahl benoetigter freier Slots.
    """
    gap_indices: list[int] = []
    index = max(0, start_after_index)
    while index < slot_count and len(gap_indices) < needed_count:
        if is_available_gap(index):
            gap_indices.append(index)
        index += 1
    return GapPlacementPlan(gap_indices=tuple(gap_indices), append_count=needed_count - len(gap_indices))


def strip_empty_dateless_rows(headers: list[str], rows: list[list[str]]) -> list[list[str]]:
    """Entfernt jede Zeile ohne Datum und ohne Inhalt, unabhaengig von ihrer Herkunft.

    Explizite, benannte Invariante ("datumslose Zeilen werden auf das
    notwendige Minimum reduziert") - wird bewusst NICHT implizit in
    `save_plan_table` eingebaut, sondern von jeder Operation aufgerufen, die
    selbst datumslose Zeilen erzeugen kann (Schulweite-Ausfall-Apply/-Revert,
    `TimetableChangeDialog`-Uebernehmen).
    """
    idx_datum = _col_index(headers, "datum")
    if idx_datum is None:
        return list(rows)
    idx_inhalt = _col_index(headers, "inhalt")
    idx_thema_ausfall = _col_index(headers, "thema/ausfall")

    result: list[list[str]] = []
    for row in rows:
        raw_datum = row[idx_datum] if idx_datum < len(row) else ""
        if parse_plan_row_date(raw_datum) is None:
            inhalt = str(row[idx_inhalt]).strip() if idx_inhalt is not None and idx_inhalt < len(row) else ""
            thema = (
                str(row[idx_thema_ausfall]).strip()
                if idx_thema_ausfall is not None and idx_thema_ausfall < len(row)
                else ""
            )
            if not inhalt and not thema:
                continue
        result.append(row)
    return result
