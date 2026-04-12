from __future__ import annotations

from typing import Literal

LessonType = Literal["Unterricht", "LZK", "Ausfall", "Hospitation"]

LESSON_TYPE_VALUES: tuple[LessonType, ...] = ("Unterricht", "LZK", "Ausfall", "Hospitation")

LIST_FIELDS = {
    "Kompetenzen",
    "Teilziele",
    "Material",
    "Vertretungsmaterial",
    "Ressourcen",
    "Baustellen",
}

_TYPE_ALIASES: dict[str, LessonType] = {
    "u": "Unterricht",
    "unterricht": "Unterricht",
    "l": "LZK",
    "lzk": "LZK",
    "a": "Ausfall",
    "ausfall": "Ausfall",
    "h": "Hospitation",
    "ho": "Hospitation",
    "hospitation": "Hospitation",
}

_ALLOWED_BY_TYPE: dict[LessonType, tuple[str, ...]] = {
    "Unterricht": (
        "Stundentyp",
        "Dauer",
        "Stundenthema",
        "Oberthema",
        "Stundenziel",
        "Teilziele",
        "Kompetenzen",
        "Material",
        "Unterrichtsbesuch",
    ),
    "LZK": (
        "Stundentyp",
        "Dauer",
        "Stundenthema",
        "Oberthema",
        "Kompetenzhorizont",
        "created_at",
        "Inhaltsübersicht",
    ),
    "Ausfall": ("Stundentyp", "Dauer", "Stundenthema", "Vertretungsmaterial"),
    "Hospitation": ("Stundentyp", "Dauer", "Stundenthema", "Beobachtungsschwerpunkte", "Ressourcen", "Baustellen"),
}


def normalize_stundentyp(value: object) -> LessonType:
    """Normalisiert Bezeichnungen auf die kanonischen Stundentyp-Werte."""
    lowered = str(value or "").strip().lower()
    resolved = _TYPE_ALIASES.get(lowered)
    if resolved is None:
        raise RuntimeError("Ungueltiger Stundentyp. Erlaubt: Unterricht, LZK, Ausfall, Hospitation.")
    return resolved


def infer_stundentyp(data: dict[str, object]) -> LessonType:
    """Leitet den Stundentyp robust aus YAML-Daten ab."""
    raw_type = str(data.get("Stundentyp", "")).strip()
    if raw_type:
        try:
            return normalize_stundentyp(raw_type)
        except RuntimeError:
            pass

    topic = str(data.get("Stundenthema", "")).strip().lower()
    if any(key in data for key in ("Beobachtungsschwerpunkte", "Ressourcen", "Baustellen")) or "hospitation" in topic:
        return "Hospitation"
    if any(key in data for key in ("Kompetenzhorizont", "Inhaltsübersicht")) or "lzk" in topic:
        return "LZK"
    if "Vertretungsmaterial" in data:
        return "Ausfall"
    return "Unterricht"


def allowed_keys_for_type(stundentyp: LessonType) -> tuple[str, ...]:
    """Liefert die exakt erlaubten YAML-Felder fuer einen Stundentyp."""
    return _ALLOWED_BY_TYPE[stundentyp]


def _normalize_list(value: object) -> list[str]:
    if isinstance(value, list):
        items = value
    elif isinstance(value, str) and value.strip():
        items = [value]
    else:
        return []

    result: list[str] = []
    for item in items:
        text = str(item).strip()
        if text:
            result.append(text)
    return result


def _normalize_scalar(value: object) -> str:
    if isinstance(value, list):
        return ""
    return str(value or "").strip()


def default_yaml_for_type(stundentyp: LessonType, *, topic: str, duration: int | str = 2) -> dict[str, object]:
    """Erzeugt typspezifische YAML-Defaults mit exakt erlaubten Schluesseln."""
    topic_text = str(topic or "").strip() or "Neue Stunde"
    duration_text = str(duration or "").strip() or "2"

    defaults: dict[str, object] = {
        "Stundentyp": stundentyp,
        "Dauer": duration_text,
        "Stundenthema": topic_text,
    }

    if stundentyp == "Unterricht":
        defaults.update(
            {
                "Oberthema": "",
                "Stundenziel": "",
                "Teilziele": [],
                "Kompetenzen": [],
                "Material": [],
                "Unterrichtsbesuch": "",
            }
        )
    elif stundentyp == "LZK":
        defaults.update(
            {
                "Oberthema": "",
                "Kompetenzhorizont": "",
                "Inhaltsübersicht": "",
            }
        )
    elif stundentyp == "Ausfall":
        defaults.update(
            {
                "Vertretungsmaterial": [],
            }
        )
    elif stundentyp == "Hospitation":
        defaults.update(
            {
                "Beobachtungsschwerpunkte": "",
                "Ressourcen": [],
                "Baustellen": [],
            }
        )

    return defaults


def canonicalize_lesson_yaml(
    data: dict[str, object] | None,
    *,
    forced_type: LessonType | None = None,
    topic_hint: str = "",
    duration_hint: int | str = 2,
) -> dict[str, object]:
    """Normalisiert YAML-Daten auf den exakten Schluesselsatz des Stundentyps."""
    source = data if isinstance(data, dict) else {}
    stundentyp = forced_type if forced_type is not None else infer_stundentyp(source)

    hint_topic = str(topic_hint or "").strip()
    source_topic = _normalize_scalar(source.get("Stundenthema", ""))
    topic = source_topic or hint_topic or "Neue Stunde"

    source_duration = _normalize_scalar(source.get("Dauer", ""))
    duration = source_duration or str(duration_hint or "2")

    normalized = default_yaml_for_type(stundentyp, topic=topic, duration=duration)
    allowed = set(allowed_keys_for_type(stundentyp))

    for key in allowed:
        if key not in source:
            continue
        if key == "Stundentyp":
            normalized[key] = stundentyp
            continue
        if key in LIST_FIELDS:
            normalized[key] = _normalize_list(source[key])
            continue
        if key == "Stundenthema":
            text = _normalize_scalar(source[key])
            normalized[key] = text or topic
            continue
        if key == "Dauer":
            text = _normalize_scalar(source[key])
            normalized[key] = text or str(duration)
            continue
        normalized[key] = _normalize_scalar(source[key])

    return normalized
