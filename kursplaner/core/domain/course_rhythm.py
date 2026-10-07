"""Wochentags-Rhythmus (Startzeit + Stundenzahl) einer Plan-Datei.

Der Rhythmus ist ein kursweites YAML-Feld (``Rhythmus``, siehe
:data:`RHYTHM_YAML_KEY`) und ersetzt den fruehren, ausschliesslich transient
im Dialog gehaltenen Wochentag->Stunden-Rhythmus. Er ist die einzige Quelle
der Wahrheit fuer die Stundenzahl und Startzeit eines Kalendertags; die
Plantabelle selbst traegt dafuer keine eigene Spalte mehr.

Format je Zeile::

    ["ab" <DD-MM-YY>] <Wochentag> <HH:MM> <Stunden> ["gKW" | "uKW"]

Das optionale Kuerzel am Zeilenende beschraenkt den Eintrag auf gerade
(``gKW``) bzw. ungerade (``uKW``) ISO-Kalenderwochen
(``date.isocalendar().week % 2``); ohne Kuerzel gilt er jede Woche. Die
Paritaet folgt strikt der ISO-Regel: In Jahren mit KW 53 folgen zwei
ungerade Wochen aufeinander (z. B. KW 53/2026 und KW 1/2027). Einziger Ort,
der die Paritaet gegen ein Datum prueft, ist :func:`entry_applies_on`.

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
- Je Segment hat jeder Wochentag entweder genau einen Eintrag ohne Kuerzel
  oder hoechstens je einen ``gKW``- und ``uKW``-Eintrag (A/B-Woche).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta

WEEKDAY_TOKENS: tuple[str, ...] = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
RHYTHM_YAML_KEY = "Rhythmus"
PARITY_TOKENS: dict[int, str] = {0: "gKW", 1: "uKW"}

RHYTHM_ENTRY_RE = re.compile(
    r"^(?:ab\s+(?P<valid_from>\d{2}-\d{2}-\d{2})\s+)?"
    r"(?P<weekday>Mo|Di|Mi|Do|Fr|Sa|So)\s+"
    r"(?P<time>\d{2}:\d{2})\s+"
    r"(?P<hours>\d{1,2})"
    r"(?:\s+(?P<parity>gKW|uKW))?$"
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
        week_parity: ``0`` = nur gerade KW (``gKW``), ``1`` = nur ungerade
            KW (``uKW``), ``None`` = jede Woche.

    Raises:
        ValueError: Bei Wochentag ausserhalb ``0..6`` oder unbekannter
            Paritaet. Die Pruefung sitzt im Typ selbst, weil Eintraege auch
            ausserhalb des Parsers gebaut werden (Eingabe-Validierung,
            Migrationstool, ``dataclasses.replace``).
    """

    weekday: int
    start_time: str
    hours: int
    valid_from: date | None = None
    week_parity: int | None = None

    def __post_init__(self) -> None:
        """Erzwingt Wochentag ``0..6`` und Paritaet ``None | 0 | 1``."""
        if not 0 <= self.weekday <= 6:
            raise ValueError(f"Wochentag-Index ausserhalb 0..6: {self.weekday}")
        if self.week_parity not in (None, 0, 1):
            raise ValueError(f"Unbekannte Wochenparitaet: {self.week_parity!r} (erlaubt: None, 0, 1).")


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


def parity_token(week_parity: int) -> str:
    """Liefert das md-Kuerzel einer Wochenparitaet.

    Example::

        parity_token(0)
        # -> "gKW"
    """
    try:
        return PARITY_TOKENS[week_parity]
    except KeyError as exc:
        raise ValueError(f"Unbekannte Wochenparitaet: {week_parity!r}") from exc


def parity_from_token(token: str) -> int:
    """Liefert die Wochenparitaet (0 = gerade, 1 = ungerade) eines md-Kuerzels.

    Example::

        parity_from_token("uKW")
        # -> 1
    """
    for parity, known in PARITY_TOKENS.items():
        if known == token:
            return parity
    raise ValueError(f"Unbekanntes Wochen-Kuerzel: '{token}' (erlaubt: gKW, uKW).")


def parse_rhythm_entry(text: str) -> WeekdayRhythm:
    """Parst eine einzelne Rhythmus-Zeile in einen :class:`WeekdayRhythm`.

    Args:
        text: Eine Zeile im Format
            ``["ab" DD-MM-YY] Wochentag HH:MM Stunden ["gKW"|"uKW"]``.

    Returns:
        Der geparste Eintrag.

    Raises:
        ValueError: Wenn Format, Startzeit oder Stundenzahl ungueltig sind.

    Example::

        parse_rhythm_entry("Mo 12:15 2")
        # -> WeekdayRhythm(weekday=0, start_time="12:15", hours=2, valid_from=None)
        parse_rhythm_entry("ab 20-04-26 Do 07:50 1 uKW").week_parity
        # -> 1
    """
    raw = str(text or "").strip()
    match = RHYTHM_ENTRY_RE.match(raw)
    if match is None:
        raise ValueError(
            f"Ungueltiger Rhythmus-Eintrag: '{raw}'. Erwartet: "
            "'[ab DD-MM-YY] Wochentag HH:MM Stunden [gKW|uKW]', z. B. 'Mo 12:15 2' oder 'Do 07:50 2 gKW'."
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

    parity_text = match.group("parity")
    week_parity = parity_from_token(parity_text) if parity_text else None

    return WeekdayRhythm(
        weekday=weekday, start_time=time_text, hours=hours, valid_from=valid_from, week_parity=week_parity
    )


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
    """Formatiert Rhythmus-Eintraege kanonisch (sortiert nach Segment, Wochentag, Paritaet).

    Example::

        format_rhythm((WeekdayRhythm(weekday=3, start_time="07:50", hours=2),))
        # -> ["Do 07:50 2"]
    """
    ordered = sorted(entries, key=_sort_key)
    lines: list[str] = []
    for entry in ordered:
        base = f"{weekday_token(entry.weekday)} {entry.start_time} {entry.hours}"
        if entry.week_parity is not None:
            base = f"{base} {parity_token(entry.week_parity)}"
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


def _sort_key(entry: WeekdayRhythm) -> tuple[date, int, int]:
    """Kanonischer Sortierschluessel: Segmentbeginn, Wochentag, Paritaet.

    ``valid_from=None`` (Basis-Segment) zaehlt als ``date.min`` - ``None``
    wird so nie direkt mit einem ``date`` verglichen. Bei gleichem Wochentag
    kommt "jede Woche" (``-1``) vor ``gKW`` (0) vor ``uKW`` (1).
    """
    parity_rank = -1 if entry.week_parity is None else entry.week_parity
    return (entry.valid_from or date.min, entry.weekday, parity_rank)


def validate_rhythm(entries: tuple[WeekdayRhythm, ...]) -> None:
    """Prueft die Rhythmus-Invarianten ueber alle Segmente.

    Oeffentlich, weil neben :func:`parse_rhythm` auch die Eingabe-Validierung
    (``validators.normalize_day_rhythm``) und das Zusammenfuegen von
    Segmenten dieselben Regeln brauchen.

    Raises:
        ValueError: Wenn kein Basis-Segment existiert oder ein Wochentag
            innerhalb eines Segments sich ueberschneidende Eintraege hat
            (doppelt, oder "jede Woche" zusammen mit ``gKW``/``uKW``).
    """
    if entries and all(entry.valid_from is not None for entry in entries):
        raise ValueError(
            "Rhythmus braucht mindestens einen Eintrag ohne 'ab <Datum>' (Basis-Rhythmus seit Kursbeginn)."
        )
    parities_by_day: dict[tuple[date, int], list[int | None]] = {}
    for entry in entries:
        parities_by_day.setdefault((entry.valid_from or date.min, entry.weekday), []).append(entry.week_parity)
    for (start, weekday), parities in parities_by_day.items():
        overlapping = len(parities) != len(set(parities)) or (None in parities and len(parities) > 1)
        if overlapping:
            segment = "Basis" if start == date.min else f"ab {start.strftime('%d-%m-%y')}"
            raise ValueError(
                f"Wochentag '{weekday_token(weekday)}' mehrfach im Segment '{segment}' "
                "(erlaubt: ein Eintrag ohne Kuerzel oder je einer mit gKW/uKW)."
            )


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


def entry_applies_on(entry: WeekdayRhythm, day: date) -> bool:
    """Prueft, ob ein Eintrag nach Wochentag und KW-Paritaet auf ``day`` passt.

    Einzige Stelle, die ``week_parity`` gegen ein Datum prueft; das
    Segment (``valid_from``) beruecksichtigt :func:`current_segment`.

    Example::

        entry = parse_rhythm_entry("Mo 08:00 2 gKW")
        entry_applies_on(entry, date(2026, 10, 12))  # Mo, KW 42
        # -> True
        entry_applies_on(entry, date(2026, 10, 5))  # Mo, KW 41
        # -> False
    """
    if entry.weekday != day.weekday():
        return False
    return entry.week_parity is None or day.isocalendar().week % 2 == entry.week_parity


def rhythm_for_date(entries: tuple[WeekdayRhythm, ...], day: date) -> WeekdayRhythm | None:
    """Liefert den fuer einen konkreten Kalendertag gueltigen Rhythmus-Eintrag.

    ``None``, wenn an diesem Tag kein Unterricht stattfindet (Wochentag nicht
    im gueltigen Segment oder falsche KW-Paritaet). Wegen der Invarianten
    aus :func:`validate_rhythm` passt hoechstens ein Eintrag.
    """
    for entry in current_segment(entries, day):
        if entry_applies_on(entry, day):
            return entry
    return None


def is_teaching_day(entries: tuple[WeekdayRhythm, ...], day: date) -> bool:
    """Prueft, ob laut Rhythmus (Segment, Wochentag, KW-Paritaet) an ``day`` Unterricht ist."""
    return rhythm_for_date(entries, day) is not None


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


def splice_segment(
    existing: tuple[WeekdayRhythm, ...],
    new_segment: tuple[WeekdayRhythm, ...],
    *,
    date_from: date,
    date_to: date,
    has_row_before: bool,
    has_row_after: bool,
) -> tuple[WeekdayRhythm, ...]:
    """Fuegt das Rhythmus-Segment einer Stundenplanaenderung in den Bestand ein.

    Reine Funktion; arbeitet in fester Reihenfolge, damit kein Schritt einen
    bereits veraenderten Bestand liest:

    1. **Rueckkehr-Rhythmus aus dem unveraenderten ``existing``:** Gibt es
       nach ``date_to`` noch eine Planzeile (``has_row_after``) und beginnt
       in ``existing`` nicht ohnehin ein Segment am Folgetag, wird der dort
       ohne die Aenderung gueltige Rhythmus als Segment ``ab date_to+1``
       wieder eingetragen. Das geschieht zuerst, damit der temporaere
       Rhythmus nie als Rueckkehr-Rhythmus erscheint.
    2. **Ueberdeckte Segmente entfernen:** Segmente mit Beginn in
       ``[date_from, date_to]`` wuerden das neue Segment ueberstimmen. Ohne
       Planzeile vor ``date_from`` (Ersatz-Zweig) faellt der gesamte Bestand
       bis ``date_to`` weg, auch Basis und aeltere ``ab``-Segmente.
       Spaetere Segmente bleiben.
    3. **Neues Segment einsetzen:** im Ersatz-Zweig ohne ``valid_from`` (es
       wird zur Basis), sonst ab ``date_from``.
    4. **Zusammensetzen und kanonisch sortieren.**
    5. **Pruefen** mit :func:`validate_rhythm` (Absicherung gegen Logikfehler).

    Args:
        existing: Bisheriger, gueltiger Rhythmus (alle Segmente).
        new_segment: Vollstaendiger neuer Rhythmus fuer den Aenderungsbereich.
        date_from: Erster Tag des Aenderungsbereichs.
        date_to: Letzter Tag des Aenderungsbereichs.
        has_row_before: Es gibt eine datierte Planzeile vor ``date_from``.
        has_row_after: Es gibt eine datierte Planzeile nach ``date_to``
            (Unterricht, Ferien oder Ausfall; datumslose Slots zaehlen nicht).

    Returns:
        Der zusammengefuegte Rhythmus, kanonisch sortiert.

    Example::

        existing = parse_rhythm(["Mo 08:00 2"])
        splice_segment(existing, parse_rhythm(["Di 10:00 1"]), date_from=date(2026, 3, 2),
                       date_to=date(2026, 3, 13), has_row_before=True, has_row_after=True)
        # -> Mo (Basis), Di ab 02.03., Mo ab 14.03. (Rueckkehr)
    """
    return_at = date_to + timedelta(days=1)
    restore: tuple[WeekdayRhythm, ...] = ()
    if has_row_after and segment_start(existing, return_at) != return_at:
        restore = tuple(replace(entry, valid_from=return_at) for entry in current_segment(existing, return_at))

    lower = date_from if has_row_before else date.min
    kept = tuple(entry for entry in existing if not lower <= (entry.valid_from or date.min) <= date_to)

    new_valid_from = date_from if has_row_before else None
    inserted = tuple(replace(entry, valid_from=new_valid_from) for entry in new_segment)

    result = tuple(sorted(kept + inserted + restore, key=_sort_key))
    validate_rhythm(result)
    return result


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
