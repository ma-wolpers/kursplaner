from __future__ import annotations

from datetime import date, datetime, time

from kursplaner.core.domain.plan_table import sanitize_hour_title

UB_KIND_PAEDAGOGIK = "Pädagogik"
UB_KIND_FACH = "Fach"

UB_KIND_VALUES: tuple[str, ...] = (UB_KIND_PAEDAGOGIK, UB_KIND_FACH)

UB_OVERVIEW_FILE_NAME = "UB Übersicht.md"
UB_ROOT_RELATIVE_PARTS: tuple[str, ...] = ("7thVault", "🏫 Pädagogik", "00 Orga", "02 UBs")

UB_YAML_KEY_BEREICH = "Bereich"
UB_YAML_KEY_LANGENTWURF = "Langentwurf"
UB_YAML_KEY_BEOBACHTUNG = "Beobachtungsschwerpunkt"
UB_YAML_KEY_EINHEIT = "Einheit"


def normalize_ub_kinds(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Normalisiert UB-Kategorien auf eindeutige, kanonische Persistenzwerte."""
    resolved: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text not in UB_KIND_VALUES:
            raise ValueError("UB-Art ungueltig. Erlaubt sind nur Pädagogik und Fach.")
        if text not in resolved:
            resolved.append(text)

    if not resolved:
        raise ValueError("Mindestens eine UB-Art muss gesetzt sein.")

    return tuple(resolved)


def parse_ub_yy_mm_dd(date_text: str) -> str:
    """Konvertiert bekannte Eingabeformate in den UB-Datumstoken yy-mm-dd."""
    raw = str(date_text or "").strip()
    if not raw:
        return "00-00-00"

    for pattern in ("%Y-%m-%d", "%d-%m-%y", "%d-%m-%Y", "%d.%m.%y", "%d.%m.%Y"):
        try:
            parsed = datetime.strptime(raw, pattern)
            return parsed.strftime("%y-%m-%d")
        except ValueError:
            continue

    return "00-00-00"


def build_ub_stem(date_text: str, lesson_title: str) -> str:
    """Baut den kanonischen UB-Dateistamm UB yy-mm-dd Einheitstitel."""
    token = parse_ub_yy_mm_dd(date_text)
    title = sanitize_hour_title(lesson_title) or "Einheit"
    return f"UB {token} {title}".strip()


def parse_ub_date_from_stem(stem: str) -> date | None:
    """Liest das UB-Datum aus dem Dateistamm `UB yy-mm-dd ...` aus."""
    text = str(stem or "").strip()
    if not text.startswith("UB "):
        return None
    parts = text.split(" ", 2)
    if len(parts) < 3:
        return None
    token = str(parts[1]).strip()
    try:
        return datetime.strptime(token, "%y-%m-%d").date()
    except ValueError:
        return None


def ub_date_counts_as_past(
    ub_date: date,
    *,
    now: datetime | None = None,
    cutoff_hour: int = 15,
    cutoff_minute: int = 0,
) -> bool:
    """Bewertet ein UB-Datum als Vergangenheit mit Tagesgrenze um 15:00 Uhr.

    Vor 15:00 Uhr gilt nur `< heute` als Vergangenheit.
    Ab 15:00 Uhr gilt auch `== heute` als Vergangenheit.
    """
    current = now or datetime.now()
    today = current.date()
    if ub_date < today:
        return True
    if ub_date > today:
        return False
    hour = max(0, min(23, int(cutoff_hour)))
    minute = max(0, min(59, int(cutoff_minute)))
    return current.time() >= time(hour=hour, minute=minute)
