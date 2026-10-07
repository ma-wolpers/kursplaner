"""Charakterisierung von `planner.generate_rows` inkl. Ferienbeginn-Abschlusszeile.

Hält das bestehende Verhalten von ``include_end_even_if_not_weekday`` fest,
bevor die Zeilengenerierung auf den Rhythmus (inkl. Wochenparität)
umgestellt wird: Die Erwartungswerte stammen aus dem Verhalten des Codes
vor der Umstellung und dürfen sich durch sie nicht ändern.

Synthetischer Kalender: Herbstferien ab Mo 12.10.2026 (KW 42); Planbeginn
Mo 28.09.2026 (KW 40).
"""

from __future__ import annotations

from datetime import date, timedelta

from kursplaner.core.domain.planner import generate_rows

START = date(2026, 9, 28)
FERIENBEGINN = date(2026, 10, 12)
EVENTS = {FERIENBEGINN + timedelta(days=offset): "Herbstferien" for offset in range(12)}

MONDAY = 0
THURSDAY = 3


def test_c1_end_not_teaching_day_without_flag_has_no_end_row():
    """C1: Ende ist kein Unterrichtstag, Flag aus -> keine Zeile am Ende."""
    rows = generate_rows(START, FERIENBEGINN, {THURSDAY}, EVENTS)
    assert rows == [(date(2026, 10, 1), ""), (date(2026, 10, 8), "")]


def test_c2_flag_appends_ferien_marker_row_at_end():
    """C2: Flag an -> genau eine Ferien-Marker-Abschlusszeile am Ferienbeginn."""
    rows = generate_rows(START, FERIENBEGINN, {THURSDAY}, EVENTS, include_end_even_if_not_weekday=True)
    assert rows == [
        (date(2026, 10, 1), ""),
        (date(2026, 10, 8), ""),
        (FERIENBEGINN, "X Herbstferien X"),
    ]


def test_c3_end_is_teaching_day_yields_single_marker_row_without_duplicate():
    """C3: Ende ist Unterrichtstag -> Zeile kommt aus der Schleife, Flag dupliziert nicht."""
    rows = generate_rows(START, FERIENBEGINN, {MONDAY}, EVENTS, include_end_even_if_not_weekday=True)
    assert rows == [
        (date(2026, 9, 28), ""),
        (date(2026, 10, 5), ""),
        (FERIENBEGINN, "X Herbstferien X"),
    ]


def test_c4_end_without_calendar_event_uses_ferienbeginn_fallback():
    """C4: Ende fehlt im Kalender -> Marker mit Fallback-Grund ``Ferienbeginn``."""
    rows = generate_rows(START, FERIENBEGINN, {THURSDAY}, {}, include_end_even_if_not_weekday=True)
    assert rows[-1] == (FERIENBEGINN, "X Ferienbeginn X")
    assert len(rows) == 3


def test_c5_end_inside_ferien_block_midweek():
    """C5: Ende mitten im Ferienblock (Mi) -> Abschlusszeile an genau diesem Tag."""
    end = date(2026, 10, 14)
    rows = generate_rows(START, end, {THURSDAY}, EVENTS, include_end_even_if_not_weekday=True)
    assert rows == [
        (date(2026, 10, 1), ""),
        (date(2026, 10, 8), ""),
        (end, "X Herbstferien X"),
    ]
