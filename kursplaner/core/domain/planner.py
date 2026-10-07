from datetime import date, timedelta

from kursplaner.core.domain.content_markers import build_ferien_marker
from kursplaner.core.domain.course_rhythm import WeekdayRhythm, active_weekdays, is_teaching_day
from kursplaner.core.domain.models import PlanResult

PlanRow = tuple[date, str]
PlanCalendarEvent = tuple[str, date, date]


def relevant_years(term: str) -> set[int]:
    """Leitet aus einem Halbjahrestoken die benötigten Kalenderjahre ab.

    Beispiel: ``26-2`` benoetigt Daten aus 2026 und 2027.
    """
    year = 2000 + int(term[:2])
    if term.endswith("-2"):
        return {year, year + 1}
    return {year}


def _find_block(blocks: list[PlanCalendarEvent], keyword: str, year: int) -> tuple[date, date] | None:
    """Findet den ersten Ferienblock eines Jahres mit passendem Namensschlüsselwort."""
    for name, start, end in blocks:
        if keyword in name.lower() and start.year == year:
            return start, end
    return None


def determine_term_range(term: str, ferien_blocks: list[PlanCalendarEvent]) -> tuple[date, date]:
    """Berechnet Start/Ende eines Halbjahrs aus Ferienblöcken.

    Die Regeln folgen der schulischen Logik (Winter-/Sommergrenzen) und werfen
    `RuntimeError`, wenn notwendige Blöcke fehlen.
    """
    year = 2000 + int(term[:2])
    kind = term[-1]

    if kind == "1":
        winter = _find_block(ferien_blocks, "winter", year)
        sommer = _find_block(ferien_blocks, "sommer", year)

        if not winter:
            raise RuntimeError("Winterferien zur Bestimmung des Anfangs fehlen.")
        if not sommer:
            raise RuntimeError("Sommerferien zur Bestimmung des Endes fehlen.")

        return winter[1], sommer[0] + timedelta(days=7)

    sommer = _find_block(ferien_blocks, "sommer", year)
    winter = _find_block(ferien_blocks, "winter", year + 1)

    if not sommer:
        raise RuntimeError("Sommerferien zur Bestimmung des Anfangs fehlen.")
    if not winter:
        raise RuntimeError("Winterferien zur Bestimmung des Endes fehlen.")

    return sommer[1], winter[0] + timedelta(days=2)


def find_next_vacation_start(from_date: date, ferien_blocks: list[PlanCalendarEvent]) -> date:
    """Liefert den chronologisch nächsten Ferienbeginn ab ``from_date``."""
    starts = sorted(start for _, start, _ in ferien_blocks if start >= from_date)
    if not starts:
        raise RuntimeError("Ab Startdatum wurde keine nächste Ferienphase gefunden.")
    return starts[0]


def find_vacation_start_with_horizon(from_date: date, ferien_blocks: list[PlanCalendarEvent], horizon: int) -> date:
    """Liefert den Ferienbeginn in gegebener Horizontebene (1=naechste, 2=uebernaechste)."""
    normalized_horizon = max(1, int(horizon))
    starts = sorted(start for _, start, _ in ferien_blocks if start >= from_date)
    if len(starts) < normalized_horizon:
        if normalized_horizon == 1:
            raise RuntimeError("Ab Startdatum wurde keine nächste Ferienphase gefunden.")
        raise RuntimeError(f"Ab Startdatum wurden nicht genug Ferienphasen gefunden (benötigt: {normalized_horizon}).")
    return starts[normalized_horizon - 1]


def find_next_halfyear_boundary_start(from_date: date, ferien_blocks: list[PlanCalendarEvent]) -> date:
    """Liefert den naechsten Sommer- oder Winterferienbeginn ab ``from_date``."""
    boundary_starts = sorted(
        start
        for name, start, _ in ferien_blocks
        if start >= from_date and ("sommer" in name.lower() or "winter" in name.lower())
    )
    if not boundary_starts:
        raise RuntimeError("Ab Startdatum wurde keine Halbjahresgrenze (Sommer/Winterferien) gefunden.")
    return boundary_starts[0]


def generate_rows(
    start: date,
    end: date,
    rhythm: tuple[WeekdayRhythm, ...],
    events: dict[date, str],
    include_end_even_if_not_weekday: bool = False,
) -> list[PlanRow]:
    """Erzeugt fachliche Planzeilen im Bereich ``start`` bis ``end``.

    Vertrag: ``rhythm`` ist der **vollstaendige** Rhythmus eines Kurses mit
    allen ``ab``-Segmenten. Fuer jeden Tag entscheidet
    :func:`~kursplaner.core.domain.course_rhythm.is_teaching_day` (Segment,
    Wochentag, KW-Paritaet), ob eine Zeile entsteht; innerhalb eines Aufrufs
    wechselt der Rhythmus daher an jeder ``ab``-Grenze. Ferien/Feiertage
    bleiben als Datumseintrag mit Ferien-Marker (siehe
    :func:`kursplaner.core.domain.content_markers.build_ferien_marker`)
    sichtbar; die Stundenzahl selbst wird nicht in der Zeile gefuehrt,
    sondern spaeter aus dem Rhythmus abgeleitet.

    Args:
        start: Erster Tag des Bereichs.
        end: Letzter Tag des Bereichs (inklusive).
        rhythm: Vollstaendiger Rhythmus (alle Segmente).
        events: Ferien-/Feiertagsnotizen je Datum.
        include_end_even_if_not_weekday: Fuegt eine Zeile am Tag ``end``
            ein, falls die normale Generierung fuer ``end`` keine Zeile
            erzeugt hat. Diese Abschlusszeile traegt immer einen
            Ferien-Marker (Grund aus ``events``, ersatzweise
            ``Ferienbeginn``) und ist keine Unterrichtsstunde: Der einzige
            Aufrufer (Uebernahme-/Verlaengern-Modus in
            :func:`create_plan_result`) uebergibt als ``end`` den ersten
            Ferientag. Ferienzeilen haben in ``DayColumn.stunden()`` stets
            0 Stunden, auch wenn der Rhythmus an diesem Datum eine Stunde
            kennt. "weekday" im Namen meint historisch "Unterrichtstag".
    """
    rows: list[PlanRow] = []
    current = start

    while current <= end:
        if is_teaching_day(rhythm, current):
            note = events.get(current, "")
            # Calendar events are loaded only from Ferien/Feiertag sources.
            # Therefore, any event note marks a non-teaching day (Ferien/Feiertag).
            is_outage = bool(note)
            rows.append((current, build_ferien_marker(note) if is_outage else ""))
        current += timedelta(days=1)

    if include_end_even_if_not_weekday and not any(row_date == end for row_date, _ in rows):
        note = build_ferien_marker(events.get(end, "Ferienbeginn"))
        rows.append((end, note))
        rows.sort(key=lambda item: item[0])

    return rows


def infer_term_from_ferien_blocks(start_date: date, ferien_blocks: list[PlanCalendarEvent]) -> str:
    """Bestimmt das Halbjahrestoken rein datenbasiert aus Ferienblöcken.

    Wenn kein exakter Treffer vorliegt, wird über die Monatslage auf Winter/Sommer
    zurückgefallen.
    """
    if not ferien_blocks:
        raise RuntimeError("Keine Ferienblöcke zur Halbjahres-Berechnung gefunden.")

    candidate_years = [start_date.year - 1, start_date.year, start_date.year + 1]
    for year in candidate_years:
        for half in ("1", "2"):
            term = f"{str(year)[-2:]}-{half}"
            try:
                start, end = determine_term_range(term, ferien_blocks)
            except RuntimeError:
                continue
            if start <= start_date <= end:
                return term

    if 2 <= start_date.month <= 7:
        return f"{str(start_date.year)[-2:]}-1"
    return f"{str(start_date.year)[-2:]}-2"


def create_plan_result(
    term: str | None,
    rhythm: tuple[WeekdayRhythm, ...],
    events: dict[date, str],
    blocks: list[PlanCalendarEvent],
    warnings: list[str],
    takeover_start: date | None = None,
    stop_at_next_break: bool = False,
    vacation_break_horizon: int = 1,
) -> tuple[list[PlanRow], PlanResult]:
    """Erzeugt Planzeilen und fachliches Ergebnisobjekt für den gewünschten Modus.

    Unterstützt Halbjahres- und Übernahme-Modus (bis nächste Ferienphase).
    ``rhythm`` ist der vollständige Rhythmus mit allen Segmenten (siehe
    Vertrag von :func:`generate_rows`). Liefert nur fachliche
    Datenstrukturen, keine Persistenz-Nebenwirkungen.
    """
    ferien_blocks = [item for item in blocks if "ferien" in item[0].lower()]
    if not ferien_blocks:
        raise RuntimeError("Keine Ferienblöcke in den Kalenderdaten gefunden.")

    if not active_weekdays(rhythm):
        raise RuntimeError("Rhythmus enthält keine aktiven Unterrichtstage.")

    if stop_at_next_break:
        if takeover_start is None:
            raise RuntimeError("Für den Übernahme-Modus wird ein Startdatum benötigt.")
        start = takeover_start
        end = find_vacation_start_with_horizon(takeover_start, ferien_blocks, vacation_break_horizon)
        rows = generate_rows(
            start,
            end,
            rhythm,
            events,
            include_end_even_if_not_weekday=True,
        )
    else:
        if not term:
            raise RuntimeError("Für Halbjahres-Modus ist ein Halbjahr erforderlich.")

        start, end = determine_term_range(term, ferien_blocks)
        if takeover_start and takeover_start > start:
            start = takeover_start
        rows = generate_rows(start, end, rhythm, events)

    if not rows:
        raise RuntimeError("Terminplan lieferte keine Termine.")

    return rows, PlanResult(
        rows_count=len(rows),
        range_start=start,
        range_end=end,
        warnings=warnings,
    )
