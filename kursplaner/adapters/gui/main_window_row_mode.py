"""Hauptfenster: Zeilenmodus, Spaltensichtbarkeit und Zeilenfilter (Delegationen an Grid- und Aktions-Controller).

Aus ``main_window.py`` ausgelagert (300-Zeilen-Regel), Methoden unverändert."""

from __future__ import annotations

from kursplaner.core.config.ui_preferences_store import save_column_visibility_settings, save_row_filter_settings
from kursplaner.core.usecases.row_display_mode_usecase import RowFilterSettings


class KursplanerRowModeMixin:
    """Hauptfenster: Zeilenmodus, Spaltensichtbarkeit und Zeilenfilter (Delegationen an Grid- und Aktions-Controller)."""

    def _open_column_visibility_settings(self):
        """Öffnet den Dialog zum Ein-/Ausblenden von Spaltenarten."""
        self.action_controller.open_column_visibility_settings()

    def _refresh_row_mode_button_styles(self):
        """Aktualisiert die Beschriftung der Modusbuttons gemäß aktivem Modus."""
        for mode_key, button in self.row_mode_buttons.items():
            base_label = self.row_mode_labels.get(mode_key, mode_key.title())
            label = f"● {base_label}" if mode_key == self.active_row_mode else base_label
            button.configure(text=label)

    def _set_row_mode(self, mode_key: str, *, manual: bool = True):
        """Setzt den aktiven Zeilen-Anzeigemodus und rendert bei Änderung neu."""
        normalized = self.row_display_mode_usecase.normalize_mode(mode_key)
        if manual:
            self.auto_row_mode_var.set(False)

        changed = normalized != self.active_row_mode
        self.active_row_mode = normalized
        self.row_defs = self.row_display_mode_usecase.row_defs_for_mode(
            self.active_row_mode, self.row_filter_settings
        )
        self._refresh_row_mode_button_styles()
        if changed:
            self._rebuild_grid()

    def _on_toggle_auto_row_mode(self):
        """Reagiert auf Umschalten des Auto-Modus für Zeilenansichten."""
        if bool(self.auto_row_mode_var.get()):
            self._update_row_mode_from_selection()

    def _set_column_visibility_settings(self, settings):
        """Setzt globale Sichtbarkeits-/Marker-Einstellungen und rendert neu."""
        self.column_visibility_settings = settings
        save_column_visibility_settings(settings)
        self._collect_day_columns()
        self._update_row_mode_from_selection()
        self._rebuild_grid()

    def _set_row_filter_settings(self, settings: RowFilterSettings) -> None:
        """Setzt den Zeilenfilter, persistiert ihn und rendert das Grid neu."""
        save_row_filter_settings(settings)
        self.row_filter_settings = settings
        self.row_defs = self.row_display_mode_usecase.row_defs_for_mode(self.active_row_mode, settings)
        self._rebuild_grid()

    def _update_row_mode_from_selection(self):
        """Leitet den Zeilenmodus automatisch aus der selektierten Spaltenart ab."""
        if not bool(self.auto_row_mode_var.get()):
            return
        mode = self.row_display_mode_usecase.mode_for_selection(
            selected_day_indices=set(self.selected_day_indices),
            day_columns=list(self.day_columns),
            fallback_mode=self.active_row_mode,
        )
        self._set_row_mode(mode, manual=False)
