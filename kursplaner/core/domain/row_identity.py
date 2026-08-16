"""Identitaetsaufloesung fuer verschobene Einheiten gegen die aktuelle Plantabelle.

Kernprimitiv des Schulweite-Ausfall-Features: gegeben ein `UnitMove` (Datum +
Position + Referenz, siehe `core.domain.school_wide_cancellation`) und die
*aktuelle* `(headers, rows)`-Tabelle, findet dieses Modul heraus, ob die Quell-
und Zielzeile noch eindeutig auffindbar und im erwarteten Zustand sind - ohne
je den frueheren Zellinhalt zu kennen (kein Content-Snapshot). Wird sowohl von
`SchoolWideCancellationRevertUseCase` (um zu handeln) als auch vom
Diagnose-Usecase (um nur zu berichten) genutzt.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from kursplaner.core.domain.content_markers import normalize_marker_text, resolve_row_cancel_state
from kursplaner.core.domain.school_wide_cancellation import RowLocation, UnitMove, UnitReference
from kursplaner.core.domain.wiki_links import extract_wiki_link_target


class ResolutionStatus(Enum):
    """Ergebnisklasse einer Identitaetsaufloesung."""

    MATCH = "match"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class SourceResolution:
    """Ergebnis der Quellzeilen-Aufloesung (die urspruenglich stornierte Zeile)."""

    status: ResolutionStatus
    row_index: int | None
    detail: str = ""


@dataclass(frozen=True)
class TargetResolution:
    """Ergebnis der Zielzeilen-Aufloesung (wo der verdraengte Inhalt aktuell liegt)."""

    status: ResolutionStatus
    row_index: int | None
    current_reference: UnitReference | None = None
    detail: str = ""


@dataclass(frozen=True)
class MoveResolution:
    """Kombiniertes Ergebnis fuer einen einzelnen `UnitMove`."""

    status: ResolutionStatus
    source: SourceResolution
    target: TargetResolution
    detail: str = ""


def _col_index(headers: list[str], name: str) -> int | None:
    """Liefert den Index einer Spaltenueberschrift (case-insensitiv); None falls fehlt."""
    lc = name.lower()
    for i, h in enumerate(headers):
        if str(h).strip().lower() == lc:
            return i
    return None


def _rows_with_date(headers: list[str], rows: list[list[str]], date_text: str) -> list[int]:
    idx_datum = _col_index(headers, "datum")
    if idx_datum is None:
        return []
    return [i for i, row in enumerate(rows) if idx_datum < len(row) and str(row[idx_datum]).strip() == date_text]


def _dateless_row_indices(headers: list[str], rows: list[list[str]]) -> list[int]:
    idx_datum = _col_index(headers, "datum")
    if idx_datum is None:
        return []
    return [i for i, row in enumerate(rows) if idx_datum < len(row) and not str(row[idx_datum]).strip()]


def extract_row_reference(headers: list[str], row: list[str]) -> UnitReference:
    """Leitet die Wiedererkennungs-Referenz einer Zeile aus ihrer `Inhalt`-Zelle ab."""
    idx_inhalt = _col_index(headers, "inhalt")
    inhalt = str(row[idx_inhalt]) if idx_inhalt is not None and idx_inhalt < len(row) else ""
    link_target = extract_wiki_link_target(inhalt)
    if link_target:
        return UnitReference(kind="link", value=link_target)
    return UnitReference(kind="raw_text", value=normalize_marker_text(inhalt))


def resolve_source(
    headers: list[str],
    rows: list[list[str]],
    source: RowLocation,
) -> SourceResolution:
    """Findet die stornierte Quellzeile und prueft, ob sie noch als Ausfall markiert ist.

    Prueft bewusst nur den strukturellen Zustand (Ausfall-Marker vorhanden),
    nicht den genauen Grundtext - eine kosmetisch bearbeitete Ausfall-Begruendung
    ist kein struktureller Konflikt. Fehlt der Marker komplett (z. B. weil die
    Zeile ueber das bestehende Strg+B-Werkzeug manuell wiederhergestellt wurde),
    ist das ein Fehler, kein Warnfall - es gibt nichts, das "trotzdem"
    weitergefuehrt werden koennte.
    """
    if source.date is None:
        return SourceResolution(ResolutionStatus.ERROR, None, "Quellposition ohne Datum ist ungueltig.")

    candidates = _rows_with_date(headers, rows, source.date)
    if source.position_in_date >= len(candidates):
        return SourceResolution(
            ResolutionStatus.ERROR,
            None,
            f"Keine Zeile mehr an Position {source.position_in_date} fuer Datum {source.date}.",
        )

    row_index = candidates[source.position_in_date]
    if not resolve_row_cancel_state(headers, rows[row_index]):
        return SourceResolution(
            ResolutionStatus.ERROR,
            row_index,
            "Zeile traegt keinen Ausfall-Marker mehr (evtl. manuell wiederhergestellt).",
        )
    return SourceResolution(ResolutionStatus.MATCH, row_index)


def resolve_target(
    headers: list[str],
    rows: list[list[str]],
    target: RowLocation | None,
    expected_reference: UnitReference | None,
) -> TargetResolution:
    """Findet die Zielzeile des verdraengten Inhalts und prueft die Referenz.

    `target=None` bedeutet: die stornierte Zeile hatte keinen Inhalt, es gibt
    nichts zu lokalisieren (immer MATCH). Bei gesetztem Datum ist die Position
    der primaere Anker (wie bei der Quelle); bei datumslosen Zeilen gibt es
    keinen verlaesslichen Positions-Anker, daher wird ueber alle aktuell
    datumslosen Zeilen nach der Referenz gesucht - genau ein Treffer gilt als
    sicher, null oder mehrere als Fehler.
    """
    if target is None:
        return TargetResolution(ResolutionStatus.MATCH, None)

    if target.date is not None:
        candidates = _rows_with_date(headers, rows, target.date)
        if target.position_in_date >= len(candidates):
            return TargetResolution(
                ResolutionStatus.ERROR,
                None,
                f"Keine Zeile mehr an Position {target.position_in_date} fuer Datum {target.date}.",
            )
        row_index = candidates[target.position_in_date]
    else:
        dateless_indices = _dateless_row_indices(headers, rows)
        matches = [
            i for i in dateless_indices if extract_row_reference(headers, rows[i]) == expected_reference
        ]
        if not matches:
            return TargetResolution(ResolutionStatus.ERROR, None, "Keine datumslose Zeile mit passender Referenz gefunden.")
        if len(matches) > 1:
            return TargetResolution(
                ResolutionStatus.ERROR, None, "Mehrdeutig: mehrere datumslose Zeilen mit passender Referenz gefunden."
            )
        row_index = matches[0]

    current_reference = extract_row_reference(headers, rows[row_index])
    if expected_reference is not None and current_reference != expected_reference:
        return TargetResolution(
            ResolutionStatus.WARNING,
            row_index,
            current_reference,
            f"Referenz geaendert: erwartet {expected_reference}, aktuell {current_reference}.",
        )
    return TargetResolution(ResolutionStatus.MATCH, row_index, current_reference)


def resolve_move(headers: list[str], rows: list[list[str]], move: UnitMove) -> MoveResolution:
    """Loest einen kompletten `UnitMove` (Quelle + Ziel) gegen die aktuelle Tabelle auf."""
    source_res = resolve_source(headers, rows, move.source)
    if source_res.status == ResolutionStatus.ERROR:
        return MoveResolution(ResolutionStatus.ERROR, source_res, TargetResolution(ResolutionStatus.ERROR, None), source_res.detail)

    target_res = resolve_target(headers, rows, move.target, move.reference)
    if target_res.status == ResolutionStatus.ERROR:
        return MoveResolution(ResolutionStatus.ERROR, source_res, target_res, target_res.detail)
    if target_res.status == ResolutionStatus.WARNING:
        return MoveResolution(ResolutionStatus.WARNING, source_res, target_res, target_res.detail)
    return MoveResolution(ResolutionStatus.MATCH, source_res, target_res)
