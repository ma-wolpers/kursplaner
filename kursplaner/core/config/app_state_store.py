from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from bw_libs.app_paths import atomic_write_json
from kursplaner.core.config.settings import SCRIPT_DIR

LAST_DAILY_LOG_DATE_KEY = "last_daily_log_date"


def _app_state_file() -> Path:
    """Liefert den Pfad zur App-Statusdatei."""
    return SCRIPT_DIR / "config" / "logs" / "app_state_logs.json"


def load_app_state() -> dict[str, str]:
    """Lädt den App-Status robust und liefert nur String-Keys/Values."""
    path = _app_state_file()
    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(payload, dict):
        return {}

    state: dict[str, str] = {}
    for key, value in payload.items():
        if isinstance(key, str) and isinstance(value, str):
            state[key] = value
    return state


def save_app_state(state: dict[str, str]) -> None:
    """Speichert den App-Status als UTF-8 JSON-Datei."""
    path = _app_state_file()
    payload: dict[str, str] = {}
    for key, value in state.items():
        if isinstance(key, str) and isinstance(value, str):
            payload[key] = value

    atomic_write_json(path, payload)


def load_last_daily_log_date() -> date | None:
    """Liest das Datum des letzten Tageslogs aus dem App-Status."""
    state = load_app_state()
    raw = state.get(LAST_DAILY_LOG_DATE_KEY, "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def save_last_daily_log_date(value: date) -> None:
    """Persistiert das Datum des zuletzt erstellten Tageslogs."""
    state = load_app_state()
    state[LAST_DAILY_LOG_DATE_KEY] = value.isoformat()
    save_app_state(state)
