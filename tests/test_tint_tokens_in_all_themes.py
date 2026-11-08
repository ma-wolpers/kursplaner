"""Jede Kursplaner-Tönung ist in jedem Theme auflösbar (bw-gui wirft bei unbekannten Tokens).

Regressionsschutz für die „nächste Einheit“-Markierung, die `info_soft` verlangte, das nur
zwei Themes kannten – in allen anderen entstand still ein Grau.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from bw_gui.theming import THEME_ORDER, tinted_color

import kursplaner.adapters.gui.grid_renderer as grid_renderer_module
import kursplaner.adapters.gui.ui_theme  # noqa: F401  (registriert die Kursplaner-Themes)
from kursplaner.adapters.gui.grid_renderer import GridRenderer
from kursplaner.adapters.gui.lesson_kind_tints import LESSON_KIND_TINTS
from kursplaner.adapters.gui.toolbar_icon_styler import _STYLE_TINT

_HEADER_STATES = (*LESSON_KIND_TINTS, "unresolved", "next_unit", "normal")


@pytest.mark.parametrize("theme_key", list(THEME_ORDER))
def test_lesson_kind_and_toolbar_tints_resolve(theme_key):
    for tint in LESSON_KIND_TINTS.values():
        tinted_color(tint.color_tint, degree=tint.degree, base_token=tint.base_token, theme_key=theme_key)
    for color in filter(None, _STYLE_TINT.values()):
        tinted_color(color, theme_key=theme_key)


@pytest.mark.parametrize("theme_key", list(THEME_ORDER))
def test_every_header_state_resolves(monkeypatch, theme_key):
    def resolve_tinted(_label, color, *, degree=0.5, base_token="bg_panel", **_kw):
        tinted_color(color, degree=degree, base_token=base_token, theme_key=theme_key)

    def resolve_token(_label, *, bg_token=None, **_kw):
        tinted_color(bg_token, degree=0.0, base_token=bg_token, theme_key=theme_key)

    monkeypatch.setattr(grid_renderer_module, "theme_label_tinted", resolve_tinted)
    monkeypatch.setattr(grid_renderer_module, "theme_label_token", resolve_token)
    monkeypatch.setattr(
        grid_renderer_module,
        "apply_label_tint",
        lambda label, tint: resolve_tinted(label, tint.color_tint, degree=tint.degree, base_token=tint.base_token),
    )
    renderer = object.__new__(GridRenderer)
    renderer.app = SimpleNamespace()
    for state in _HEADER_STATES:
        renderer._apply_header_color(object(), state)
