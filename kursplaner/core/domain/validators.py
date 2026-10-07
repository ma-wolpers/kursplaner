import re
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

from kursplaner.core.config.path_store import resolve_path_value
from kursplaner.core.config.settings import WEEKDAY_MAP
from kursplaner.core.domain.course_rhythm import WeekdayRhythm, validate_rhythm
from kursplaner.core.domain.course_subject import short_subject_for_course_subject


class ValidationError(ValueError):
    """Kennzeichnet Fehlerzustände über Validation Error.

    Die Klasse macht fachlich erwartbare Validierungsprobleme als eigenen Fehlertyp unterscheidbar.
    """

    pass


def normalize_subject(subject_raw: str) -> str:
    """Normalisiert Kursfach strikt auf das im System verwendete Kurzformat.

    Leere Eingaben sind unzulässig und führen zu ``ValidationError``.
    """
    clean = subject_raw.strip()
    if not clean:
        raise ValidationError("Kursfach darf nicht leer sein.")

    try:
        return short_subject_for_course_subject(clean)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


def normalize_group(group_raw: str) -> str:
    """Normalisiert den Lerngruppen-Namen für Ordner-/Dateinutzung."""
    clean = re.sub(r"\s+", " ", group_raw.strip())
    if not clean:
        raise ValidationError("Lerngruppe darf nicht leer sein.")

    clean = clean.replace(" ", "-")
    if any(char in clean for char in "\\/"):
        raise ValidationError("Lerngruppe darf keine / oder \\ enthalten.")
    return clean


def normalize_grade_level(raw: str) -> int:
    """Validiert und normalisiert die Jahrgangsstufe auf einen Integer von 1 bis 13."""
    value = raw.strip()
    if not value.isdigit():
        raise ValidationError("Stufe muss eine Zahl zwischen 1 und 13 sein.")

    grade = int(value)
    if grade < 1 or grade > 13:
        raise ValidationError("Stufe muss eine Zahl zwischen 1 und 13 sein.")
    return grade


def normalize_weekdays(labels: list[str]) -> list[int]:
    """Übersetzt Wochentagslabels in eindeutige, sortierte Integer-Wochentage."""
    if not labels:
        raise ValidationError("Bitte mindestens einen Wochentag auswählen.")

    numbers = []
    for label in labels:
        key = label.strip().lower()
        if key not in WEEKDAY_MAP:
            raise ValidationError(f"Unbekannter Wochentag: {label}")
        numbers.append(WEEKDAY_MAP[key])

    return sorted(set(numbers))


def normalize_day_rhythm(
    entries: dict[tuple[int, int | None], tuple[str, str]], *, valid_from: date | None = None
) -> tuple[WeekdayRhythm, ...]:
    """Validiert Startzeit-/Stundenangaben je Wochentag und Woche und baut Rhythmus-Eintraege.

    Args:
        entries: Rohe Formulareingaben als
            ``{(weekday, week_parity): (start_time_raw, hours_raw)}``.
            ``week_parity`` ist ``None`` (jede Woche), ``0`` (gerade KW,
            ``gKW``) oder ``1`` (ungerade KW, ``uKW``); ein A/B-Tag liefert
            zwei Schluessel ``(wd, 0)`` und ``(wd, 1)``. Die Tupel-Schluessel
            sind bewusst eine reine Boundary-Struktur zwischen Picker/CLI und
            Validator. Eintraege mit leerer Startzeit UND leerer
            Stundenangabe werden als deaktiviert uebersprungen.
        valid_from: Optionales Gueltig-ab-Datum fuer alle erzeugten Eintraege
            (z. B. bei einer Stundenplanaenderung ab einem Stichtag).

    Returns:
        Nach Wochentag und Paritaet sortierte Rhythmus-Eintraege.

    Raises:
        ValidationError: Bei ungueltiger Stundenzahl oder Startzeit, wenn
            kein Unterrichtstag angegeben wurde oder sich Eintraege eines
            Wochentags ueberschneiden (z. B. "jede Woche" und ``gKW``).

    Example::

        normalize_day_rhythm({(0, 0): ("08:00", "2"), (0, 1): ("11:30", "1")})
        # -> Mo 08:00 2 gKW, Mo 11:30 1 uKW
    """
    selected: list[WeekdayRhythm] = []
    for (weekday, week_parity), (start_raw, hours_raw) in entries.items():
        start_value = start_raw.strip()
        hours_value = hours_raw.strip()
        if not start_value and not hours_value:
            continue

        if not hours_value.isdigit():
            raise ValidationError("Stundenzahl muss zwischen 1 und 4 liegen.")
        hours = int(hours_value)
        if hours < 1 or hours > 4:
            raise ValidationError("Stundenzahl muss zwischen 1 und 4 liegen.")

        try:
            datetime.strptime(start_value, "%H:%M")
        except ValueError as exc:
            raise ValidationError("Startzeit muss im Format HH:MM angegeben werden.") from exc

        selected.append(
            WeekdayRhythm(
                weekday=weekday,
                start_time=start_value,
                hours=hours,
                valid_from=valid_from,
                week_parity=week_parity,
            )
        )

    if not selected:
        raise ValidationError("Bitte mindestens einen Unterrichtstag mit Startzeit und Stunden angeben.")

    try:
        # Geprueft wird nur die Ueberschneidungsregel: Ein Segment mit
        # valid_from ist fuer sich allein keine Basis, deshalb ohne valid_from.
        validate_rhythm(tuple(replace(entry, valid_from=None) for entry in selected))
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return tuple(
        sorted(selected, key=lambda entry: (entry.weekday, -1 if entry.week_parity is None else entry.week_parity))
    )


def normalize_base_dir(path_raw: str) -> Path:
    """Normalisiert den Unterrichts-Basisordner auf einen aufgelösten Pfad."""
    return resolve_path_value(path_raw)


def normalize_calendar_dir(path_raw: str) -> Path:
    """Normalisiert den Kalenderordner auf einen aufgelösten Pfad."""
    return resolve_path_value(path_raw)


def normalize_optional_start_date(value: str) -> date | None:
    """Parst ein optionales Startdatum aus erlaubten Benutzerformaten."""
    raw = value.strip()
    if not raw:
        return None

    patterns = ["%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%d.%m.%y", "%d-%m-%y"]
    for pattern in patterns:
        try:
            return datetime.strptime(raw, pattern).date()
        except ValueError:
            continue

    raise ValidationError("Startdatum ungültig. Erlaubt: YYYY-MM-DD, DD.MM.YYYY, DD-MM-YYYY.")


def parse_period_input(value: str) -> tuple[str | None, date | None, bool]:
    """Interpretation der Perioden-Eingabe als Halbjahr oder Startdatum.

    Rückgabe: ``(term, start_date, is_date_mode)``.
    """
    raw = value.strip().lower()
    if not raw:
        raise ValidationError("Bitte Halbjahr oder Startdatum eingeben.")

    if re.fullmatch(r"\d{2}-[12]", raw):
        return raw, None, False

    date_value = normalize_optional_start_date(raw)
    if date_value is None:
        raise ValidationError("Bitte gueltiges Halbjahr (z. B. 26-1/26-2) oder ein Startdatum angeben.")

    return None, date_value, True
