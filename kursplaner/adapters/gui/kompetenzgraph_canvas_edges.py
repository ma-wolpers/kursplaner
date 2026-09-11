from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui
from bw_gui.theming import canvas_fill, canvas_outline_color, canvas_text_fill

from kursplaner.adapters.gui.kompetenzgraph_canvas_shapes import ray_rectangle_intersection
from kursplaner.core.domain.kompetenzgraph_layout import GraphNodePosition, KompetenzGraphLayout
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.kompetenzgraph_view import KompetenzGraphView
from kursplaner.core.domain.kompetenzgraph_view_mode import MODE_ABHAENGIGKEITEN, MODE_OBER_TEIL

_UNRESOLVED_MARKER_RADIUS = 10.0
_EDGE_ANCHOR_RADIUS = 3.0
"""Radius des kleinen, gefüllten Andockpunkts am Rechteckrand -- siehe `_draw_connecting_edge()`."""
_ABHAENGIGKEITEN_VORAUSSETZUNG_DASH = (4, 2)
"""Eigenes, deutlich gestricheltes Muster für Voraussetzungs-Kanten in `MODE_ABHAENGIGKEITEN`
-- unterscheidbar vom Klassifikations-Dash (`(2, 3)`), damit "gestrichelt = Voraussetzung" in
dieser Ansicht nicht mit "gestrichelt = Prozessbereich" verwechselt wird."""


class KompetenzGraphEdgeRenderer:
    """Zeichnet alle Kanten-Arten des Kompetenzgraphen (Klassifikation, Hierarchie, Unresolved-Marker).

    Ausgelagert aus `kompetenzgraph_canvas_render.py`, um dessen
    300-Zeilen-Budget einzuhalten -- reine Kanten-Zeichenverantwortung,
    kennt keine Knoten-Zeichnung. Kanten werden vor den Knoten gezeichnet
    (Aufrufreihenfolge liegt bei `KompetenzGraphCanvasRenderer.render()`),
    liegen also durch die natürliche Canvas-Stapelreihenfolge bereits
    hinter ihnen.
    """

    def __init__(
        self, canvas: ui.Canvas, *, competency_half_extent: tuple[float, float], bereich_half_extent: tuple[float, float]
    ):
        """Args: die halbe Breite/Höhe von Kompetenz-Knoten bzw. Bereichs-Hubs (für die Andockpunkt-Geometrie)."""
        self.canvas = canvas
        self._competency_half_extent = competency_half_extent
        self._bereich_half_extent = bereich_half_extent

    def draw_classification_edges(
        self, snapshot: KompetenzGraphSnapshot, view: KompetenzGraphView, layout: KompetenzGraphLayout
    ) -> None:
        """`primarer_bereich` (durchgezogen) und `prozessbereiche` (gestrichelt) -- ansichtsunabhängig, immer sichtbar."""
        for node_id in view.visible.all_ids:
            node = snapshot.nodes.get(node_id)
            start = layout.positions.get(node_id)
            if node is None or start is None:
                continue
            if node.primarer_bereich_id is not None and node.primarer_bereich_id in view.visible_bereich_ids:
                end = layout.positions.get(node.primarer_bereich_id)
                if end is not None:
                    self._draw_connecting_edge(
                        start,
                        end,
                        dash=None,
                        token="secondary",
                        start_half_extent=self._competency_half_extent,
                        end_half_extent=self._bereich_half_extent,
                    )
            for prozessbereich_id in node.prozessbereich_ids:
                if prozessbereich_id in view.visible_bereich_ids:
                    end = layout.positions.get(prozessbereich_id)
                    if end is not None:
                        self._draw_connecting_edge(
                            start,
                            end,
                            dash=(2, 3),
                            token="secondary_soft",
                            start_half_extent=self._competency_half_extent,
                            end_half_extent=self._bereich_half_extent,
                        )

    def draw_hierarchy_edges(
        self, snapshot: KompetenzGraphSnapshot, view: KompetenzGraphView, layout: KompetenzGraphLayout, mode_key: str
    ) -> None:
        """Zeichnet die Hierarchie-Kanten des AKTIVEN View-Modes.

        `MODE_OBER_TEIL`/`MODE_FORT_VORAUS`: eine einzige, durchgezogene
        Kantenart (`oberkompetenzen` bzw. `voraussetzungen`, wie
        gespeichert). `MODE_ABHAENGIGKEITEN`: BEIDE Kantentypen gemeinsam,
        mit unterschiedlicher Strichart -- Teilkompetenz (durchgezogen,
        `teilkompetenzen_by_id`, d. h. `oberkompetenzen` UMGEDREHT
        gezeichnet: Eltern→Kind statt wie gespeichert Kind→Eltern, damit
        der Pfeil konsistent "X braucht Y" bedeutet) und Voraussetzung
        (gestrichelt, `voraussetzungen_ids` -- bereits in der richtigen
        Richtung gespeichert, keine Umkehrung nötig). Reine
        Rendering-Entscheidung; die zugrunde liegende fachliche Kante
        bleibt in beiden Fällen unverändert `hierarchy` bzw. `prerequisite`
        (siehe `kompetenzgraph_view_mode.py::MODE_ABHAENGIGKEITEN`).
        """
        for node_id in view.visible.all_ids:
            node = snapshot.nodes.get(node_id)
            start = layout.positions.get(node_id)
            if node is None or start is None:
                continue
            if mode_key == MODE_ABHAENGIGKEITEN:
                for target_id in snapshot.teilkompetenzen_by_id.get(node_id, ()):
                    self._draw_hierarchy_edge_if_visible(view, layout, start, target_id, dash=None)
                for target_id in node.voraussetzungen_ids:
                    self._draw_hierarchy_edge_if_visible(
                        view, layout, start, target_id, dash=_ABHAENGIGKEITEN_VORAUSSETZUNG_DASH
                    )
                continue
            forward_ids = node.oberkompetenzen_ids if mode_key == MODE_OBER_TEIL else node.voraussetzungen_ids
            for target_id in forward_ids:
                self._draw_hierarchy_edge_if_visible(view, layout, start, target_id, dash=None)

    def _draw_hierarchy_edge_if_visible(
        self, view: KompetenzGraphView, layout: KompetenzGraphLayout, start: GraphNodePosition, target_id: str, *, dash
    ) -> None:
        if target_id not in view.visible.all_ids:
            return
        end = layout.positions.get(target_id)
        if end is not None:
            self._draw_connecting_edge(
                start,
                end,
                dash=dash,
                token="border",
                start_half_extent=self._competency_half_extent,
                end_half_extent=self._competency_half_extent,
            )

    def draw_unresolved_markers(self, layout: KompetenzGraphLayout) -> None:
        """Gestrichelte Kante + gedimmter Marker für Wikilinks ohne existierendes Ziel.

        Rein visueller Hinweis -- die Marker sind bewusst nicht klickbar/
        fokussierbar. Bekommen bewusst KEINEN Andockpunkt (der gestrichelte
        Oval-Marker macht den Endpunkt bereits eindeutig).
        """
        for link, marker_position in layout.unresolved_marker_positions.items():
            source_position = layout.positions.get(link.source_id)
            if source_position is not None:
                self._draw_edge(source_position, marker_position, dash=(1, 3), token="fg_muted")
            oval_id = self.canvas.create_oval(
                marker_position.x - _UNRESOLVED_MARKER_RADIUS,
                marker_position.y - _UNRESOLVED_MARKER_RADIUS,
                marker_position.x + _UNRESOLVED_MARKER_RADIUS,
                marker_position.y + _UNRESOLVED_MARKER_RADIUS,
                dash=(2, 2),
            )
            canvas_fill(self.canvas, oval_id, token="bg_surface")
            canvas_outline_color(self.canvas, oval_id, token="danger")
            text_id = self.canvas.create_text(
                marker_position.x, marker_position.y + _UNRESOLVED_MARKER_RADIUS + 8, text=f"? {link.target_id}"
            )
            canvas_text_fill(self.canvas, text_id, token="fg_muted")

    def _draw_edge(self, start: GraphNodePosition, end: GraphNodePosition, *, dash, token: str) -> None:
        item_id = self.canvas.create_line(start.x, start.y, end.x, end.y, dash=dash, width=1.4)
        canvas_fill(self.canvas, item_id, token=token)

    def _draw_connecting_edge(
        self,
        start: GraphNodePosition,
        end: GraphNodePosition,
        *,
        dash,
        token: str,
        start_half_extent: tuple[float, float],
        end_half_extent: tuple[float, float],
    ) -> None:
        """Wie `_draw_edge()`, zusätzlich mit sichtbaren Andockpunkten an beiden Enden.

        Macht erkennbar, ob eine Linie an einem Knoten wirklich andockt oder
        nur optisch dahinter/daneben verläuft (regulär möglich, seit Kanten
        Schichten überspringen dürfen) -- ein kleiner gefüllter Punkt genau
        am Rechteckrand (`ray_rectangle_intersection()`), nicht am
        unsichtbaren Mittelpunkt.
        """
        self._draw_edge(start, end, dash=dash, token=token)
        self._draw_edge_anchor(start.x, start.y, end.x, end.y, *start_half_extent, token=token)
        self._draw_edge_anchor(end.x, end.y, start.x, start.y, *end_half_extent, token=token)

    def _draw_edge_anchor(
        self, center_x: float, center_y: float, toward_x: float, toward_y: float, half_width: float, half_height: float, *, token: str
    ) -> None:
        anchor_x, anchor_y = ray_rectangle_intersection(center_x, center_y, toward_x, toward_y, half_width, half_height)
        dot_id = self.canvas.create_oval(
            anchor_x - _EDGE_ANCHOR_RADIUS,
            anchor_y - _EDGE_ANCHOR_RADIUS,
            anchor_x + _EDGE_ANCHOR_RADIUS,
            anchor_y + _EDGE_ANCHOR_RADIUS,
        )
        canvas_fill(self.canvas, dot_id, token=token)
