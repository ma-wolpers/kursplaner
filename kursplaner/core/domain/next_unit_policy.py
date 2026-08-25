"""Zentrale Policy: gilt eine Einheit noch als "anstehend" ("nächste Einheit")?

Einziger Wahrheitsort für diese Frage im gesamten Codebase — Grid-Markierung
(`overview_controller.py`), Kursübersicht (`plan_overview_query_usecase.py`)
und die nummerische Spaltenauswahl (`selection_controller.py`) rufen
ausschließlich `unit_counts_as_upcoming()` auf, statt eigene Zeitvergleichs-
logik zu implementieren. Reines Domain-Modul ohne GUI-/Tk-Abhängigkeiten.
"""

from __future__ import annotations

from datetime import date, datetime, time


def unit_counts_as_upcoming(
    row_date: date | None,
    start_time_text: str,
    *,
    now: datetime,
    global_cutoff_enabled: bool,
    global_cutoff_time: time,
) -> bool:
    """True, wenn eine Einheit an `row_date` noch als "anstehend" gilt.

    Semantik: "anstehend" heißt, die Startzeit der Einheit liegt noch in der
    Zukunft. Eine bereits begonnene/laufende Einheit gilt NICHT mehr als
    anstehend (Grundannahme: der Kursplaner wird nicht während einer
    laufenden Stunde zur Auswahl der "nächsten Einheit" benutzt) — heute mit
    Startzeit exakt `now.time()` zählt daher bereits als nicht mehr anstehend.

    Ist `global_cutoff_enabled` gesetzt, ersetzt ein einzelner globaler
    Zeitpunkt (`global_cutoff_time`) vollständig den Startzeit-Vergleich für
    heutige Einheiten.

    Ist keine Startzeit ermittelbar (`start_time_text == ""`), gilt die
    Einheit bewusst konservativ als anstehend — kein Rhythmus-Eintrag für
    den Tag ist kein Grund, die Einheit zu verstecken.
    """
    if row_date is None:
        return False

    today = now.date()
    if row_date > today:
        return True
    if row_date < today:
        return False

    if global_cutoff_enabled:
        return now.time() < global_cutoff_time

    if not start_time_text:
        return True

    start_time = _parse_time(start_time_text)
    if start_time is None:
        return True

    return now.time() < start_time


def _parse_time(text: str) -> time | None:
    """Parst einen `"HH:MM"`-String; `None` bei unerwartetem Format."""
    try:
        return datetime.strptime(text, "%H:%M").time()
    except ValueError:
        return None
