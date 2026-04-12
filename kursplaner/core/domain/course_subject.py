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
