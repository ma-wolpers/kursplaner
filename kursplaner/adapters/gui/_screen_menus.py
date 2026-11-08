"""Menu items, intent emission and hover help of the main window (ScreenBuilder mixin).

Split out of screen_builder.py (file-size rule); method bodies unchanged."""

from __future__ import annotations

from bw_gui.menu import MenuItem as SharedMenuItem
from bw_gui.runtime import ui
from bw_gui.shortcuts import compose_hover_text_for_intent as compose_shared_hover_text_for_intent
from bw_gui.shortcuts import compose_menu_label

from bw_libs.ui_contract.keybinding import KeybindingRegistry
from kursplaner.adapters.gui._screen_shortcuts import RUNTIME_DEBUG_INTENT
from kursplaner.adapters.gui.detail_surface import DetailSurface
from kursplaner.adapters.gui.hover_tooltip import HoverTooltip
from kursplaner.adapters.gui.ui_intents import UiIntent


class ScreenMenusMixin:
    """Menu items, intent emission and hover help of the main window (ScreenBuilder mixin)."""

    _runtime_shortcuts: KeybindingRegistry
    """Laufzeit-Registry der Kürzel, gesetzt von ``ScreenBuilder.__init__`` (für den Typprüfer deklariert)."""

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
            SharedMenuItem(
                type="command",
                label=self._menu_label("Neu", UiIntent.TOOLBAR_NEW),
                command=lambda: self._emit_intent(UiIntent.TOOLBAR_NEW),
            ),
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
            SharedMenuItem(
                type="command",
                label=self._menu_label("Undo", UiIntent.TOOLBAR_UNDO),
                command=lambda: self._emit_intent(UiIntent.TOOLBAR_UNDO),
            ),
            SharedMenuItem(
                type="command",
                label=self._menu_label("Redo", UiIntent.TOOLBAR_REDO),
                command=lambda: self._emit_intent(UiIntent.TOOLBAR_REDO),
            ),
            SharedMenuItem(type="submenu", label="Letzte Änderungen", items=self._recent_changes_menu_items()),
        )

    def _menu_items_action(self):
        return (
            SharedMenuItem(
                type="command",
                label=self._menu_label("Einheit kopieren", UiIntent.SHORTCUT_COPY),
                command=lambda: self._emit_intent(UiIntent.TOOLBAR_COPY),
            ),
            SharedMenuItem(
                type="command",
                label=self._menu_label("Einheit einfügen", UiIntent.SHORTCUT_PASTE),
                command=lambda: self._emit_intent(UiIntent.TOOLBAR_PASTE),
            ),
            SharedMenuItem(
                type="command",
                label=self._menu_label("Exportieren als...", UiIntent.TOOLBAR_EXPORT_AS),
                command=lambda: self._emit_intent(UiIntent.TOOLBAR_EXPORT_AS),
            ),
            SharedMenuItem(
                type="command",
                label=self._menu_label("Markdown finden…", UiIntent.TOOLBAR_FIND),
                command=lambda: self._emit_intent(UiIntent.TOOLBAR_FIND),
            ),
            SharedMenuItem(type="separator"),
            SharedMenuItem(
                type="command",
                label=self._menu_label("Einheit leeren", UiIntent.TOOLBAR_CLEAR),
                command=lambda: self._emit_intent(UiIntent.TOOLBAR_CLEAR),
            ),
            SharedMenuItem(
                type="command",
                label=self._menu_label("Einheit umbenennen…", UiIntent.TOOLBAR_RENAME),
                command=lambda: self._emit_intent(UiIntent.TOOLBAR_RENAME),
            ),
            SharedMenuItem(
                type="command",
                label="Schatteneinheiten anzeigen…",
                command=lambda: self._emit_intent(UiIntent.SHOW_SHADOW_LESSONS),
            ),
            SharedMenuItem(
                type="command",
                label=self._menu_label(
                    "Kontextaktion: UB markieren / Ausfall zurücknehmen", UiIntent.TOGGLE_RESUME_OR_UB
                ),
                command=lambda: self._emit_intent(UiIntent.TOGGLE_RESUME_OR_UB),
            ),
            SharedMenuItem(
                type="command",
                label=self._menu_label("Als Hospitation markieren", UiIntent.TOOLBAR_HOSPITATION),
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
                on_toggle=lambda on: self._set_var_and_emit(
                    self.app.expand_long_rows_var, on, UiIntent.TOGGLE_EXPAND_MODE
                ),
            ),
            SharedMenuItem(
                type="command",
                label=self._menu_label("Spaltenarten anzeigen/verstecken…", UiIntent.OPEN_COLUMN_VISIBILITY_SETTINGS),
                command=lambda: self._emit_intent(UiIntent.OPEN_COLUMN_VISIBILITY_SETTINGS),
            ),
            SharedMenuItem(
                type="switch",
                label=self._menu_label("Sequenzfelder anzeigen", UiIntent.TOGGLE_SEQUENCE_FIELDS_VISIBLE),
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
                label=self._menu_label("UB-Übersicht anzeigen", UiIntent.SHOW_UB_ACHIEVEMENTS),
                command=lambda: self._emit_intent(UiIntent.SHOW_UB_ACHIEVEMENTS),
            ),
            SharedMenuItem(
                type="command",
                label=self._menu_label("Shortcut-Übersicht anzeigen", UiIntent.SHOW_SHORTCUT_OVERVIEW),
                command=lambda: self._emit_intent(UiIntent.SHOW_SHORTCUT_OVERVIEW),
            ),
            SharedMenuItem(
                type="command",
                label=self._menu_label("Shortcut-Runtime-Debug anzeigen", RUNTIME_DEBUG_INTENT),
                command=self._open_shortcut_runtime_debug_dialog,
            ),
            SharedMenuItem(type="separator"),
            SharedMenuItem(
                type="command",
                label=self._menu_label("Kompetenznetz anzeigen…", UiIntent.SHOW_KOMPETENZGRAPH),
                command=lambda: self._emit_intent(UiIntent.SHOW_KOMPETENZGRAPH),
            ),
            SharedMenuItem(
                type="switch",
                label=self._menu_label("Sequenzleiter", UiIntent.TOGGLE_SEQUENCE_LADDER_VIEW),
                checked=self.app.ui_state.detail_surface is DetailSurface.LADDER,
                # Der Intent schaltet selbst um; der angefragte Wert ist immer „nicht gesetzt“.
                on_toggle=lambda _on: self._emit_intent(UiIntent.TOGGLE_SEQUENCE_LADDER_VIEW),
            ),
        )

    def _menu_label(self, text: str, intent: str) -> str:
        """Menütext mit der Taste der Bindung von *intent* (Registry, dieselbe Quelle wie die Tooltips)."""
        return compose_menu_label(text, self._runtime_shortcuts.shortcut_for_intent(intent))

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

    def _add_help(
        self,
        widget: ui.Widget,
        text: str,
        *,
        intent: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> HoverTooltip | None:
        """Registriert bei Bedarf eine Hover-Hilfe für ein Widget.

        Mit *intent* hängt die Hilfe die Taste der passenden Bindung an (``metadata``
        unterscheidet Bindungen desselben Intents, z. B. die Verschieberichtung); der
        Hilfetext selbst nennt keine Taste.
        """
        base_text = text.strip()
        if not base_text:
            return None
        tooltip = HoverTooltip(widget, self._intent_help_text(base_text, intent, metadata))
        if intent is not None:
            self._intent_help_tooltips.append((tooltip, base_text, intent, metadata))
        self.app.hover_tooltips.append(tooltip)
        return tooltip

    def _intent_help_text(self, base_text: str, intent: str | None, metadata: dict[str, str] | None) -> str:
        """Hilfetext plus Taste der Bindung – einzige Zusammensetzung für Intent-Hilfen."""
        if not intent:
            return base_text
        return compose_shared_hover_text_for_intent(
            base_text, intent=intent, shortcuts=self._runtime_shortcuts, metadata=metadata
        )

    def set_intent_help_text(self, tooltip: HoverTooltip, base_text: str) -> None:
        """Tauscht den Hilfetext einer Intent-Hilfe (z. B. Ausfall ↔ zurücknehmen); die Taste bleibt."""
        for index, (known, _old_text, intent, metadata) in enumerate(self._intent_help_tooltips):
            if known is tooltip:
                self._intent_help_tooltips[index] = (known, base_text, intent, metadata)
                tooltip.text = self._intent_help_text(base_text, intent, metadata)
                return
        tooltip.text = base_text

    def _refresh_intent_help_tooltips(self) -> None:
        """Aktualisiert Intent-basierte Hover-Texte nach Shortcut-Registrierung."""

        for tooltip, base_text, intent, metadata in list(self._intent_help_tooltips):
            try:
                tooltip.text = self._intent_help_text(base_text, intent, metadata)
            except Exception:
                continue
