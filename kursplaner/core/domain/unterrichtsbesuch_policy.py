from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time


UB_KIND_PAEDAGOGIK = "Pädagogik"
UB_KIND_FACH = "Fach"

UB_KIND_VALUES: tuple[str, ...] = (UB_KIND_PAEDAGOGIK, UB_KIND_FACH)

UB_OVERVIEW_FILE_NAME = "UB Übersicht.md"
UB_ROOT_RELATIVE_PARTS: tuple[str, ...] = ("7thVault", "🏫 Pädagogik", "00 Orga", "02 UBs")

UB_YAML_KEY_BEREICH = "Bereich"
UB_YAML_KEY_LANGENTWURF = "Langentwurf"
UB_YAML_KEY_BEOBACHTUNG = "Beobachtungsschwerpunkt"
UB_YAML_KEY_EINHEIT = "Einheit"

JAHRGANGSSTUFE_MIN = 5
JAHRGANGSSTUFE_MAX = 13

_UB_STEM_PREFIX = "ub"
_UB_STEM_DATE_FORMAT = "%y-%m-%d"
_UB_STEM_FALLBACK = f"{_UB_STEM_PREFIX} 00-00-00"


def normalize_ub_kinds(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Normalisiert UB-Kategorien auf eindeutige, kanonische Persistenzwerte."""
    resolved: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text not in UB_KIND_VALUES:
            raise ValueError("UB-Art ungueltig. Erlaubt sind nur Pädagogik und Fach.")
        if text not in resolved:
            resolved.append(text)

    return tuple(resolved)


def parse_jahrgangsstufe(value: object) -> int | None:
    """Parst einen rohen Stufenwert robust zu ``int`` (5-13) oder ``None``.

    Numerische Stufen 5-13, konsistent mit der bestehenden Konvention in
    ``core/domain/grade_groups.py`` und dem Informatik-Kompetenzkatalog-
    Manifest. Wird auf den `Stufe`-Metadatenwert des Kurses angewendet, zu
    dem eine UB-markierte Einheit gehoert (Single Source of Truth fuer die
    Jahrgangs-Achievements, siehe `QueryUbAchievementsUseCase`) -- ein Kurs
    ausserhalb 5-13 (z. B. Grundschulstufen) liefert bewusst ``None`` statt
    einer Exception, da er fuer UB-Jahrgangs-Achievements nicht in Frage
    kommt.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = int(text)
    except ValueError:
        return None
    if JAHRGANGSSTUFE_MIN <= parsed <= JAHRGANGSSTUFE_MAX:
        return parsed
    return None


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


@dataclass(frozen=True)
class UbStem:
    """Value object for the canonical UB filename stem `ub yy-mm-dd`.

    Centralises the stem format so that build, parse, and format logic
    live in one place.  Any future change to the naming convention only
    requires touching this class and its three helpers below.

    Attributes:
        date_token: Two-digit-year date token in the form ``yy-mm-dd``,
            e.g. ``"26-03-31"``.

    Example::

        stem = UbStem.from_date_text("31-03-26")
        assert str(stem) == "ub 26-03-31"
        assert stem.date() == date(2026, 3, 31)
    """

    date_token: str

    @classmethod
    def from_date_text(cls, date_text: str) -> "UbStem":
        """Erstellt einen UbStem aus einem beliebigen unterstützten Datumsformat.

        Args:
            date_text: Datumstext in einem der von ``parse_ub_yy_mm_dd``
                unterstützten Formate (z. B. ``"31-03-26"`` oder ``"2026-03-31"``).

        Returns:
            UbStem mit dem kanonischen Datumstoken.
        """
        return cls(date_token=parse_ub_yy_mm_dd(date_text))

    @classmethod
    def parse(cls, raw_stem: str) -> "UbStem | None":
        """Liest einen UbStem aus einem bestehenden Dateistamm.

        Akzeptiert nur das aktuelle Format ``ub yy-mm-dd`` (Kleinbuchstaben).
        Alte Stämme im Format ``UB yy-mm-dd Titel`` geben ``None`` zurück,
        damit der Caller sie als migrationspflichtig erkennt.

        Args:
            raw_stem: Dateistamm ohne Erweiterung, z. B. ``"ub 26-03-31"``.

        Returns:
            UbStem wenn das Format passt, sonst None.
        """
        text = str(raw_stem or "").strip()
        if not text.startswith(f"{_UB_STEM_PREFIX} "):
            return None
        parts = text.split(" ", 1)
        if len(parts) < 2:
            return None
        token = parts[1].strip()[:8]
        try:
            datetime.strptime(token, _UB_STEM_DATE_FORMAT)
            return cls(date_token=token)
        except ValueError:
            return None

    def __str__(self) -> str:
        """Liefert den kanonischen Dateistamm, z. B. ``"ub 26-03-31"``."""
        return f"{_UB_STEM_PREFIX} {self.date_token}"

    def date(self) -> date | None:
        """Konvertiert den Datumstoken zu einem ``datetime.date``-Objekt."""
        try:
            return datetime.strptime(self.date_token, _UB_STEM_DATE_FORMAT).date()
        except ValueError:
            return None


def build_ub_stem(date_text: str) -> str:
    """Baut den kanonischen UB-Dateistamm ``ub yy-mm-dd``.

    Der Titel der Unterrichtseinheit wird bewusst nicht mehr im Dateinamen
    kodiert, um Datei-Link-Drift zu vermeiden wenn ein Titel nachträglich
    geändert wird.

    Args:
        date_text: Datumstext in einem beliebigen unterstützten Format.

    Returns:
        Kanonischer Stamm, z. B. ``"ub 26-03-31"``.
    """
    return str(UbStem.from_date_text(date_text))


def parse_ub_date_from_stem(stem: str) -> date | None:
    """Liest das UB-Datum aus dem Dateistamm ``ub yy-mm-dd`` aus.

    Args:
        stem: Dateistamm ohne Erweiterung, z. B. ``"ub 26-03-31"``.

    Returns:
        ``datetime.date``-Objekt oder None wenn das Format nicht passt.
    """
    ub = UbStem.parse(stem)
    return ub.date() if ub is not None else None


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
