"""Tests für `kompetenzgraph_canvas_edges.py::KompetenzGraphEdgeRenderer.draw_classification_edges()`.

Nutzt einen echten `tk.Canvas` (eigener `tk.Toplevel` pro Test, siehe
`test_kompetenzgraph_canvas_recenter.py` für dasselbe Isolations-Muster gegenüber der
session-weiten `tk_root`-Fixture) -- Canvas-Item-Introspektion (`find_all()`) ist reines
Tcl/Tk-Verhalten.
"""

from __future__ import annotations

import tkinter as tk

from kursplaner.adapters.gui.kompetenzgraph_canvas_edges import KompetenzGraphEdgeRenderer
from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphVisibleSet
from kursplaner.core.domain.kompetenzgraph_layout import GraphNodePosition, KompetenzGraphLayout
from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from kursplaner.core.domain.kompetenzgraph_view import KompetenzGraphView
from tests.kompetenzgraph_test_support import make_bereich, make_node

_COMPETENCY_HALF_EXTENT = (46.0, 44.0)
_BEREICH_HALF_EXTENT = (85.0, 19.0)


def _make_canvas(tk_root) -> tk.Canvas:
    return tk.Canvas(tk.Toplevel(tk_root))


def _build_layout(positions: dict[str, tuple[float, float]]) -> KompetenzGraphLayout:
    return KompetenzGraphLayout(
        positions={node_id: GraphNodePosition(x=x, y=y) for node_id, (x, y) in positions.items()},
        unresolved_marker_positions={},
    )


def _build_view(*, primary_ids: frozenset[str], visible_bereich_ids: frozenset[str]) -> KompetenzGraphView:
    return KompetenzGraphView(
        visible=KompetenzGraphVisibleSet(primary_ids=primary_ids, context_ids=frozenset()),
        visible_bereich_ids=visible_bereich_ids,
    )


def test_prozessbereich_edges_hidden_by_default(tk_root):
    node = make_node("A", primarer_bereich_id="I-Primary", prozessbereich_ids=("P-Eins", "P-Zwei"))
    snapshot = build_kompetenz_graph_snapshot(
        [node], [make_bereich("I-Primary"), make_bereich("P-Eins"), make_bereich("P-Zwei")]
    )
    view = _build_view(primary_ids=frozenset({"A"}), visible_bereich_ids=frozenset({"I-Primary", "P-Eins", "P-Zwei"}))
    layout = _build_layout({"A": (0.0, 0.0), "I-Primary": (0.0, -200.0), "P-Eins": (100.0, -200.0), "P-Zwei": (200.0, -200.0)})
    canvas = _make_canvas(tk_root)
    renderer = KompetenzGraphEdgeRenderer(
        canvas, competency_half_extent=_COMPETENCY_HALF_EXTENT, bereich_half_extent=_BEREICH_HALF_EXTENT
    )

    renderer.draw_classification_edges(snapshot, view, layout, selected_id=None)

    lines = [item for item in canvas.find_all() if canvas.type(item) == "line"]
    assert len(lines) == 1  # nur die primäre Kante


def test_prozessbereich_edges_visible_for_selected_competency_node(tk_root):
    node_a = make_node("A", primarer_bereich_id="I-Primary", prozessbereich_ids=("P-Eins", "P-Zwei"))
    node_b = make_node("B", primarer_bereich_id="I-Primary", prozessbereich_ids=("P-Eins",))
    snapshot = build_kompetenz_graph_snapshot(
        [node_a, node_b], [make_bereich("I-Primary"), make_bereich("P-Eins"), make_bereich("P-Zwei")]
    )
    view = _build_view(
        primary_ids=frozenset({"A", "B"}), visible_bereich_ids=frozenset({"I-Primary", "P-Eins", "P-Zwei"})
    )
    layout = _build_layout(
        {
            "A": (0.0, 0.0),
            "B": (150.0, 0.0),
            "I-Primary": (0.0, -200.0),
            "P-Eins": (100.0, -200.0),
            "P-Zwei": (200.0, -200.0),
        }
    )
    canvas = _make_canvas(tk_root)
    renderer = KompetenzGraphEdgeRenderer(
        canvas, competency_half_extent=_COMPETENCY_HALF_EXTENT, bereich_half_extent=_BEREICH_HALF_EXTENT
    )

    renderer.draw_classification_edges(snapshot, view, layout, selected_id="A")

    lines = [item for item in canvas.find_all() if canvas.type(item) == "line"]
    # 2 primäre Kanten (A, B) + 2 Prozessbereich-Kanten NUR für A (P-Eins, P-Zwei) -- B's eigener
    # Prozessbereich (P-Eins) darf trotz Überschneidung mit A's Prozessbereichen nicht erscheinen.
    assert len(lines) == 4


def test_prozessbereich_edges_visible_for_selected_bereich_hub(tk_root):
    node_a = make_node("A", primarer_bereich_id="I-Primary", prozessbereich_ids=("P-Eins",))
    node_b = make_node("B", primarer_bereich_id="I-Primary", prozessbereich_ids=("P-Zwei",))
    snapshot = build_kompetenz_graph_snapshot(
        [node_a, node_b], [make_bereich("I-Primary"), make_bereich("P-Eins"), make_bereich("P-Zwei")]
    )
    view = _build_view(
        primary_ids=frozenset({"A", "B"}), visible_bereich_ids=frozenset({"I-Primary", "P-Eins", "P-Zwei"})
    )
    layout = _build_layout(
        {
            "A": (0.0, 0.0),
            "B": (150.0, 0.0),
            "I-Primary": (0.0, -200.0),
            "P-Eins": (100.0, -200.0),
            "P-Zwei": (200.0, -200.0),
        }
    )
    canvas = _make_canvas(tk_root)
    renderer = KompetenzGraphEdgeRenderer(
        canvas, competency_half_extent=_COMPETENCY_HALF_EXTENT, bereich_half_extent=_BEREICH_HALF_EXTENT
    )

    renderer.draw_classification_edges(snapshot, view, layout, selected_id="P-Eins")

    lines = [item for item in canvas.find_all() if canvas.type(item) == "line"]
    # 2 primäre Kanten (A, B) + genau 1 Prozessbereich-Kante (A -> P-Eins) -- B referenziert
    # P-Eins nicht, darf also keine Kante zu diesem selektierten Hub zeigen.
    assert len(lines) == 3


def test_prozessbereich_edges_are_drawn_exactly_once(tk_root):
    node = make_node("A", primarer_bereich_id="I-Primary", prozessbereich_ids=("P-Eins", "P-Zwei", "P-Drei"))
    snapshot = build_kompetenz_graph_snapshot(
        [node],
        [make_bereich("I-Primary"), make_bereich("P-Eins"), make_bereich("P-Zwei"), make_bereich("P-Drei")],
    )
    view = _build_view(
        primary_ids=frozenset({"A"}), visible_bereich_ids=frozenset({"I-Primary", "P-Eins", "P-Zwei", "P-Drei"})
    )
    layout = _build_layout(
        {
            "A": (0.0, 0.0),
            "I-Primary": (0.0, -200.0),
            "P-Eins": (100.0, -200.0),
            "P-Zwei": (200.0, -200.0),
            "P-Drei": (300.0, -200.0),
        }
    )
    canvas = _make_canvas(tk_root)
    renderer = KompetenzGraphEdgeRenderer(
        canvas, competency_half_extent=_COMPETENCY_HALF_EXTENT, bereich_half_extent=_BEREICH_HALF_EXTENT
    )

    renderer.draw_classification_edges(snapshot, view, layout, selected_id="A")

    lines = [item for item in canvas.find_all() if canvas.type(item) == "line"]
    # 1 primäre Kante + genau 3 eindeutige Prozessbereich-Kanten, keine davon doppelt gezeichnet.
    assert len(lines) == 4
