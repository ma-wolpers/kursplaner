"""Menütexte zeigen die Taste ihrer Bindung (eine Quelle), Anzeige deutsch (synthetisch, ohne Tk).

Die Erwartung hält die bisherigen Menütexte fest; neu tragen „Markdown finden…“,
„Einheit leeren“, „Einheit umbenennen…“ und „Als Hospitation markieren“ ihre vorhandene
Taste (vorher fehlte der Hinweis).
"""

from __future__ import annotations

from types import SimpleNamespace

from bw_gui.contracts import KeySpec

from kursplaner.adapters.gui._screen_menus import ScreenMenusMixin
from kursplaner.adapters.gui._screen_shortcuts import RUNTIME_DEBUG_INTENT
from kursplaner.adapters.gui.shortcut_guide import load_shortcut_guide_entries


class _Var:
    def get(self):
        return False

    def set(self, _value):
        return None


class _Resolver:
    """Erste Bindung je Intent wie `KeybindingRegistry.shortcut_for_intent` (Guide zuerst gebunden)."""

    def __init__(self):
        self._keys: dict[str, KeySpec] = {}
        for entry in load_shortcut_guide_entries():
            self._keys.setdefault(entry.intent, entry.key)
        self._keys.setdefault(RUNTIME_DEBUG_INTENT, KeySpec.parse("Ctrl+Shift+D"))

    def shortcut_for_intent(self, intent, **_kw):
        return self._keys.get(intent)


def _menus():
    menus = object.__new__(ScreenMenusMixin)
    menus._runtime_shortcuts = _Resolver()
    menus._open_shortcut_runtime_debug_dialog = lambda: None
    menus.app = SimpleNamespace(
        expand_long_rows_var=_Var(),
        sequence_fields_visible_var=_Var(),
        auto_scroll_next_unit_var=_Var(),
        action_controller=SimpleNamespace(list_recent_change_labels=lambda limit: []),
        destroy=lambda: None,
    )
    return menus


def _labels(items):
    return [item.label for item in items if item.type not in {"separator"}]


def test_menu_labels_take_keys_from_bindings():
    menus = _menus()
    assert _labels(menus._menu_items_file()) == ["Neu (Strg+N)", "Lesson-Index neu aufbauen", "Beenden"]
    assert _labels(menus._menu_items_edit()) == ["Undo (Strg+Z)", "Redo (Strg+Y)", "Letzte Änderungen"]
    assert _labels(menus._menu_items_action()) == [
        "Einheit kopieren (Strg+C)",
        "Einheit einfügen (Strg+V)",
        "Exportieren als... (Strg+P)",
        "Markdown finden… (Strg+G)",
        "Einheit leeren (Strg+Entf)",
        "Einheit umbenennen… (Strg+J)",
        "Schatteneinheiten anzeigen…",
        "Kontextaktion: UB markieren / Ausfall zurücknehmen (Strg+B)",
        "Als Hospitation markieren (Strg+O)",
        "Stundenplanänderung…",
    ]
    assert _labels(menus._menu_items_view()) == [
        "Lange Zeilen aufgeklappt",
        "Spaltenarten anzeigen/verstecken… (Strg+L)",
        "Sequenzfelder anzeigen (Strg+Shift+S)",
        "Auto-Scroll zur nächsten Einheit",
        "UB-Übersicht anzeigen (Strg+Shift+U)",
        "Shortcut-Übersicht anzeigen (Strg+H)",
        "Shortcut-Runtime-Debug anzeigen (Strg+Shift+D)",
        "Kompetenznetz anzeigen… (Strg+Shift+K)",
        "Sequenzleiter öffnen… (Strg+Shift+L)",
    ]


def test_guide_display_is_derived_from_the_key():
    entries = load_shortcut_guide_entries()
    assert len(entries) == 29
    by_intent = {entry.intent: entry for entry in entries}
    assert by_intent["toolbar.clear"].display_shortcut == "Strg+Entf"
    assert all(entry.is_ctrl_shortcut for entry in entries)
