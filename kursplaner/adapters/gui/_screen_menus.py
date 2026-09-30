"""Menu items, intent emission and hover help of the main window (ScreenBuilder mixin).

Split out of screen_builder.py (file-size rule); method bodies unchanged."""

from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.menu import MenuItem as SharedMenuItem
from bw_gui.runtime import ui
from bw_gui.shortcuts import compose_hover_text_for_intent as compose_shared_hover_text_for_intent

from kursplaner.adapters.gui.hover_tooltip import HoverTooltip
from kursplaner.adapters.gui.ui_intents import UiIntent


class ScreenMenusMixin:
    """Menu items, intent emission and hover help of the main window (ScreenBuilder mixin)."""

    def _set_theme_from_menu(self, theme_key: str) -> None:
        self.app.theme_var.set(theme_key)
        self.app._on_theme_changed()

    def _recent_changes_menu_items(self):
        labels = self.app.action_controller.list_recent_change_labels(limit=5)
        if not labels:
            return (SharedMenuItem(type="disabled", label="Keine Änderungen"),)

        return tuple(
            SharedMenuItem(
                type="command",
                label=f"{idx + 1}. {(label.strip() or 'Änderung')}",
                command=lambda recent_index=idx: self._emit_intent(
                    UiIntent.EDIT_UNDO_TO_RECENT_INDEX,
                    recent_index=recent_index,
                ),
            )
            for idx, label in enumerate(labels)
        )

    def _menu_items_file(self):
        return (
            SharedMenuItem(type="command", label="Neu (Strg+N)", command=lambda: self._emit_intent(UiIntent.TOOLBAR_NEW)),
            SharedMenuItem(
                type="command",
                label="Lesson-Index neu aufbauen",
                command=lambda: self._emit_intent(UiIntent.REBUILD_LESSON_INDEX),
            ),
            SharedMenuItem(type="separator"),
            SharedMenuItem(type="command", label="Beenden", command=self.app.destroy),
        )

    def _menu_items_edit(self):
        return (
            SharedMenuItem(type="command", label="Undo (Strg+Z)", command=lambda: self._emit_intent(UiIntent.TOOLBAR_UNDO)),
            SharedMenuItem(type="command", label="Redo (Strg+Y)", command=lambda: self._emit_intent(UiIntent.TOOLBAR_REDO)),
            SharedMenuItem(type="submenu", label="Letzte Änderungen", items=self._recent_changes_menu_items()),
        )

    def _menu_items_action(self):
        return (
            SharedMenuItem(type="command", label="Einheit kopieren (Strg+C)", command=lambda: self._emit_intent(UiIntent.TOOLBAR_COPY)),
            SharedMenuItem(type="command", label="Einheit einfügen (Strg+V)", command=lambda: self._emit_intent(UiIntent.TOOLBAR_PASTE)),
            SharedMenuItem(type="command", label="Exportieren als... (Strg+P)", command=lambda: self._emit_intent(UiIntent.TOOLBAR_EXPORT_AS)),
            SharedMenuItem(type="command", label="Markdown finden…", command=lambda: self._emit_intent(UiIntent.TOOLBAR_FIND)),
            SharedMenuItem(type="separator"),
            SharedMenuItem(type="command", label="Einheit leeren", command=lambda: self._emit_intent(UiIntent.TOOLBAR_CLEAR)),
            SharedMenuItem(type="command", label="Einheit umbenennen…", command=lambda: self._emit_intent(UiIntent.TOOLBAR_RENAME)),
            SharedMenuItem(type="command", label="Schatteneinheiten anzeigen…", command=lambda: self._emit_intent(UiIntent.SHOW_SHADOW_LESSONS)),
            SharedMenuItem(
                type="command",
                label="Kontextaktion: UB markieren / Ausfall zurücknehmen (Strg+B)",
                command=lambda: self._emit_intent(UiIntent.TOGGLE_RESUME_OR_UB),
            ),
            SharedMenuItem(
                type="command",
                label="Als Hospitation markieren",
                command=lambda: self._emit_intent(UiIntent.TOOLBAR_HOSPITATION),
            ),
            SharedMenuItem(type="separator"),
            SharedMenuItem(
                type="command",
                label="Stundenplanänderung…",
                command=lambda: self._emit_intent(UiIntent.OPEN_TIMETABLE_CHANGE),
            ),
        )

    def _menu_items_view(self):
        return (
            SharedMenuItem(
                type="switch",
                label="Lange Zeilen aufgeklappt",
                checked=bool(self.app.expand_long_rows_var.get()),
                on_toggle=lambda on: self._set_var_and_emit(self.app.expand_long_rows_var, on, UiIntent.TOGGLE_EXPAND_MODE),
            ),
            SharedMenuItem(
                type="command",
                label="Spaltenarten anzeigen/verstecken… (Strg+L)",
                command=lambda: self._emit_intent(UiIntent.OPEN_COLUMN_VISIBILITY_SETTINGS),
            ),
            SharedMenuItem(
                type="switch",
                label="Sequenzfelder anzeigen (Strg+Shift+S)",
                checked=bool(self.app.sequence_fields_visible_var.get()),
                # The intent flips the variable itself (shared with Strg+Shift+S);
                # the requested value is always "not checked", so this is equivalent.
                on_toggle=lambda _on: self._emit_intent(UiIntent.TOGGLE_SEQUENCE_FIELDS_VISIBLE),
            ),
            SharedMenuItem(
                type="switch",
                label="Auto-Scroll zur nächsten Einheit",
                checked=bool(self.app.auto_scroll_next_unit_var.get()),
                on_toggle=self.app.auto_scroll_next_unit_var.set,
            ),
            SharedMenuItem(type="separator"),
            SharedMenuItem(
                type="command",
                label="UB-Übersicht anzeigen (Strg+Shift+U)",
                command=lambda: self._emit_intent(UiIntent.SHOW_UB_ACHIEVEMENTS),
            ),
            SharedMenuItem(
                type="command",
                label="Shortcut-Übersicht anzeigen (Strg+H)",
                command=lambda: self._emit_intent(UiIntent.SHOW_SHORTCUT_OVERVIEW),
            ),
            SharedMenuItem(
                type="command",
                label="Shortcut-Runtime-Debug anzeigen (Strg+Shift+D)",
                command=self._open_shortcut_runtime_debug_dialog,
            ),
            SharedMenuItem(type="separator"),
            SharedMenuItem(
                type="command",
                label="Kompetenznetz anzeigen… (Strg+Shift+K)",
                command=lambda: self._emit_intent(UiIntent.SHOW_KOMPETENZGRAPH),
            ),
        )

    def _set_var_and_emit(self, variable, value: bool, intent: str) -> None:
        """Apply a switch menu row: set the requested value, then let the intent act on it.

        Args:
            variable: BooleanVar mirroring the setting.
            value: The value requested by the switch (``MenuItem.on_toggle``).
            intent: Intent that applies the current variable value.
        """
        variable.set(bool(value))
        self._emit_intent(intent)

    def _emit_intent(self, intent: str, **payload):
        """Leitet ein View-Ereignis als Intent an die Orchestrierung weiter."""
        return self.app._handle_ui_intent(intent, **payload)

    def _ensure_tooltip_store(self):
        """Stellt sicher, dass Tooltip-Objekte am App-Lifecycle hängen."""
        if not hasattr(self.app, "hover_tooltips"):
            self.app.hover_tooltips = []

    def _add_help(self, widget: ui.Widget, text: str, *, intent: str | None = None) -> HoverTooltip | None:
        """Registriert bei Bedarf eine Hover-Hilfe für ein Widget."""
        base_text = text.strip()
        if not base_text:
            return None

        rendered_text = base_text
        if intent:
            rendered_text = compose_shared_hover_text_for_intent(
                base_text,
                intent=intent,
                shortcuts=self._runtime_shortcuts,
            )

        tooltip = HoverTooltip(widget, rendered_text)
        if intent is not None:
            self._intent_help_tooltips.append((tooltip, base_text, intent))
        self.app.hover_tooltips.append(tooltip)
        return tooltip

    def _refresh_intent_help_tooltips(self) -> None:
        """Aktualisiert Intent-basierte Hover-Texte nach Shortcut-Registrierung."""

        for tooltip, base_text, intent in list(self._intent_help_tooltips):
            try:
                tooltip.text = compose_shared_hover_text_for_intent(
                    base_text,
                    intent=intent,
                    shortcuts=self._runtime_shortcuts,
                )
            except Exception:
                continue
