"""Tests für den UB-Rahmen im Kursgitter (`GridRenderer._apply_ub_border`).

Der UB-Rahmen darf den Auswahlrahmen nicht verdecken: UB nutzt das Token
``secondary``, die Auswahl ``selection_bg``. Geprüft werden der Stilweg einer
UB-Zelle (ausgewählt/nicht ausgewählt) und dass beide Tokens in jedem Theme
tatsächlich verschiedene Farben haben. Synthetische Spalten, keine Kursdaten.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from bw_gui.theming import THEME_ORDER
from bw_gui.theming._theme_manager import get_theme

import kursplaner.adapters.gui.grid_renderer as module
import kursplaner.adapters.gui.ui_theme  # noqa: F401  (registriert die Kursplaner-Themes)
from kursplaner.adapters.gui.grid_renderer import GridRenderer
from kursplaner.core.domain.unterrichtsbesuch_policy import UB_LESSON_KEY
from tests.day_column_factory import make_day_column


class _CellStub:
    def __init__(self) -> None:
        self.config: dict = {}

    def configure(self, **kwargs) -> None:
        self.config.update(kwargs)


def _border_tokens(monkeypatch, *, selected: bool) -> list[str]:
    tokens: list[str] = []
    monkeypatch.setattr(module, "theme_widget_border", lambda _w, **kw: tokens.append(kw["color_token"]))
    day = make_day_column(row_index=0, datum="18-02-26", yaml={UB_LESSON_KEY: "[[UB Mathe]]"})
    assert day.is_ub()
    selected_cell = SimpleNamespace(field_key="Inhalt", day_index=0) if selected else None
    renderer = object.__new__(GridRenderer)
    renderer.app = SimpleNamespace(day_columns=[day], ui_state=SimpleNamespace(selected_cell=selected_cell))
    renderer._apply_cell_selection_style(_CellStub(), field_key="Inhalt", day_index=0)
    return tokens


def test_ub_cell_uses_secondary_border(monkeypatch):
    assert _border_tokens(monkeypatch, selected=False) == ["secondary"]


def test_selected_ub_cell_uses_selection_border(monkeypatch):
    assert _border_tokens(monkeypatch, selected=True) == ["selection_bg"]


@pytest.mark.parametrize("theme_key", list(THEME_ORDER))
def test_ub_border_colour_differs_from_selection_in_every_theme(theme_key):
    theme = get_theme(theme_key)
    assert theme["secondary"].lower() != theme["selection_bg"].lower()
