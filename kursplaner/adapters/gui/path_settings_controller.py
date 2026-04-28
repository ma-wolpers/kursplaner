from __future__ import annotations

import pathlib
from datetime import time
from tkinter import filedialog

from kursplaner.adapters.gui.settings_window import SettingsWindow
from kursplaner.core.config.ui_preferences_store import (
    LessonBuilderFieldSettings,
    load_lesson_builder_field_settings,
    load_ub_past_cutoff_time,
    save_lesson_builder_field_settings,
    save_ub_past_cutoff_time,
)
from kursplaner.core.usecases.path_settings_usecase import PathSettingsUseCase


class MainWindowPathSettingsController:
    """Kapselt Pfad-/Settings-Interaktionen der Hauptansicht."""

    def __init__(self, app):
        """Initialisiert den Controller mit App-Referenz und Pfad-Use-Case."""
        self.app = app
        self.path_settings_usecase = PathSettingsUseCase()

    def pick_base_dir(self):
        """Öffnet einen Ordnerdialog und übernimmt den neuen Unterrichtspfad."""
        current_dir = pathlib.Path(self.app.base_dir_var.get().strip() or ".").expanduser().resolve()
        selected = filedialog.askdirectory(
            parent=self.app,
            initialdir=self.path_settings_usecase.suggest_initial_dir(current_dir),
        )
        if selected:
            updated_values, changed = self.path_settings_usecase.apply_selected_path(
                self.app.path_values,
                self.path_settings_usecase.UNTERRICHT_KEY,
                selected,
            )
            if changed:
                self.apply_saved_paths(self.path_settings_usecase.save_values(updated_values))
            self.app.refresh_overview()

    def apply_saved_paths(self, values: dict[str, str]):
        """Synchronisiert persistierte Pfade in Variablen und UI-Strings."""
        self.app.path_values = values
        self.app.base_dir_var.set(str(self.path_settings_usecase.resolve_unterricht_dir(values)))

    def archive_dir(self) -> pathlib.Path:
        """Berechnet den Standard-Archivordner unterhalb des Unterrichtspfads."""
        return self.path_settings_usecase.resolve_unterricht_dir(self.app.path_values) / "Archiv"

    def auto_archive_enabled(self) -> bool:
        """Signalisiert, ob automatisches Archivieren unterstützt/aktiv ist."""
        return False

    def open_settings_window(self):
        """Öffnet das Fenster zur Pflege aller verwalteten Pfade."""
        window = SettingsWindow(
            self.app,
            path_values=self.app.path_values,
            on_saved=lambda values: self.on_paths_saved(values),
            ub_past_cutoff_time=load_ub_past_cutoff_time(),
            on_ub_past_cutoff_saved=self.on_ub_past_cutoff_saved,
            lesson_builder_field_settings=load_lesson_builder_field_settings(),
            on_lesson_builder_fields_saved=self.on_lesson_builder_fields_saved,
            theme_key=self.app.theme_var.get(),
            path_settings_usecase=self.path_settings_usecase,
        )
        window.grab_set()

    @staticmethod
    def on_ub_past_cutoff_saved(cutoff: time) -> None:
        """Persistiert die konfigurierbare Uhrzeit für UB-Vergangenheitszählung."""
        save_ub_past_cutoff_time(cutoff)

    @staticmethod
    def on_lesson_builder_fields_saved(settings: LessonBuilderFieldSettings) -> None:
        """Persistiert Sichtbarkeit optionaler Felder im Lesson-Builder."""
        save_lesson_builder_field_settings(settings)

    def on_paths_saved(self, values: dict[str, str]):
        """Übernimmt gespeicherte Pfade und lädt die Übersicht neu."""
        self.apply_saved_paths(values)
        self.app.refresh_overview()
