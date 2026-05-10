from __future__ import annotations

from datetime import time

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.dialogs import (
    SettingsDialogSpec,
    SettingsFieldSpec,
    SettingsSectionSpec,
    open_tabbed_settings_dialog,
)

from kursplaner.adapters.gui.dialog_services import filedialog, messagebox
from kursplaner.core.config.ui_preferences_store import LessonBuilderFieldSettings
from kursplaner.core.usecases.path_settings_usecase import PathSettingsUseCase

_UB_CUTOFF_HOUR_KEY = "ub_past_cutoff_hour"
_UB_CUTOFF_MINUTE_KEY = "ub_past_cutoff_minute"
_SHOW_KOMPETENZEN_KEY = "lesson_builder_show_kompetenzen"
_SHOW_STUNDENZIEL_KEY = "lesson_builder_show_stundenziel"


def _build_settings_spec(path_settings_usecase: PathSettingsUseCase) -> SettingsDialogSpec:
    """Create the shared tabbed settings spec for Kursplaner settings."""

    path_fields = tuple(
        SettingsFieldSpec(
            key=field.key,
            label=field.label,
            field_type="string",
            hint=field.help_text,
        )
        for field in path_settings_usecase.path_field_definitions()
    )

    return SettingsDialogSpec(
        sections=(
            SettingsSectionSpec(
                key="paths",
                label="Pfad-Einstellungen",
                fields=path_fields,
            ),
            SettingsSectionSpec(
                key="ub_past_cutoff",
                label="UB-Vergangenheitsregel",
                fields=(
                    SettingsFieldSpec(
                        key=_UB_CUTOFF_HOUR_KEY,
                        label="UB-Cutoff Stunde",
                        field_type="int",
                        default=15,
                        min_value=0,
                        max_value=23,
                        hint="UBs am aktuellen Datum gelten ab dieser Uhrzeit als Vergangenheit.",
                    ),
                    SettingsFieldSpec(
                        key=_UB_CUTOFF_MINUTE_KEY,
                        label="UB-Cutoff Minute",
                        field_type="int",
                        default=0,
                        min_value=0,
                        max_value=59,
                        hint="24h-Format.",
                    ),
                ),
            ),
            SettingsSectionSpec(
                key="lesson_builder_fields",
                label="Einheit planen: optionale Felder",
                fields=(
                    SettingsFieldSpec(
                        key=_SHOW_KOMPETENZEN_KEY,
                        label="Kompetenzen anzeigen",
                        field_type="bool",
                        default=True,
                    ),
                    SettingsFieldSpec(
                        key=_SHOW_STUNDENZIEL_KEY,
                        label="Stundenziel anzeigen",
                        field_type="bool",
                        default=True,
                    ),
                ),
            ),
        )
    )


def _initial_values(
    *,
    path_values: dict[str, str],
    ub_past_cutoff_time: time,
    lesson_builder_field_settings: LessonBuilderFieldSettings,
) -> dict[str, object]:
    values: dict[str, object] = {key: value for key, value in path_values.items()}
    values[_UB_CUTOFF_HOUR_KEY] = int(ub_past_cutoff_time.hour)
    values[_UB_CUTOFF_MINUTE_KEY] = int(ub_past_cutoff_time.minute)
    values[_SHOW_KOMPETENZEN_KEY] = bool(lesson_builder_field_settings.show_kompetenzen)
    values[_SHOW_STUNDENZIEL_KEY] = bool(lesson_builder_field_settings.show_stundenziel)
    return values


def _extract_path_values(payload: dict[str, object], path_settings_usecase: PathSettingsUseCase) -> dict[str, str]:
    values: dict[str, str] = {}
    for field in path_settings_usecase.path_field_definitions():
        raw = payload.get(field.key, "")
        values[field.key] = str(raw).strip()
    return values


def _extract_cutoff_time(payload: dict[str, object]) -> time:
    hour = int(payload.get(_UB_CUTOFF_HOUR_KEY, 15))
    minute = int(payload.get(_UB_CUTOFF_MINUTE_KEY, 0))
    hour = max(0, min(23, hour))
    minute = max(0, min(59, minute))
    return time(hour=hour, minute=minute)


def _extract_lesson_builder_settings(payload: dict[str, object]) -> LessonBuilderFieldSettings:
    return LessonBuilderFieldSettings(
        show_kompetenzen=bool(payload.get(_SHOW_KOMPETENZEN_KEY, True)),
        show_stundenziel=bool(payload.get(_SHOW_STUNDENZIEL_KEY, True)),
    )


def _pick_path_for_issue(
    *,
    parent,
    issue_key: str,
    current_values: dict[str, str],
    path_settings_usecase: PathSettingsUseCase,
) -> str | None:
    """Open picker dialog for an invalid path field and return normalized value."""

    field = path_settings_usecase.path_field_by_key(issue_key)
    if field is None:
        return None

    current = path_settings_usecase.resolve_for_key(current_values, issue_key)
    initial = current if current.exists() else current.parent
    if field.kind == "file":
        selected = filedialog.askopenfilename(
            parent=parent,
            title=field.pick_title,
            initialdir=str(initial),
            filetypes=[("JSON", "*.json"), ("Alle Dateien", "*.*")],
        )
    else:
        selected = filedialog.askdirectory(
            parent=parent,
            title=field.pick_title,
            initialdir=str(initial),
        )

    if not selected:
        return None

    updated_values, changed = path_settings_usecase.apply_selected_path(current_values, issue_key, selected)
    if not changed:
        return None
    return updated_values.get(issue_key)


def open_settings_dialog(
    master,
    *,
    path_values: dict[str, str],
    on_saved=None,
    ub_past_cutoff_time: time | None = None,
    on_ub_past_cutoff_saved=None,
    lesson_builder_field_settings: LessonBuilderFieldSettings | None = None,
    on_lesson_builder_fields_saved=None,
    theme_key: str | None = None,
    path_settings_usecase: PathSettingsUseCase | None = None,
) -> None:
    """Open Kursplaner settings using the shared tabbed settings renderer."""

    if path_settings_usecase is None:
        raise RuntimeError("PathSettingsUseCase fehlt in SettingsWindow-Verdrahtung.")

    spec = _build_settings_spec(path_settings_usecase)
    active_path_values = dict(path_values)
    active_cutoff = ub_past_cutoff_time or time(hour=15, minute=0)
    active_lesson_builder_settings = lesson_builder_field_settings or LessonBuilderFieldSettings()
    active_section: str | None = None
    effective_theme_key = str(theme_key or "slate_indigo")

    while True:
        payload = _initial_values(
            path_values=active_path_values,
            ub_past_cutoff_time=active_cutoff,
            lesson_builder_field_settings=active_lesson_builder_settings,
        )
        result = open_tabbed_settings_dialog(
            master,
            title="Einstellungen",
            theme_key=effective_theme_key,
            spec=spec,
            initial_values=payload,
            initial_section=active_section,
        )
        if result is None:
            return

        proposed_path_values = _extract_path_values(result, path_settings_usecase)
        proposed_cutoff = _extract_cutoff_time(result)
        proposed_lesson_builder = _extract_lesson_builder_settings(result)

        issues = path_settings_usecase.validate_values(proposed_path_values)
        if issues:
            first = issues[0]
            choose_other = messagebox.askyesno(
                "Einstellungen",
                f"{first.message}\n\nMöchten Sie stattdessen einen anderen Ort auswählen?",
                parent=master,
            )
            if choose_other:
                selected = _pick_path_for_issue(
                    parent=master,
                    issue_key=first.key,
                    current_values=proposed_path_values,
                    path_settings_usecase=path_settings_usecase,
                )
                if selected:
                    proposed_path_values[first.key] = selected

            active_path_values = proposed_path_values
            active_cutoff = proposed_cutoff
            active_lesson_builder_settings = proposed_lesson_builder
            active_section = "paths"
            continue

        saved_values = path_settings_usecase.save_values(proposed_path_values)
        if on_saved:
            on_saved(saved_values)
        if on_ub_past_cutoff_saved:
            on_ub_past_cutoff_saved(proposed_cutoff)
        if on_lesson_builder_fields_saved:
            on_lesson_builder_fields_saved(proposed_lesson_builder)
        return

