"""Wochentags-Rhythmus (Startzeit + Stundenzahl) einer Plan-Datei.

Der Rhythmus ist ein kursweites YAML-Feld (``Rhythmus``, siehe
:data:`RHYTHM_YAML_KEY`) und ersetzt den fruehren, ausschliesslich transient
im Dialog gehaltenen Wochentag->Stunden-Rhythmus. Er ist die einzige Quelle
der Wahrheit fuer die Stundenzahl und Startzeit eines Kalendertags; die
Plantabelle selbst traegt dafuer keine eigene Spalte mehr.

Format je Zeile::

    ["ab" <DD-MM-YY>] <Wochentag> <HH:MM> <Stunden>

``ab <Datum>`` ist optional und markiert den Beginn eines neuen Segments
(z. B. nach einer Stundenplanaenderung); Eintraege ohne ``ab`` bilden das
Basis-Segment, das seit Kursbeginn gilt.

Ganz-Segment-Regel: Ein ``ab``-Segment beschreibt den vollstaendigen Rhythmus
ab diesem Datum. Nicht aufgefuehrte Wochentage entfallen. Fuer ein konkretes
Datum gilt stets genau das Segment mit dem spaetesten ``valid_from``, das
nicht nach diesem Datum liegt (siehe :func:`current_segment`). Eine fruehere
Fassung loeste Segmente je Wochentag auf - dadurch blieben bei einem Wechsel
von ``Mo, Do`` auf ``ab X Di`` nach X faelschlich ``Mo, Di, Do`` aktiv.

Invarianten (geprueft von :func:`validate_rhythm`):

- Es gibt ein Basis-Segment (mindestens einen Eintrag ohne ``ab``). Ohne
  Basis waere die Zeit vor dem ersten ``ab`` undefiniert.
- Je Segment hat jeder Wochentag hoechstens einen Eintrag.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

WEEKDAY_TOKENS: tuple[str, ...] = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
RHYTHM_YAML_KEY = "Rhythmus"

RHYTHM_ENTRY_RE = re.compile(
    r"^(?:ab\s+(?P<valid_from>\d{2}-\d{2}-\d{2})\s+)?"
    r"(?P<weekday>Mo|Di|Mi|Do|Fr|Sa|So)\s+"
    r"(?P<time>\d{2}:\d{2})\s+"
    r"(?P<hours>\d{1,2})$"
)


@dataclass(frozen=True)
class WeekdayRhythm:
    """Ein einzelner Rhythmus-Eintrag: Wochentag, Startzeit, Stundenzahl.

    Args:
        weekday: Wochentag als Index (0=Montag ... 6=Sonntag).
        start_time: Startzeit im Format ``HH:MM``.
        hours: Stundenzahl an diesem Wochentag (1-4).
        valid_from: Erster Geltungstag dieses Eintrags, oder ``None`` fuer
            "seit Kursbeginn gueltig".
    """

    weekday: int
    start_time: str
    hours: int
    valid_from: date | None = None


def weekday_token(weekday: int) -> str:
    """Liefert das zweibuchstabige Kuerzel eines Wochentag-Index (0=Mo).

    Example::

        weekday_token(3)
        # -> "Do"
    """
    if not 0 <= weekday <= 6:
        raise ValueError(f"Wochentag-Index ausserhalb 0..6: {weekday}")
    return WEEKDAY_TOKENS[weekday]


def weekday_from_token(token: str) -> int:
    """Liefert den Wochentag-Index (0=Mo) eines zweibuchstabigen Kuerzels.

    Example::

        weekday_from_token("Do")
        # -> 3
    """
    try:
        return WEEKDAY_TOKENS.index(token)
    except ValueError as exc:
        raise ValueError(f"Unbekannter Wochentag-Token: '{token}'.") from exc


def parse_rhythm_entry(text: str) -> WeekdayRhythm:
    """Parst eine einzelne Rhythmus-Zeile in einen :class:`WeekdayRhythm`.

    Args:
        text: Eine Zeile im Format ``["ab" DD-MM-YY] Wochentag HH:MM Stunden``.

    Returns:
        Der geparste Eintrag.

    Raises:
        ValueError: Wenn Format, Startzeit oder Stundenzahl ungueltig sind.

    Example::

        parse_rhythm_entry("Mo 12:15 2")
        # -> WeekdayRhythm(weekday=0, start_time="12:15", hours=2, valid_from=None)
    """
    raw = str(text or "").strip()
    match = RHYTHM_ENTRY_RE.match(raw)
    if match is None:
        raise ValueError(
            f"Ungueltiger Rhythmus-Eintrag: '{raw}'. Erwartet: "
            "'[ab DD-MM-YY] Wochentag HH:MM Stunden', z. B. 'Mo 12:15 2'."
        )

    weekday = weekday_from_token(match.group("weekday"))

    time_text = match.group("time")
    try:
        datetime.strptime(time_text, "%H:%M")
    except ValueError as exc:
        raise ValueError(f"Ungueltige Startzeit im Rhythmus-Eintrag: '{time_text}'. Erwartet HH:MM.") from exc

    hours = int(match.group("hours"))
    if hours < 1 or hours > 4:
        raise ValueError(f"Stundenzahl im Rhythmus-Eintrag muss zwischen 1 und 4 liegen: '{raw}'.")

    valid_from_text = match.group("valid_from")
    valid_from = datetime.strptime(valid_from_text, "%d-%m-%y").date() if valid_from_text else None

    return WeekdayRhythm(weekday=weekday, start_time=time_text, hours=hours, valid_from=valid_from)


def parse_rhythm(value: object) -> tuple[WeekdayRhythm, ...]:
    """Parst den rohen YAML-Wert des ``Rhythmus``-Felds in Rhythmus-Eintraege.

    Akzeptiert sowohl eine einzelne Zeichenkette (Einzeleintrag) als auch eine
    Liste von Zeichenketten (Normalfall bei mehreren Eintraegen), da
    ``parse_yaml_frontmatter`` ein einzeiliges Feld als Scalar statt Liste
    zurueckgibt.

    Args:
        value: Rohwert aus ``PlanTableData.metadata["Rhythmus"]``.

    Returns:
        Geparste Rhythmus-Eintraege, unsortiert in Eingabereihenfolge.

    Raises:
        ValueError: Wenn ein Eintrag ungueltig ist, ``value`` weder
            Zeichenkette noch Liste ist oder die Invarianten von
            :func:`validate_rhythm` verletzt sind.
    """
    if value is None:
        return ()
    if isinstance(value, str):
        raw_items = [value] if value.strip() else []
    elif isinstance(value, list):
        raw_items = [str(item) for item in value]
    else:
        raise ValueError(f"Unerwarteter Rhythmus-Werttyp: {type(value)!r}")

    entries = tuple(parse_rhythm_entry(item) for item in raw_items)
    validate_rhythm(entries)
    return entries


def format_rhythm(entries: tuple[WeekdayRhythm, ...]) -> list[str]:
    """Formatiert Rhythmus-Eintraege kanonisch (sortiert nach Segment, Wochentag).

    Example::

        format_rhythm((WeekdayRhythm(weekday=3, start_time="07:50", hours=2),))
        # -> ["Do 07:50 2"]
    """
    ordered = sorted(entries, key=_sort_key)
    lines: list[str] = []
    for entry in ordered:
        base = f"{weekday_token(entry.weekday)} {entry.start_time} {entry.hours}"
        if entry.valid_from is not None:
            lines.append(f"ab {entry.valid_from.strftime('%d-%m-%y')} {base}")
        else:
            lines.append(base)
    return lines


def is_valid_rhythm_value(value: object) -> bool:
    """Prueft, ob ein roher YAML-Wert ein gueltiges, nicht-leeres Rhythmus-Feld ist.

    Fuer die Verwendung als ``value_validators``-Eintrag in
    :data:`kursplaner.core.domain.yaml_registry.PLAN_METADATA_SCHEMA`.
    """
    try:
        entries = parse_rhythm(value)
    except ValueError:
        return False
    return len(entries) > 0


def _sort_key(entry: WeekdayRhythm) -> tuple[date, int]:
    """Kanonischer Sortierschluessel: Segmentbeginn, dann Wochentag.

    ``valid_from=None`` (Basis-Segment) zaehlt als ``date.min`` - ``None``
    wird so nie direkt mit einem ``date`` verglichen.
    """
    return (entry.valid_from or date.min, entry.weekday)


def validate_rhythm(entries: tuple[WeekdayRhythm, ...]) -> None:
    """Prueft die Rhythmus-Invarianten ueber alle Segmente.

    Oeffentlich, weil neben :func:`parse_rhythm` auch die Eingabe-Validierung
    (``validators.normalize_day_rhythm``) und das Zusammenfuegen von
    Segmenten dieselben Regeln brauchen.

    Raises:
        ValueError: Wenn kein Basis-Segment existiert oder ein Wochentag
            innerhalb eines Segments mehrfach vorkommt.
    """
    if entries and all(entry.valid_from is not None for entry in entries):
        raise ValueError(
            "Rhythmus braucht mindestens einen Eintrag ohne 'ab <Datum>' (Basis-Rhythmus seit Kursbeginn)."
        )
    seen: set[tuple[date, int]] = set()
    for entry in entries:
        key = _sort_key(entry)
        if key in seen:
            segment = "Basis" if entry.valid_from is None else f"ab {entry.valid_from.strftime('%d-%m-%y')}"
            raise ValueError(f"Wochentag '{weekday_token(entry.weekday)}' mehrfach im Segment '{segment}'.")
        seen.add(key)


def segment_start(entries: tuple[WeekdayRhythm, ...], on: date) -> date | None:
    """Liefert den Beginn (``valid_from or date.min``) des am Datum ``on`` gueltigen Segments.

    ``None``, wenn kein Segment greift (nur moeglich ohne Basis-Segment,
    das :func:`validate_rhythm` fuer gueltige Rhythmen ausschliesst).
    """
    starts = [entry.valid_from or date.min for entry in entries]
    eligible = [start for start in starts if start <= on]
    return max(eligible) if eligible else None


def current_segment(entries: tuple[WeekdayRhythm, ...], on: date) -> tuple[WeekdayRhythm, ...]:
    """Liefert das vollstaendige, zum Datum ``on`` gueltige Rhythmus-Segment.

    Ganz-Segment-Regel (siehe Modul-Docstring): Es gewinnt das Segment mit
    dem spaetesten ``valid_from``, das nicht nach ``on`` liegt; zurueckgegeben
    werden genau dessen Eintraege. Wochentage frueherer Segmente, die im
    gueltigen Segment fehlen, sind an ``on`` kein Unterrichtstag.

    Args:
        entries: Alle Rhythmus-Eintraege eines Kurses (ueber alle Segmente).
        on: Referenzdatum.

    Returns:
        Die Eintraege des gueltigen Segments, kanonisch sortiert.

    Example::

        entries = parse_rhythm(["Mo 08:00 2", "Do 07:50 2", "ab 20-04-26 Di 10:00 2"])
        current_segment(entries, date(2026, 5, 1))
        # -> (WeekdayRhythm(weekday=1, ..., valid_from=date(2026, 4, 20)),)
    """
    start = segment_start(entries, on)
    if start is None:
        return ()
    active = [entry for entry in entries if (entry.valid_from or date.min) == start]
    return tuple(sorted(active, key=_sort_key))


def rhythm_for_date(entries: tuple[WeekdayRhythm, ...], day: date) -> WeekdayRhythm | None:
    """Liefert den fuer einen konkreten Kalendertag gueltigen Rhythmus-Eintrag.

    ``None``, wenn an diesem Wochentag zum gegebenen Datum kein Unterricht
    stattfindet (kein passendes Segment vorhanden).
    """
    for entry in current_segment(entries, day):
        if entry.weekday == day.weekday():
            return entry
    return None


def hours_for_date(entries: tuple[WeekdayRhythm, ...], day: date) -> int:
    """Liefert die Stundenzahl eines Kalendertags aus dem Rhythmus, ``0`` falls kein Unterrichtstag."""
    entry = rhythm_for_date(entries, day)
    return entry.hours if entry is not None else 0


def start_time_for_date(entries: tuple[WeekdayRhythm, ...], day: date) -> str:
    """Liefert die Startzeit eines Kalendertags aus dem Rhythmus, leer falls kein Unterrichtstag."""
    entry = rhythm_for_date(entries, day)
    return entry.start_time if entry is not None else ""


def active_weekdays(entries: tuple[WeekdayRhythm, ...]) -> set[int]:
    """Liefert die Menge der in den uebergebenen Eintraegen vertretenen Wochentage.

    Nimmt die Eintraege wie uebergeben (kein Segment-Filtering) - Aufrufer, die
    nur das aktuell wirksame Segment wollen, filtern vorher ueber
    :func:`current_segment`.
    """
    return {entry.weekday for entry in entries}


def add_segment(
    entries: tuple[WeekdayRhythm, ...], new_segment: tuple[WeekdayRhythm, ...]
) -> tuple[WeekdayRhythm, ...]:
    """Ergaenzt bestehende Rhythmus-Eintraege um ein neues, datiertes Segment.

    Bestehende Eintraege (fruehere Segmente) bleiben unveraendert erhalten,
    damit vergangene Zeilen ihre historisch korrekte Stundenzahl/Startzeit
    behalten. ``new_segment`` muss nach der Ganz-Segment-Regel den
    vollstaendigen Rhythmus ab seinem ``valid_from`` enthalten.
    """
    return tuple(entries) + tuple(new_segment)


def parse_lesson_hours(raw: object) -> int:
    """Parst die aus dem Rhythmus abgeleitete Stundenzahl einer Planzeile.

    Konsolidiert die zuvor an mehreren Stellen duplizierte Parsing-Logik für
    ``day["stunden"]``-Rohwerte. Anders als eine frühere Fassung dieser
    Funktion liefert sie **keinen stillen Default** mehr: seit ``Rhythmus``
    einzige Quelle der Wahrheit für die Stundenzahl ist, hat jede Zeile mit
    gültigem Datum immer eine daraus abgeleitete Stundenzahl (auch ``0`` für
    Ferien-/Nicht-Unterrichtstage); ein leerer/ungültiger Wert bedeutet daher
    ausschließlich ein nicht parsbares Zeilendatum - ein echter Fehlerfall,
    kein Normalzustand, der einen erfundenen Default rechtfertigen würde.

    Args:
        raw: Rohwert aus ``day["stunden"]`` (siehe
            :meth:`kursplaner.core.usecases.load_plan_detail_usecase.
            LoadPlanDetailUseCase.build_day_columns`).

    Returns:
        Die geparste Stundenzahl.

    Raises:
        ValueError: Wenn ``raw`` keine gültige nicht-negative Ganzzahl ist.
    """
    text = str(raw or "").strip()
    if not text.isdigit():
        raise ValueError(f"Keine gültige Stundenzahl ableitbar: {raw!r} (Zeilendatum vermutlich ungültig).")
    return int(text)
