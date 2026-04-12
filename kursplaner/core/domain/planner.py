from datetime import date, timedelta

from kursplaner.core.domain.models import PlanResult

PlanRow = tuple[date, int, str]
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
    day_hours: dict[int, int],
    events: dict[date, str],
    include_end_even_if_not_weekday: bool = False,
) -> list[PlanRow]:
    """Erzeugt fachliche Planzeilen im Bereich ``start`` bis ``end``.

    Pro konfiguriertem Wochentag wird eine Zeile erzeugt. Ferien/Feiertage werden
    als 0-Stunden-Tage markiert, bleiben aber als Datumseintrag sichtbar.
    """

    def format_outage_note(note: str) -> str:
        cleaned = note.strip()
        if not cleaned:
            return "X"
        if cleaned.lower().startswith("x ") or cleaned.lower() == "x":
            return cleaned
        return f"X {cleaned}"

    rows: list[PlanRow] = []
    current = start

    while current <= end:
        weekday = current.weekday()
        if weekday in day_hours:
            note = events.get(current, "")
            # Calendar events are loaded only from Ferien/Feiertag sources.
            # Therefore, any event note marks a non-teaching day (Ausfall).
            is_outage = bool(note)
            hours = 0 if is_outage else day_hours[weekday]
            if is_outage:
                note = format_outage_note(note)
            rows.append((current, hours, note))
        current += timedelta(days=1)

    if include_end_even_if_not_weekday and not any(row_date == end for row_date, _, _ in rows):
        note = format_outage_note(events.get(end, "Ferienbeginn"))
        rows.append((end, 0, note))
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
    day_hours: dict[int, int],
    events: dict[date, str],
    blocks: list[PlanCalendarEvent],
    warnings: list[str],
    takeover_start: date | None = None,
    stop_at_next_break: bool = False,
    vacation_break_horizon: int = 1,
) -> tuple[list[PlanRow], PlanResult]:
    """Erzeugt Planzeilen und fachliches Ergebnisobjekt für den gewünschten Modus.

    Unterstützt Halbjahres- und Übernahme-Modus (bis nächste Ferienphase).
    Liefert nur fachliche Datenstrukturen, keine Persistenz-Nebenwirkungen.
    """
    ferien_blocks = [item for item in blocks if "ferien" in item[0].lower()]
    if not ferien_blocks:
        raise RuntimeError("Keine Ferienblöcke in den Kalenderdaten gefunden.")

    if stop_at_next_break:
        if takeover_start is None:
            raise RuntimeError("Für den Übernahme-Modus wird ein Startdatum benötigt.")
        start = takeover_start
        end = find_vacation_start_with_horizon(takeover_start, ferien_blocks, vacation_break_horizon)
        rows = generate_rows(
            start,
            end,
            day_hours,
            events,
            include_end_even_if_not_weekday=True,
        )
    else:
        if not term:
            raise RuntimeError("Für Halbjahres-Modus ist ein Halbjahr erforderlich.")

        start, end = determine_term_range(term, ferien_blocks)
        if takeover_start and takeover_start > start:
            start = takeover_start
        rows = generate_rows(start, end, day_hours, events)

    if not rows:
        raise RuntimeError("Terminplan lieferte keine Termine.")

    return rows, PlanResult(
        rows_count=len(rows),
        range_start=start,
        range_end=end,
        warnings=warnings,
    )
