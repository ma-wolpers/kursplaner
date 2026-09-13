"""Integrations-/Smoke-Test für `compute_layered_layout()` in realistischer Größenordnung.

Bewusst als Integrations-/Smoke-Test deklariert, NICHT als Ersatz für die feingranularen
Unit-/Regressionstests in `test_kompetenzgraph_layout.py`/`test_kompetenzgraph_layout_forces.py`/
`test_kompetenzgraph_canvas_edges.py` -- die einzelnen Eigenschaften (Spacing-Invariante,
Kanten-Sichtbarkeit, Prozessbereich-Isolation) bleiben durch diese dedizierten Tests abgesichert.
Dieser eine große Test sichert NUR das Zusammenspiel aller Teile auf realistischer Skala ab, wo
ein rein synthetisches Mini-Beispiel ein Interaktionsproblem (z. B. Performance-Budget-Grenzfall,
Sortier-Instabilität bei vielen Gleichständen) verdecken könnte.

Nutzt bewusst KEINE echten Vault-Daten -- Tests dürfen nicht von einem außerhalb des Repos
liegenden, persönlichen Ordner abhängen (nicht reproduzierbar auf anderen Maschinen/CI).
Stattdessen: eine synthetische Fixture, die die reale Informatik-Struktur zahlenmäßig nachbildet
(144 Knoten über 9 Bereiche, ~6 Hierarchieschichten, ca. zwei Drittel der Knoten mit mehreren
Prozessbereichen).
"""

from __future__ import annotations

import tkinter as tk

from kursplaner.adapters.gui.kompetenzgraph_canvas_edges import KompetenzGraphEdgeRenderer
from kursplaner.adapters.gui.kompetenzgraph_canvas_render import (
    _BEREICH_HALF_EXTENT,
    _BEREICH_WIDTH,
    _COMPETENCY_HALF_EXTENT,
)
from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphVisibleSet
from kursplaner.core.domain.kompetenzgraph_layout import compute_layered_layout
from kursplaner.core.domain.kompetenzgraph_view import KompetenzGraphView
from kursplaner.core.domain.kompetenzgraph_view_mode import MODE_OBER_TEIL
from tests.kompetenzgraph_test_support import make_synthetic_informatik_like_snapshot

_MAX_VERTICAL_JITTER = 20.0


def test_large_synthetic_graph_produces_valid_non_overlapping_layout(tk_root):
    """Integrations-/Smoke-Test: prüft NUR das Zusammenspiel auf realistischer Skala, nicht
    einzelne Eigenschaften isoliert (die sind bereits durch die feingranularen Tests in
    `test_kompetenzgraph_layout.py`/`test_kompetenzgraph_canvas_edges.py` abgedeckt)."""
    snapshot = make_synthetic_informatik_like_snapshot()
    visible_node_ids = frozenset(snapshot.nodes.keys())
    visible_bereich_ids = frozenset(snapshot.bereiche.keys())

    layout = compute_layered_layout(snapshot, MODE_OBER_TEIL, visible_node_ids, visible_bereich_ids)

    # (1) Jeder sichtbare Knoten UND jeder sichtbare Bereich-Hub hat eine endliche, reelle Position.
    for node_id in visible_node_ids | visible_bereich_ids:
        position = layout.positions.get(node_id)
        assert position is not None
        assert position.x == position.x and position.y == position.y  # kein NaN (NaN != NaN)
        assert abs(position.x) < float("inf") and abs(position.y) < float("inf")

    # (2) Hierarchiekanten bleiben in Schicht-Reihenfolge konsistent: jedes Kind liegt (abzüglich
    # des kosmetischen Jitters) strikt unterhalb seines Elternteils.
    for node_id, node in snapshot.nodes.items():
        for parent_id in node.oberkompetenzen_ids:
            if parent_id in layout.positions:
                assert layout.positions[node_id].y > layout.positions[parent_id].y - _MAX_VERTICAL_JITTER

    # (3) Keine zwei Bereich-Hub-Bounding-Boxes überlappen.
    bereich_positions = sorted(
        ((bid, layout.positions[bid].x) for bid in visible_bereich_ids), key=lambda entry: entry[1]
    )
    for (_prev_id, prev_x), (_next_id, next_x) in zip(bereich_positions, bereich_positions[1:]):
        assert next_x - prev_x >= _BEREICH_WIDTH

    # (4) Mehrfache Layout-Läufe mit denselben Eingaben driften nicht.
    repeated_layout = compute_layered_layout(snapshot, MODE_OBER_TEIL, visible_node_ids, visible_bereich_ids)
    assert layout.positions == repeated_layout.positions

    # (5) Standard-Kantenzahl (ohne Selektion) sinkt gegenüber "primär + prozess" auf nur "primär"
    # -- Regressionsschutz gegen ein Wiederaufleben des ursprünglichen Clutter-Problems.
    view = KompetenzGraphView(
        visible=KompetenzGraphVisibleSet(primary_ids=visible_node_ids, context_ids=frozenset()),
        visible_bereich_ids=visible_bereich_ids,
    )
    canvas = tk.Canvas(tk.Toplevel(tk_root))
    renderer = KompetenzGraphEdgeRenderer(
        canvas, competency_half_extent=_COMPETENCY_HALF_EXTENT, bereich_half_extent=_BEREICH_HALF_EXTENT
    )
    renderer.draw_classification_edges(snapshot, view, layout, selected_id=None)
    lines = [item for item in canvas.find_all() if canvas.type(item) == "line"]
    nodes_with_primary_bereich = sum(1 for node in snapshot.nodes.values() if node.primarer_bereich_id is not None)
    assert len(lines) == nodes_with_primary_bereich  # nur primäre Kanten, keine Prozessbereich-Kanten
