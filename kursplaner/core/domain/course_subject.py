from __future__ import annotations

COURSE_SUBJECT_TO_SHORT: dict[str, str] = {
    "Informatik": "Inf",
    "Mathematik": "Mat",
    "Darstellendes Spiel": "DS",
}


def normalize_course_subject(value: str) -> str:
    """Validiert hart auf den verbindlichen Kursfach-Standard."""
    normalized = str(value or "").strip()
    if normalized in COURSE_SUBJECT_TO_SHORT:
        return normalized
    allowed = ", ".join(COURSE_SUBJECT_TO_SHORT.keys())
    raise ValueError(f"Kursfach muss exakt einem Standardwert entsprechen ({allowed}).")


def short_subject_for_course_subject(course_subject: str) -> str:
    """Leitet das deterministische Fachkuerzel aus einem standardisierten Kursfach ab."""
    canonical = normalize_course_subject(course_subject)
    return COURSE_SUBJECT_TO_SHORT[canonical]


_SORT_UMLAUT_FOLD = str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss"})


def subject_short_or_name(subject: str) -> str:
    """Liefert das offizielle Fachkürzel (z. B. ``"Mat"``) oder -- falls unbekannt -- den Fachnamen selbst.

    Im Gegensatz zu `short_subject_for_course_subject()` wirft diese Funktion
    NIE: Sie ist für Anzeige-Labels gedacht, deren Fachname aus Vault-Daten
    stammt (z. B. dem Ordnernamen eines Kompetenznetz-Fachs), die dem
    Kursfach-Standard noch nicht entsprechen müssen. Ein neu angelegter
    Fachordner ohne Standard-Kürzel erscheint so mit vollem Namen, statt die
    GUI abstürzen zu lassen.

    Args:
        subject: Fachname, z. B. ``"Mathematik"``.

    Returns:
        Kürzel aus `COURSE_SUBJECT_TO_SHORT` oder den (getrimmten) Fachnamen.
    """
    normalized = str(subject or "").strip()
    return COURSE_SUBJECT_TO_SHORT.get(normalized, normalized)


def subject_sort_key(text: str) -> str:
    """Sortierschlüssel für deutsche Anzeigetexte (Fächer, Bereichstitel).

    `sorted()` vergleicht Codepoints -- Umlaute landen dadurch hinter "z"
    und Großbuchstaben vor Kleinbuchstaben. Dieser Schlüssel faltet Groß-/
    Kleinschreibung und Umlaute (ä→a, ö→o, ü→u, ß→ss), sodass z. B.
    "Ökonomie" zwischen "Mathematik" und "Physik" einsortiert wird.

    Args:
        text: Beliebiger Anzeigetext.

    Returns:
        Normalisierter Vergleichsschlüssel.
    """
    return str(text or "").casefold().translate(_SORT_UMLAUT_FOLD)
