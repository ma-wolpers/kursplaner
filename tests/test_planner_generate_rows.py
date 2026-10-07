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

from kursplaner.core.domain.course_rhythm import parse_rhythm
from kursplaner.core.domain.planner import generate_rows

START = date(2026, 9, 28)
FERIENBEGINN = date(2026, 10, 12)
EVENTS = {FERIENBEGINN + timedelta(days=offset): "Herbstferien" for offset in range(12)}

# Vor der Umstellung auf den Rhythmus wurden hier Wochentag-Mengen ({0}/{3})
# uebergeben; die Erwartungswerte von C1-C5 sind seitdem unveraendert.
MONDAY = parse_rhythm(["Mo 08:00 2"])
THURSDAY = parse_rhythm(["Do 07:50 2"])


def test_c1_end_not_teaching_day_without_flag_has_no_end_row():
    """C1: Ende ist kein Unterrichtstag, Flag aus -> keine Zeile am Ende."""
    rows = generate_rows(START, FERIENBEGINN, THURSDAY, EVENTS)
    assert rows == [(date(2026, 10, 1), ""), (date(2026, 10, 8), "")]


def test_c2_flag_appends_ferien_marker_row_at_end():
    """C2: Flag an -> genau eine Ferien-Marker-Abschlusszeile am Ferienbeginn."""
    rows = generate_rows(START, FERIENBEGINN, THURSDAY, EVENTS, include_end_even_if_not_weekday=True)
    assert rows == [
        (date(2026, 10, 1), ""),
        (date(2026, 10, 8), ""),
        (FERIENBEGINN, "X Herbstferien X"),
    ]


def test_c3_end_is_teaching_day_yields_single_marker_row_without_duplicate():
    """C3: Ende ist Unterrichtstag -> Zeile kommt aus der Schleife, Flag dupliziert nicht."""
    rows = generate_rows(START, FERIENBEGINN, MONDAY, EVENTS, include_end_even_if_not_weekday=True)
    assert rows == [
        (date(2026, 9, 28), ""),
        (date(2026, 10, 5), ""),
        (FERIENBEGINN, "X Herbstferien X"),
    ]


def test_c4_end_without_calendar_event_uses_ferienbeginn_fallback():
    """C4: Ende fehlt im Kalender -> Marker mit Fallback-Grund ``Ferienbeginn``."""
    rows = generate_rows(START, FERIENBEGINN, THURSDAY, {}, include_end_even_if_not_weekday=True)
    assert rows[-1] == (FERIENBEGINN, "X Ferienbeginn X")
    assert len(rows) == 3


def test_c5_end_inside_ferien_block_midweek():
    """C5: Ende mitten im Ferienblock (Mi) -> Abschlusszeile an genau diesem Tag."""
    end = date(2026, 10, 14)
    rows = generate_rows(START, end, THURSDAY, EVENTS, include_end_even_if_not_weekday=True)
    assert rows == [
        (date(2026, 10, 1), ""),
        (date(2026, 10, 8), ""),
        (end, "X Herbstferien X"),
    ]


# --- Abschluss-Flag mit Wochenparitaet, Segmenten und A/B-Tagen --------------
# Der 12.10.2026 (Ferienbeginn) liegt in KW 42 (gerade), der 05.10. in KW 41,
# der 28.09. in KW 40.


def test_p1_wrong_parity_at_end_without_flag_has_no_end_row():
    rows = generate_rows(START, FERIENBEGINN, parse_rhythm(["Mo 08:00 2 uKW"]), EVENTS)
    assert rows == [(date(2026, 10, 5), "")]


def test_p2_wrong_parity_at_end_with_flag_appends_single_marker_row():
    rows = generate_rows(
        START, FERIENBEGINN, parse_rhythm(["Mo 08:00 2 uKW"]), EVENTS, include_end_even_if_not_weekday=True
    )
    assert rows == [(date(2026, 10, 5), ""), (FERIENBEGINN, "X Herbstferien X")]


def test_p3_matching_parity_at_end_comes_from_loop_without_duplicate():
    rows = generate_rows(
        START, FERIENBEGINN, parse_rhythm(["Mo 08:00 2 gKW"]), EVENTS, include_end_even_if_not_weekday=True
    )
    assert rows == [(date(2026, 9, 28), ""), (FERIENBEGINN, "X Herbstferien X")]


def test_p4_end_inside_later_segment_without_that_weekday_gets_marker_row():
    rhythm = parse_rhythm(["Mo 08:00 2", "ab 05-10-26 Do 07:50 2"])
    rows = generate_rows(START, FERIENBEGINN, rhythm, EVENTS, include_end_even_if_not_weekday=True)
    assert rows == [
        (date(2026, 9, 28), ""),
        (date(2026, 10, 8), ""),
        (FERIENBEGINN, "X Herbstferien X"),
    ]


def test_p5_ab_day_end_row_is_ferien_row_with_zero_hours():
    """P5: prueft bewusst ZWEI Ebenen, die sich scheinbar widersprechen.

    1. Rhythmus-Semantik: Der Rhythmus kennt am 12.10. (KW 42, gerade) eine
       gKW-Stunde - ``hours_for_date`` liefert 2.
    2. Darstellung eines Ferientags als Planzeile: Die Abschlusszeile am
       Ferienbeginn traegt einen Ferien-Marker und hat in
       ``DayColumn.stunden()`` daher 0 Stunden.

    Die Diskrepanz ist gewollt: Ein Ferientag wird nie als Unterrichtsstunde
    gezaehlt, egal was der Rhythmus fuer dieses Datum vorsieht.
    """
    from kursplaner.core.domain.course_rhythm import hours_for_date
    from tests.day_column_factory import make_day_column

    rhythm = parse_rhythm(["Mo 08:00 2 gKW", "Mo 11:30 1 uKW"])
    rows = generate_rows(START, FERIENBEGINN, rhythm, EVENTS, include_end_even_if_not_weekday=True)
    assert rows == [
        (date(2026, 9, 28), ""),
        (date(2026, 10, 5), ""),
        (FERIENBEGINN, "X Herbstferien X"),
    ]
    assert hours_for_date(rhythm, FERIENBEGINN) == 2  # Ebene 1: Rhythmus
    end_row = make_day_column(datum="12-10-26", thema_ausfall=rows[-1][1], rhythm=rhythm)
    assert end_row.stunden() == 0  # Ebene 2: Ferienzeile
    assert end_row.startzeit() == ""
    # Gegenprobe: A/B-Stunden der regulaeren Zeilen kommen aus dem Rhythmus.
    assert make_day_column(datum="28-09-26", rhythm=rhythm).stunden() == 2
    assert make_day_column(datum="05-10-26", rhythm=rhythm).stunden() == 1


# P6 (Ende ist manueller Ausfall statt Ferientag) entfaellt: `end` ist laut
# einzigem Aufrufer immer der Ferienbeginn, manuelle Ausfaelle entstehen erst
# nach der Generierung.


# --- Vertrag: vollstaendiger Rhythmus, Wechsel an Segmentgrenzen ------------


def test_rhythm_switches_at_segment_boundary_within_one_call():
    rhythm = parse_rhythm(["Mo 08:00 2", "ab 15-05-26 Di 10:00 2"])
    rows = generate_rows(date(2026, 5, 1), date(2026, 5, 31), rhythm, {})
    assert [row_date for row_date, _ in rows] == [
        date(2026, 5, 4),
        date(2026, 5, 11),
        date(2026, 5, 19),
        date(2026, 5, 26),
    ]


def test_segment_boundary_combined_with_parity():
    """Basis jede Woche Mo, ab 12.10. nur noch ungerade KW."""
    rhythm = parse_rhythm(["Mo 08:00 2", "ab 12-10-26 Mo 08:00 2 uKW"])
    rows = generate_rows(date(2026, 9, 28), date(2026, 11, 9), rhythm, {})
    assert [row_date for row_date, _ in rows] == [
        date(2026, 9, 28),  # KW 40, Basis
        date(2026, 10, 5),  # KW 41, Basis
        date(2026, 10, 19),  # KW 43
        date(2026, 11, 2),  # KW 45
    ]


def test_biweekly_rows_only_in_matching_week_and_ferien_marker_only_there():
    rhythm = parse_rhythm(["Do 07:50 2 gKW"])
    events = {date(2026, 10, 15): "Herbstferien", date(2026, 10, 22): "Herbstferien"}
    rows = generate_rows(date(2026, 9, 28), date(2026, 10, 31), rhythm, events)
    # KW 40: 01.10., KW 42: 15.10. (Ferien, gerade), KW 43: 22.10. ungerade -> keine Zeile
    assert rows == [
        (date(2026, 10, 1), ""),
        (date(2026, 10, 15), "X Herbstferien X"),
        (date(2026, 10, 29), ""),
    ]
