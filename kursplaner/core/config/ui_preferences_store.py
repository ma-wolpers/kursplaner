from dataclasses import dataclass
from datetime import time
from pathlib import Path

from bw_libs.app_paths import atomic_write_json
from bw_libs.safe_read import read_json_or_default
from kursplaner.core.config.settings import SCRIPT_DIR
from kursplaner.core.usecases.column_visibility_projection_usecase import ColumnVisibilitySettings
from kursplaner.core.usecases.row_display_mode_usecase import RowFilterSettings

_THEME_KEY = "theme"
_COLUMN_VISIBILITY_KEY = "column_visibility"
_UB_PAST_CUTOFF_KEY = "ub_past_cutoff_time"
_LESSON_BUILDER_FIELDS_KEY = "lesson_builder_fields"
_COURSE_OVERVIEW_HIGHLIGHT_DAYS_KEY = "course_overview_highlight_days"
_ROW_FILTER_KEY = "row_filter"
_SCHOOL_WIDE_CANCELLATIONS_PATH_KEY = "school_wide_cancellations_path"


@dataclass(frozen=True)
class LessonBuilderFieldSettings:
    """Konfiguriert sichtbare optionale Felder im Lesson-Builder-Dialog."""

    show_kompetenzen: bool = True
    show_stundenziel: bool = True


def _preferences_file() -> Path:
    """Liefert den Pfad zur UI-Persistenzdatei."""
    return SCRIPT_DIR / "config" / "ui_preferences.json"


def _load_payload() -> dict[str, object]:
    path = _preferences_file()
    if not path.exists():
        return {}
    payload = read_json_or_default(path, default=None)
    if isinstance(payload, dict):
        return payload
    return {}


def _save_payload(payload: dict[str, object]) -> None:
    path = _preferences_file()
    atomic_write_json(path, payload)


def load_theme_key(default_theme: str) -> str:
    """Lädt den gespeicherten Theme-Key oder liefert den Default."""
    payload = _load_payload()
    value = payload.get(_THEME_KEY)
    if not isinstance(value, str) or not value.strip():
        return default_theme
    return value.strip()


def save_theme_key(theme_key: str):
    """Persistiert den übergebenen Theme-Key in der UI-Persistenzdatei."""
    payload = _load_payload()
    payload[_THEME_KEY] = theme_key.strip()
    _save_payload(payload)


def load_column_visibility_settings() -> ColumnVisibilitySettings:
    """Lädt globale Spalten-Sichtbarkeits- und Marker-Einstellungen."""
    payload = _load_payload()
    raw = payload.get(_COLUMN_VISIBILITY_KEY)
    if not isinstance(raw, dict):
        return ColumnVisibilitySettings()

    defaults = ColumnVisibilitySettings()
    return ColumnVisibilitySettings(
        hide_unterricht=bool(raw.get("hide_unterricht", defaults.hide_unterricht)),
        hide_lzk=bool(raw.get("hide_lzk", defaults.hide_lzk)),
        hide_ausfall=bool(raw.get("hide_ausfall", defaults.hide_ausfall)),
        hide_hospitation=bool(raw.get("hide_hospitation", defaults.hide_hospitation)),
        hide_leer=bool(raw.get("hide_leer", defaults.hide_leer)),
        hint_unterricht=bool(raw.get("hint_unterricht", defaults.hint_unterricht)),
        hint_lzk=bool(raw.get("hint_lzk", defaults.hint_lzk)),
        hint_ausfall=bool(raw.get("hint_ausfall", defaults.hint_ausfall)),
        hint_hospitation=bool(raw.get("hint_hospitation", defaults.hint_hospitation)),
        hint_leer=bool(raw.get("hint_leer", defaults.hint_leer)),
    )


def save_column_visibility_settings(settings: ColumnVisibilitySettings) -> None:
    """Persistiert globale Spalten-Sichtbarkeits- und Marker-Einstellungen."""
    payload = _load_payload()
    payload[_COLUMN_VISIBILITY_KEY] = {
        "hide_unterricht": bool(settings.hide_unterricht),
        "hide_lzk": bool(settings.hide_lzk),
        "hide_ausfall": bool(settings.hide_ausfall),
        "hide_hospitation": bool(settings.hide_hospitation),
        "hide_leer": bool(settings.hide_leer),
        "hint_unterricht": bool(settings.hint_unterricht),
        "hint_lzk": bool(settings.hint_lzk),
        "hint_ausfall": bool(settings.hint_ausfall),
        "hint_hospitation": bool(settings.hint_hospitation),
        "hint_leer": bool(settings.hint_leer),
    }
    _save_payload(payload)


def load_ub_past_cutoff_time(default: time | None = None) -> time:
    """Lädt die UB-Vergangenheitsgrenze als Uhrzeit (HH:MM)."""
    fallback = default or time(hour=15, minute=0)
    payload = _load_payload()
    raw = payload.get(_UB_PAST_CUTOFF_KEY)
    if not isinstance(raw, str):
        return fallback
    text = raw.strip()
    if not text:
        return fallback

    parts = text.split(":", 1)
    if len(parts) != 2:
        return fallback
    hour_text, minute_text = parts
    if not (hour_text.isdigit() and minute_text.isdigit()):
        return fallback

    hour = int(hour_text)
    minute = int(minute_text)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return fallback
    return time(hour=hour, minute=minute)


def save_ub_past_cutoff_time(value: time) -> None:
    """Persistiert die UB-Vergangenheitsgrenze als HH:MM-String."""
    payload = _load_payload()
    payload[_UB_PAST_CUTOFF_KEY] = f"{int(value.hour):02d}:{int(value.minute):02d}"
    _save_payload(payload)


def load_lesson_builder_field_settings() -> LessonBuilderFieldSettings:
    """Lädt Sichtbarkeit optionaler Felder im Lesson-Builder."""
    payload = _load_payload()
    raw = payload.get(_LESSON_BUILDER_FIELDS_KEY)
    if not isinstance(raw, dict):
        return LessonBuilderFieldSettings()

    defaults = LessonBuilderFieldSettings()
    return LessonBuilderFieldSettings(
        show_kompetenzen=bool(raw.get("show_kompetenzen", defaults.show_kompetenzen)),
        show_stundenziel=bool(raw.get("show_stundenziel", defaults.show_stundenziel)),
    )


def save_lesson_builder_field_settings(settings: LessonBuilderFieldSettings) -> None:
    """Persistiert Sichtbarkeit optionaler Felder im Lesson-Builder."""
    payload = _load_payload()
    payload[_LESSON_BUILDER_FIELDS_KEY] = {
        "show_kompetenzen": bool(settings.show_kompetenzen),
        "show_stundenziel": bool(settings.show_stundenziel),
    }
    _save_payload(payload)


def load_course_overview_highlight_days(default: int = 5) -> int:
    """Laedt das Hervorhebungsfenster (Tage) fuer die Kursuebersicht."""
    fallback = max(0, min(60, int(default)))
    payload = _load_payload()
    raw = payload.get(_COURSE_OVERVIEW_HIGHLIGHT_DAYS_KEY)
    if raw is None:
        return fallback

    if isinstance(raw, bool):
        return fallback

    if isinstance(raw, int):
        return max(0, min(60, raw))

    text = str(raw).strip()
    if not text.isdigit():
        return fallback
    return max(0, min(60, int(text)))


def save_course_overview_highlight_days(value: int) -> None:
    """Persistiert das Hervorhebungsfenster (Tage) fuer die Kursuebersicht."""
    payload = _load_payload()
    payload[_COURSE_OVERVIEW_HIGHLIGHT_DAYS_KEY] = max(0, min(60, int(value)))
    _save_payload(payload)


def load_row_filter_settings() -> RowFilterSettings:
    """Lädt die persistierten Zeilenfilter-Einstellungen.

    Bei fehlendem oder korruptem Eintrag wird ein leeres ``RowFilterSettings()``
    (= Standard-Moduszugehörigkeit für alle Felder) zurückgegeben. Ein Eintrag im
    alten Format (``hidden_fields``, vor der Pro-Modus-Konfiguration) wird einmalig
    migriert: global versteckte Felder werden auf "in keinem Modus sichtbar"
    abgebildet, damit bestehende Nutzer-Einstellungen nicht verloren gehen.
    """
    payload = _load_payload()
    raw = payload.get(_ROW_FILTER_KEY)
    if not isinstance(raw, dict):
        return RowFilterSettings()

    overrides_raw = raw.get("field_mode_overrides")
    if isinstance(overrides_raw, dict):
        overrides = {
            str(field_key): frozenset(str(mode) for mode in modes if isinstance(mode, str))
            for field_key, modes in overrides_raw.items()
            if isinstance(field_key, str) and isinstance(modes, list)
        }
        return RowFilterSettings(field_mode_overrides=overrides)

    hidden_raw = raw.get("hidden_fields")
    if isinstance(hidden_raw, list):
        hidden = frozenset(str(k) for k in hidden_raw if isinstance(k, str))
        return RowFilterSettings(field_mode_overrides={field_key: frozenset() for field_key in hidden})

    return RowFilterSettings()


def load_school_wide_cancellations_path_override() -> str:
    """Lädt den konfigurierten Override-Pfad für `schulweite_ausfaelle.json` (leer = Standardort).

    Rein technische String-Ablage - Pfadauflösung, Default und Migration
    gehören in `core.config.school_wide_cancellations_store`, nicht hierher.
    """
    payload = _load_payload()
    raw = payload.get(_SCHOOL_WIDE_CANCELLATIONS_PATH_KEY)
    return raw.strip() if isinstance(raw, str) else ""


def save_school_wide_cancellations_path_override(value: str) -> None:
    """Persistiert den Override-Pfad für `schulweite_ausfaelle.json` (leerer String löscht ihn)."""
    payload = _load_payload()
    payload[_SCHOOL_WIDE_CANCELLATIONS_PATH_KEY] = value.strip()
    _save_payload(payload)


def save_row_filter_settings(settings: RowFilterSettings) -> None:
    """Persistiert die Zeilenfilter-Einstellungen."""
    payload = _load_payload()
    payload[_ROW_FILTER_KEY] = {
        "field_mode_overrides": {
            field_key: sorted(modes) for field_key, modes in settings.field_mode_overrides.items()
        }
    }
    _save_payload(payload)
