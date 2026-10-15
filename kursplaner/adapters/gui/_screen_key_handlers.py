"""Key and mouse event handlers of the main window (ScreenBuilder mixin).

Split out of screen_builder.py (file-size rule). Handlers receive bw-gui ``KeyEvent``s
or pointer events and return ``EventResult`` (``None`` lets the event continue). Exact
modifiers make the former "Strg oder unbekannter Zustand"-Pruefung bei Pfeil hoch/runter
ueberfluessig: Strg+Pfeil erreicht diese Definitionen gar nicht mehr."""

from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.contracts import EventResult, Key
from bw_gui.runtime import ui, widgets

from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.adapters.gui.ui_intents import UiIntent


class ScreenKeyHandlersMixin:
    """Key and mouse event handlers of the main window (ScreenBuilder mixin)."""

    def _on_global_click_commit_cell(self, event):
        """Meldet globalen Klick als Commit-Intent an den Orchestrator."""
        if self._has_active_popup():
            return EventResult.HANDLED
        return self._emit_intent(UiIntent.GLOBAL_CLICK_COMMIT_CELL, event=event)

    def _on_tree_confirm_selection(self, _event):
        """Meldet Kurslisten-Bestätigung als Intent an den Orchestrator."""
        return self._emit_intent(UiIntent.COURSE_CONFIRM_SELECTION, event=_event)

    def _on_tree_enter(self, _event):
        """Meldet Enter im Kursbaum als GRID_ENTER, damit Kursauswahl über dieselbe `SelectionLayerStack` läuft.

        Ersetzt die frühere direkte `COURSE_CONFIRM_SELECTION`-Emission für
        die Tastatur -- Maus-Trigger (Doppelklick, Loslassen der linken Taste)
        bleiben auf `_on_tree_confirm_selection` gebunden.
        """
        if self._has_active_popup():
            return EventResult.HANDLED
        return self._emit_intent(UiIntent.GRID_ENTER, event=_event)

    def _on_tree_hover_select(self, event):
        """Meldet Hover-Selektion der Kursliste als Intent an den Orchestrator."""
        return self._emit_intent(UiIntent.COURSE_HOVER_SELECT, event=event)

    def _on_tree_keyboard_navigation(self, event):
        """Meldet ↑/↓ in der Kursliste als Intent (``on_key`` vor der Treeview-Klasse, alle Modifier).

        Die native Treeview-Navigation laeuft danach normal weiter (``None``).
        """
        if event.key not in (Key.UP, Key.DOWN):
            return None
        return self._emit_intent(UiIntent.COURSE_KEYBOARD_NAVIGATION, event=event)

    def _on_detail_left(self, _event):
        """Meldet Shortcut für Spaltenfokus nach links als Intent."""
        if self._has_active_popup():
            return EventResult.HANDLED
        return self._emit_intent(UiIntent.SHORTCUT_DETAIL_LEFT, event=_event)

    def _on_detail_right(self, _event):
        """Meldet Shortcut für Spaltenfokus nach rechts als Intent."""
        if self._has_active_popup():
            return EventResult.HANDLED
        return self._emit_intent(UiIntent.SHORTCUT_DETAIL_RIGHT, event=_event)

    def _on_detail_left_all(self, _event):
        """Meldet Alt-Links für Spaltennavigation ohne Skip-Regeln."""
        if self._has_active_popup():
            return EventResult.HANDLED
        return self._emit_intent(UiIntent.SHORTCUT_DETAIL_LEFT_ALL, event=_event)

    def _on_detail_right_all(self, _event):
        """Meldet Alt-Rechts für Spaltennavigation ohne Skip-Regeln."""
        if self._has_active_popup():
            return EventResult.HANDLED
        return self._emit_intent(UiIntent.SHORTCUT_DETAIL_RIGHT_ALL, event=_event)

    def _on_grid_nav_up(self, _event):
        """Meldet Pfeil-hoch für Grid-Navigation im Zellauswahlmodus."""
        if self._has_active_popup():
            return EventResult.HANDLED
        return self._emit_intent(UiIntent.GRID_NAV_UP, event=_event)

    def _on_grid_nav_down(self, _event):
        """Meldet Pfeil-runter für Grid-Navigation im Zellauswahlmodus."""
        if self._has_active_popup():
            return EventResult.HANDLED
        return self._emit_intent(UiIntent.GRID_NAV_DOWN, event=_event)

    def _on_grid_enter(self, _event):
        """Meldet Enter für Übergänge zwischen Spalten-, Zell- und Edit-Modus."""
        if self._has_active_popup():
            return EventResult.HANDLED
        return self._emit_intent(UiIntent.GRID_ENTER, event=_event)

    def _on_home(self, _event):
        """Leitet Home je nach Modus an Kurs- oder Grid-Navigation weiter."""
        if self._has_active_popup():
            return EventResult.HANDLED
        if self._is_editable_widget(getattr(_event, "widget", None)):
            return None
        if bool(getattr(self.app, "is_detail_view", False)):
            return self._emit_intent(UiIntent.GRID_HOME, event=_event)
        return self._emit_intent(UiIntent.COURSE_HOME, event=_event)

    def _on_end(self, _event):
        """Leitet Ende je nach Modus an Kurs- oder Grid-Navigation weiter."""
        if self._has_active_popup():
            return EventResult.HANDLED
        if self._is_editable_widget(getattr(_event, "widget", None)):
            return None
        if bool(getattr(self.app, "is_detail_view", False)):
            return self._emit_intent(UiIntent.GRID_END, event=_event)
        return self._emit_intent(UiIntent.COURSE_END, event=_event)

    @staticmethod
    def _is_editable_widget(widget) -> bool:
        if widget is None:
            return False
        editable_widget_types = (ui.Entry, ui.Text, ui.Spinbox, widgets.Entry, widgets.Combobox)
        return isinstance(widget, editable_widget_types)

    def _on_grid_delete(self, _event):
        """Meldet Delete/Backspace für Zellenleeren im Zellauswahlmodus."""
        if self._has_active_popup():
            return EventResult.HANDLED
        return self._emit_intent(UiIntent.GRID_DELETE_CELL, event=_event)

    def _on_escape(self, _event):
        """Meldet Esc-Shortcut als Intent an den Orchestrator."""
        if self._has_active_popup():
            ScrollablePopupWindow.close_active_popup()
            self._sync_popup_sessions_from_windows()
            return EventResult.HANDLED
        return self._emit_intent(UiIntent.SHORTCUT_ESCAPE, event=_event)

    def _on_ctrl_enter(self, _event):
        """Meldet Strg+Enter als expliziten Edit-Commit-Intent."""
        if self._has_active_popup():
            return None
        selection_level = getattr(getattr(self.app, "ui_state", None), "selection_level", "")
        column_level = getattr(getattr(self.app, "ui_state", None), "SELECTION_LEVEL_COLUMN", "column")
        if selection_level == column_level:
            return self._emit_intent(UiIntent.SHORTCUT_COMMIT_COLUMN, event=_event)
        return self._emit_intent(UiIntent.SHORTCUT_COMMIT_EDIT, event=_event)

    def _on_search_open(self, _event):
        """Meldet Strg+F als Intent, um die Einheitensuche zu öffnen."""
        if self._has_active_popup():
            return EventResult.HANDLED
        return self._emit_intent(UiIntent.SEARCH_OPEN, event=_event)

    def _on_find_previous(self, _event):
        """Meldet Umschalt+Enter als Intent für den vorherigen Suchtreffer."""
        if self._has_active_popup():
            return EventResult.HANDLED
        return self._emit_intent(UiIntent.SHORTCUT_FIND_PREVIOUS, event=_event)

    def _on_ctrl_c(self, event):
        """Meldet globales Copy-Shortcut als Intent an den Orchestrator."""
        return self._emit_intent(UiIntent.SHORTCUT_COPY, event=event)

    def _on_ctrl_v(self, event):
        """Meldet globales Paste-Shortcut als Intent an den Orchestrator."""
        return self._emit_intent(UiIntent.SHORTCUT_PASTE, event=event)
