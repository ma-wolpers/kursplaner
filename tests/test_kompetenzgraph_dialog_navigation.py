"""Regressionstest gegen die Navigations-Ruckelei: Klick/Pfeiltasten dürfen View/Layout nie neu berechnen.

`KompetenzGraphDialog` wird bewusst NICHT über `__init__` konstruiert (das
würde einen echten Tk-Root samt vollständigem `load_result`/Usecase-Setup
erfordern) -- stattdessen wird nur die für die Redraw-Pfad-Entscheidung
relevante Teilmenge an Attributen über `object.__new__` gesetzt, dasselbe
Stub-Muster wie in `tests/test_grid_renderer_column_mount.py`.
"""

from __future__ import annotations

from types import SimpleNamespace

import kursplaner.adapters.gui.kompetenzgraph_dialog as dialog_module
from kursplaner.adapters.gui.kompetenzgraph_dialog import KompetenzGraphDialog
from kursplaner.adapters.gui.kompetenzgraph_ui_state import KompetenzGraphUiState
from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphFilter, KompetenzGraphVisibleSet
from kursplaner.core.domain.kompetenzgraph_layout import GraphNodePosition, KompetenzGraphLayout
from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from kursplaner.core.domain.kompetenzgraph_view import KompetenzGraphView
from tests.kompetenzgraph_test_support import make_node


class _CountingViewUsecase:
    """Zählt `execute()`-Aufrufe, liefert immer dieselbe fest vorgegebene View zurück."""

    def __init__(self, view: KompetenzGraphView):
        self._view = view
        self.execute_call_count = 0

    def execute(self, *_args, **_kwargs) -> KompetenzGraphView:
        self.execute_call_count += 1
        return self._view


class _RecordingRenderer:
    """Zählt `render()`-Aufrufe, ohne echtes Canvas-Zeichnen."""

    def __init__(self):
        self.render_call_count = 0

    def render(self, *_args, **_kwargs) -> None:
        self.render_call_count += 1


def _build_dialog_stub() -> KompetenzGraphDialog:
    node_a = make_node("A")
    node_b = make_node("B")
    snapshot = build_kompetenz_graph_snapshot([node_a, node_b], [])
    visible = KompetenzGraphVisibleSet(primary_ids=frozenset({"A", "B"}))
    view = KompetenzGraphView(visible=visible, visible_bereich_ids=frozenset())
    layout = KompetenzGraphLayout(
        positions={"A": GraphNodePosition(x=0.0, y=0.0), "B": GraphNodePosition(x=200.0, y=0.0)},
        unresolved_marker_positions={},
    )

    dialog = object.__new__(KompetenzGraphDialog)
    dialog._snapshot = snapshot
    dialog._compute_view_usecase = _CountingViewUsecase(view)
    dialog._state = KompetenzGraphUiState(filter=KompetenzGraphFilter(), selected_id="A")
    dialog._last_view = view
    dialog._last_layout = layout
    dialog._renderer = _RecordingRenderer()
    dialog._zoom_pan = SimpleNamespace(reapply_label_visibility=lambda: None)
    dialog._sidebar_scroll = SimpleNamespace(bind_mousewheel_to_content=lambda *_args, **_kwargs: None)
    dialog._detail_panel = SimpleNamespace(render=lambda _node: None, frame=None)
    dialog.canvas = SimpleNamespace(focus_set=lambda: None)
    return dialog


def _patch_layout_call_counter(monkeypatch) -> list[int]:
    """Ersetzt `compute_layered_layout` im Dialog-Modul durch eine zählende Variante, liefert den Zähler als 1-elementige Liste."""
    call_count = [0]

    def _counting_compute_layered_layout(*_args, **_kwargs):
        call_count[0] += 1
        return KompetenzGraphLayout(positions={}, unresolved_marker_positions={})

    monkeypatch.setattr(dialog_module, "compute_layered_layout", _counting_compute_layered_layout)
    return call_count


def test_click_selection_does_not_recompute_view_or_layout(monkeypatch):
    dialog = _build_dialog_stub()
    layout_call_count = _patch_layout_call_counter(monkeypatch)

    dialog._on_node_selected("B")

    assert dialog._compute_view_usecase.execute_call_count == 0
    assert layout_call_count[0] == 0
    assert dialog._renderer.render_call_count == 1
    assert dialog._state.selected_id == "B"


def test_arrow_navigation_does_not_recompute_view_or_layout(monkeypatch):
    dialog = _build_dialog_stub()
    layout_call_count = _patch_layout_call_counter(monkeypatch)
    monkeypatch.setattr(dialog_module, "recenter_on_node", lambda *_args, **_kwargs: None)

    dialog._on_arrow_direction((1.0, 0.0))  # Richtung Osten -- Knoten "B" liegt bei x=200, y=0

    assert dialog._compute_view_usecase.execute_call_count == 0
    assert layout_call_count[0] == 0
    assert dialog._renderer.render_call_count == 1
    assert dialog._state.selected_id == "B"


def test_filter_change_does_recompute_view_and_layout(monkeypatch):
    """Gegenprobe zu den beiden Tests oben: hier MUSS die Pipeline laufen (mindestens einmal, im
    Unterschied zur harten `== 0`-Garantie bei reiner Selektion; `_refresh()` prüft die
    Selektions-Gültigkeit bereits vor `_recompute_and_redraw()` und ruft die View-Berechnung
    daher vorhersehbar mehrfach auf -- Anzahl ist hier nicht der Testgegenstand)."""
    dialog = _build_dialog_stub()
    layout_call_count = _patch_layout_call_counter(monkeypatch)

    dialog._on_filter_changed(KompetenzGraphFilter(jahrgang=8))

    assert dialog._compute_view_usecase.execute_call_count >= 1
    assert layout_call_count[0] >= 1
    assert dialog._renderer.render_call_count == 1
