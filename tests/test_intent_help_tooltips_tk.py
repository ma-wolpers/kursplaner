"""Intent-Hilfen lesen ihre Taste beim Anzeigen (bw-gui ``text_provider``), nicht beim Bauen.

Die Toolbar-Hilfen entstehen vor der Kürzel-Registrierung; früher frischte eine eigene
Liste sie danach auf. Synthetisch: ein Resolver statt der echten Registry, ein Label
im geteilten Off-Screen-Root.
"""

from __future__ import annotations

from types import SimpleNamespace

from bw_gui.contracts import KeySpec
from bw_gui.runtime import widgets

from kursplaner.adapters.gui._screen_menus import ScreenMenusMixin


class _LateResolver:
    """Kennt eine Taste erst, nachdem sie „registriert“ wurde (wie nach ``build_ui``)."""

    def __init__(self):
        self.keys: dict[str, KeySpec] = {}

    def shortcut_for_intent(self, intent, **_kw):
        return self.keys.get(intent)


def _menus():
    menus = object.__new__(ScreenMenusMixin)
    menus._runtime_shortcuts = _LateResolver()
    menus.app = SimpleNamespace(hover_tooltips=[])
    return menus


def test_help_built_before_the_binding_shows_its_key(tk_root):
    menus = _menus()
    tooltip = menus._add_help(widgets.Label(tk_root), "Ausfall markieren", intent="demo.ausfall")
    assert tooltip.current_text() == "Ausfall markieren"
    menus._runtime_shortcuts.keys["demo.ausfall"] = KeySpec.parse("Ctrl+Shift+A")
    assert tooltip.current_text().startswith("Ausfall markieren")
    assert tooltip.current_text().endswith("Strg+Shift+A")


def test_swapped_help_text_keeps_the_key(tk_root):
    menus = _menus()
    menus._runtime_shortcuts.keys["demo.ausfall"] = KeySpec.parse("Ctrl+Shift+A")
    tooltip = menus._add_help(widgets.Label(tk_root), "Ausfall markieren", intent="demo.ausfall")
    menus.set_intent_help_text(tooltip, " Ausfall zurücknehmen ")
    assert tooltip.text == "Ausfall zurücknehmen"
    assert tooltip.current_text().startswith("Ausfall zurücknehmen")
    assert tooltip.current_text().endswith("Strg+Shift+A")


def test_help_without_intent_stays_plain(tk_root):
    menus = _menus()
    tooltip = menus._add_help(widgets.Label(tk_root), "Nur Text")
    assert tooltip.text_provider is None
    assert tooltip.current_text() == "Nur Text"
    assert menus.app.hover_tooltips == [tooltip]
