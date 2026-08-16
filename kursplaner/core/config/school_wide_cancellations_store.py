"""Persistenz fuer schulweite Ausfall-Eintraege.

Folgt dem bestehenden Muster von `ui_preferences_store.py` (flaches JSON,
defensives Laden). Eigene Datei statt Einmischung in `ui_preferences.json`,
da diese Eintraege wachsende strukturierte Fachdaten sind, keine Einstellungen.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from bw_libs.app_paths import atomic_write_json
from bw_libs.safe_read import read_json_or_default
from kursplaner.core.config.settings import SCRIPT_DIR
from kursplaner.core.domain.school_wide_cancellation import (
    CourseApplicationLedger,
    RowLocation,
    SchoolWideCancellationEntry,
    UnitMove,
    UnitReference,
)

_STORE_FILE = "schulweite_ausfaelle.json"


def _store_path() -> Path:
    return SCRIPT_DIR / "config" / _STORE_FILE


def _load_payload() -> dict[str, object]:
    path = _store_path()
    if not path.exists():
        return {}
    payload = read_json_or_default(path, default=None)
    if isinstance(payload, dict):
        return payload
    return {}


def _serialize_row_location(location: RowLocation | None) -> dict[str, object] | None:
    if location is None:
        return None
    return {"date": location.date, "position_in_date": location.position_in_date}


def _deserialize_row_location(raw: object) -> RowLocation | None:
    if not isinstance(raw, dict):
        return None
    raw_date = raw.get("date")
    date_value = str(raw_date) if isinstance(raw_date, str) and raw_date.strip() else None
    try:
        position = int(raw.get("position_in_date", 0))
    except (TypeError, ValueError):
        position = 0
    return RowLocation(date=date_value, position_in_date=position)


def _serialize_reference(reference: UnitReference | None) -> dict[str, object] | None:
    if reference is None:
        return None
    return {"kind": reference.kind, "value": reference.value}


def _deserialize_reference(raw: object) -> UnitReference | None:
    if not isinstance(raw, dict):
        return None
    kind = raw.get("kind")
    if kind not in ("link", "raw_text"):
        return None
    return UnitReference(kind=kind, value=str(raw.get("value", "")))


def _serialize_move(move: UnitMove) -> dict[str, object]:
    return {
        "source": _serialize_row_location(move.source),
        "reference": _serialize_reference(move.reference),
        "target": _serialize_row_location(move.target),
    }


def _deserialize_move(raw: dict[str, object]) -> UnitMove | None:
    source = _deserialize_row_location(raw.get("source"))
    if source is None:
        return None
    return UnitMove(
        source=source,
        reference=_deserialize_reference(raw.get("reference")),
        target=_deserialize_row_location(raw.get("target")),
    )


def _serialize_ledger(ledger: CourseApplicationLedger) -> dict[str, object]:
    return {"moves": [_serialize_move(move) for move in ledger.moves]}


def _deserialize_ledger(raw: dict[str, object]) -> CourseApplicationLedger:
    raw_moves = raw.get("moves")
    moves: list[UnitMove] = []
    if isinstance(raw_moves, list):
        for raw_move in raw_moves:
            if isinstance(raw_move, dict):
                move = _deserialize_move(raw_move)
                if move is not None:
                    moves.append(move)
    return CourseApplicationLedger(moves=tuple(moves))


def _serialize_entry(entry: SchoolWideCancellationEntry) -> dict[str, object]:
    return {
        "entry_id": entry.entry_id,
        "reason": entry.reason,
        "date_from": entry.date_from.isoformat(),
        "date_to": entry.date_to.isoformat(),
        "grade_levels": sorted(entry.grade_levels),
        "created_at": entry.created_at,
        "course_ledgers": {
            course_key: _serialize_ledger(ledger) for course_key, ledger in entry.course_ledgers.items()
        },
    }


def _deserialize_entry(raw: dict[str, object]) -> SchoolWideCancellationEntry | None:
    """Deserialisiert einen Eintrag; liefert `None` bei korrupten/unlesbaren Daten.

    Einzelne kaputte Eintraege werden vom Aufrufer uebersprungen statt die
    gesamte Liste zu verwerfen (defensives Laden, siehe `ui_preferences_store.py`).
    """
    try:
        entry_id = str(raw["entry_id"])
        reason = str(raw["reason"])
        date_from = date.fromisoformat(str(raw["date_from"]))
        date_to = date.fromisoformat(str(raw["date_to"]))
    except (KeyError, ValueError, TypeError):
        return None
    created_at = str(raw.get("created_at", ""))

    grade_levels_raw = raw.get("grade_levels", [])
    grade_levels = (
        frozenset(int(g) for g in grade_levels_raw if isinstance(g, (int, str)) and str(g).strip().lstrip("-").isdigit())
        if isinstance(grade_levels_raw, list)
        else frozenset()
    )

    course_ledgers_raw = raw.get("course_ledgers", {})
    course_ledgers: dict[str, CourseApplicationLedger] = {}
    if isinstance(course_ledgers_raw, dict):
        for course_key, ledger_raw in course_ledgers_raw.items():
            if isinstance(ledger_raw, dict):
                course_ledgers[str(course_key)] = _deserialize_ledger(ledger_raw)

    return SchoolWideCancellationEntry(
        entry_id=entry_id,
        reason=reason,
        date_from=date_from,
        date_to=date_to,
        grade_levels=grade_levels,
        created_at=created_at,
        course_ledgers=course_ledgers,
    )


def load_school_wide_cancellations() -> list[SchoolWideCancellationEntry]:
    """Laedt alle persistierten schulweiten Ausfall-Eintraege.

    Korrupte oder unlesbare Einzeleintraege werden uebersprungen statt die
    gesamte Liste zu verwerfen.
    """
    payload = _load_payload()
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list):
        return []

    entries: list[SchoolWideCancellationEntry] = []
    for raw_entry in raw_entries:
        if isinstance(raw_entry, dict):
            entry = _deserialize_entry(raw_entry)
            if entry is not None:
                entries.append(entry)
    return entries


def save_school_wide_cancellations(entries: list[SchoolWideCancellationEntry]) -> None:
    """Persistiert die vollstaendige Liste schulweiter Ausfall-Eintraege."""
    payload: dict[str, object] = {"entries": [_serialize_entry(entry) for entry in entries]}
    atomic_write_json(_store_path(), payload)
