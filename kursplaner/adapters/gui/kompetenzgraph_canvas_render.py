from __future__ import annotations

from collections.abc import Callable, Mapping

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui
from bw_gui.theming import (
    canvas_domain_fill,
    canvas_domain_outline,
    canvas_fill,
    canvas_outline_color,
    canvas_text_fill,
)

from kursplaner.adapters.gui.kompetenzgraph_canvas_colors import hue_to_color_pair
from kursplaner.adapters.gui.kompetenzgraph_canvas_shapes import create_rounded_rectangle
from kursplaner.core.domain.kompetenzgraph_layout import GraphNodePosition, KompetenzGraphLayout
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.kompetenzgraph_view import KompetenzGraphView
from kursplaner.core.domain.kompetenzgraph_view_mode import MODE_OBER_TEIL

_NODE_WIDTH = 92.0
_NODE_HEIGHT = 88.0  # nahezu quadratisch statt lang-rechteckig (früher 150x46)
_BEREICH_WIDTH = 170.0
_BEREICH_HEIGHT = 38.0
_CORNER_RADIUS = 10.0
_UNRESOLVED_MARKER_RADIUS = 10.0
NODE_TAG_PREFIX = "kompetenz_node_"
"""Öffentlich, da `kompetenzgraph_canvas_recenter.py` denselben Tag braucht, um das
aktuell ausgewählte Knoten-Item über `canvas.bbox(tag)` wiederzufinden."""
LABEL_TAG = "kompetenz_label"
"""Öffentlich, da `kompetenzgraph_canvas_zoom_pan.py` alle Label-Textitems über dieses
gemeinsame Tag in einem einzigen `itemconfigure`-Aufruf aus-/einblendet."""
_MAX_COMPETENCY_LABEL_CHARS = 22
"""Kürzer als früher (30 bei breiterer 150px-Box) -- passend zur schmaleren Knotenform."""
_MAX_BEREICH_LABEL_CHARS = 30
_DEFAULT_BEREICH_HUE = 0.0
"""Fallback für den praktisch nie auftretenden Fall einer `bereich_hues`-Lücke -- verhindert einen KeyError."""


def _truncate(text: str, max_chars: int) -> str:
    return text if len(text) <= max_chars else text[: max_chars - 1] + "…"


class KompetenzGraphCanvasRenderer:
    """Zeichnet Knoten und Kanten des Kompetenzgraphen auf einen tkinter-Canvas.

    Volles Redraw bei jeder Sichtbarkeits-/Ansichtswechsel-Anfrage (siehe
    `kompetenzgraph_dialog.py::_reapply_selection` für den NICHT neu
    berechnenden Selektions-Redraw-Pfad). Farben kommen ausschließlich über
    geteilte Theme-Canvas-Helfer (`canvas_fill`/`canvas_outline_color`/
    `canvas_text_fill` für Token-Farben, `canvas_domain_fill`/
    `canvas_domain_outline` für Bereichs-Hue-Farben aus
    `kompetenzgraph_canvas_colors.py`) -- kein hartkodierter Hex-Wert.
    Knoten sind abgerundete Rechtecke (`kompetenzgraph_canvas_shapes.py`).
    """

    def __init__(
        self,
        canvas: ui.Canvas,
        *,
        on_node_click: Callable[[str], None],
        on_node_double_click: Callable[[str], None] | None = None,
        tooltip=None,
    ):
        """Initialisiert den Renderer.

        Args:
            canvas: Der zu bemalende Canvas (Zoom/Pan-Bindings sind Sache
                von `kompetenzgraph_canvas_zoom_pan.py`, nicht hier).
            on_node_click: Wird mit der Knoten-ID aufgerufen, sobald ein
                Kompetenz- oder Bereichs-Knoten angeklickt wird.
            on_node_double_click: Optional -- wird mit der Knoten-ID bei
                einem Doppelklick aufgerufen (Fokus-Toggle, Meilenstein 5).
            tooltip: Optionales `KompetenzGraphCanvasTooltip` -- wenn
                gesetzt, wird für jeden gezeichneten Knoten ein
                Hover-Binding registriert.
        """
        self.canvas = canvas
        self._on_node_click = on_node_click
        self._on_node_double_click = on_node_double_click
        self._tooltip = tooltip

    def render(
        self,
        snapshot: KompetenzGraphSnapshot,
        view: KompetenzGraphView,
        layout: KompetenzGraphLayout,
        *,
        mode_key: str,
        selected_id: str | None,
        focus_id: str | None,
        bereich_hues: Mapping[str, float],
    ) -> None:
        """Baut die komplette Canvas-Zeichnung für den aktuellen Zustand neu auf.

        Args:
            bereich_hues: Über die Popup-Sitzung stabile Bereich→Farbton-
                Zuordnung (`kompetenzgraph_canvas_colors.py::assign_bereich_hues`,
                einmalig in `KompetenzGraphUiState.bereich_hues` gehalten) --
                bestimmt Rahmenfarbe der Kompetenz-Knoten (Quelle: deren
                `primarer_bereich_id`) und Füllung/Rahmen der Bereichs-Hubs.
        """
        self.canvas.delete("all")

        self._draw_classification_edges(snapshot, view, layout)
        self._draw_hierarchy_edges(snapshot, view, layout, mode_key)
        self._draw_unresolved_markers(layout)

        for bereich_id in view.visible_bereich_ids:
            self._draw_bereich_node(snapshot, bereich_id, layout, bereich_hues, is_selected=bereich_id == selected_id)

        for node_id in view.visible.all_ids:
            self._draw_competency_node(
                snapshot,
                node_id,
                layout,
                bereich_hues,
                is_context=node_id in view.visible.context_ids,
                is_selected=node_id == selected_id,
                is_focused=node_id == focus_id,
            )

        self._update_scrollregion(layout)

    def _draw_edge(self, start: GraphNodePosition, end: GraphNodePosition, *, dash, token: str) -> None:
        # Kanten werden vor allen Knoten gezeichnet (siehe Aufrufreihenfolge in render()),
        # liegen also durch die natuerliche Canvas-Stapelreihenfolge bereits hinter ihnen.
        item_id = self.canvas.create_line(start.x, start.y, end.x, end.y, dash=dash, width=1.4)
        canvas_fill(self.canvas, item_id, token=token)

    def _draw_classification_edges(
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
                    self._draw_edge(start, end, dash=None, token="secondary")
            for prozessbereich_id in node.prozessbereich_ids:
                if prozessbereich_id in view.visible_bereich_ids:
                    end = layout.positions.get(prozessbereich_id)
                    if end is not None:
                        self._draw_edge(start, end, dash=(2, 3), token="secondary_soft")

    def _draw_hierarchy_edges(
        self, snapshot: KompetenzGraphSnapshot, view: KompetenzGraphView, layout: KompetenzGraphLayout, mode_key: str
    ) -> None:
        """Nur die Kanten des AKTIVEN View-Modes (`oberkompetenzen` oder `voraussetzungen`)."""
        for node_id in view.visible.all_ids:
            node = snapshot.nodes.get(node_id)
            start = layout.positions.get(node_id)
            if node is None or start is None:
                continue
            forward_ids = node.oberkompetenzen_ids if mode_key == MODE_OBER_TEIL else node.voraussetzungen_ids
            for target_id in forward_ids:
                if target_id not in view.visible.all_ids:
                    continue
                end = layout.positions.get(target_id)
                if end is not None:
                    self._draw_edge(start, end, dash=None, token="border")

    def _draw_unresolved_markers(self, layout: KompetenzGraphLayout) -> None:
        """Gestrichelte Kante + gedimmter Marker für Wikilinks ohne existierendes Ziel.

        Rein visueller Hinweis -- die Marker sind bewusst nicht klickbar/
        fokussierbar (siehe Meilenstein 5 für die Interaktions-Invarianten).
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

    def _draw_competency_node(
        self,
        snapshot: KompetenzGraphSnapshot,
        node_id: str,
        layout: KompetenzGraphLayout,
        bereich_hues: Mapping[str, float],
        *,
        is_context: bool,
        is_selected: bool,
        is_focused: bool,
    ) -> None:
        node = snapshot.nodes[node_id]
        position = layout.positions[node_id]
        x0, y0 = position.x - _NODE_WIDTH / 2, position.y - _NODE_HEIGHT / 2
        x1, y1 = position.x + _NODE_WIDTH / 2, position.y + _NODE_HEIGHT / 2
        tag = f"{NODE_TAG_PREFIX}{node_id}"

        fill_token = "accent_soft" if is_focused else ("bg_surface" if is_context else "bg_panel")
        rect_id = create_rounded_rectangle(self.canvas, x0, y0, x1, y1, radius=_CORNER_RADIUS, tags=(tag,))
        canvas_fill(self.canvas, rect_id, token=fill_token)
        if is_selected:
            canvas_outline_color(self.canvas, rect_id, token="accent")
            self.canvas.itemconfigure(rect_id, width=2.5)
        else:
            # Dünner, bereichsfarbener Rahmen als Gruppierungshilfe (siehe
            # `kompetenzgraph_canvas_colors.py`) -- bewusst dünner als die
            # Selektions-Markierung, damit beide nie verwechselt werden.
            # Kontextknoten bekommen die gedämpfte Variante, damit die
            # bestehende Fill-basierte Kontext-Kennzeichnung das dominante
            # Signal bleibt und die Bereichsfarbe sie nur ergänzt.
            primarer_bereich_id = node.primarer_bereich_id
            hue = (
                bereich_hues.get(primarer_bereich_id, _DEFAULT_BEREICH_HUE)
                if primarer_bereich_id is not None
                else _DEFAULT_BEREICH_HUE
            )
            light_color, dark_color = hue_to_color_pair(hue, muted=is_context)
            canvas_domain_outline(self.canvas, rect_id, light_color=light_color, dark_color=dark_color)
            self.canvas.itemconfigure(rect_id, width=1.5)

        text_id = self.canvas.create_text(
            position.x,
            position.y,
            text=_truncate(node.title, _MAX_COMPETENCY_LABEL_CHARS),
            width=_NODE_WIDTH - 10,
            tags=(tag, LABEL_TAG),
        )
        canvas_text_fill(self.canvas, text_id, token="fg_muted" if is_context else "fg_primary")

        self.canvas.tag_bind(tag, "<Button-1>", lambda _event, nid=node_id: self._on_node_click(nid))
        if self._on_node_double_click is not None:
            self.canvas.tag_bind(tag, "<Double-Button-1>", lambda _event, nid=node_id: self._on_node_double_click(nid))
        if self._tooltip is not None:
            self._tooltip.bind_node(tag, node.title)

    def _draw_bereich_node(
        self,
        snapshot: KompetenzGraphSnapshot,
        bereich_id: str,
        layout: KompetenzGraphLayout,
        bereich_hues: Mapping[str, float],
        *,
        is_selected: bool,
    ) -> None:
        bereich = snapshot.bereiche.get(bereich_id)
        position = layout.positions.get(bereich_id)
        if bereich is None or position is None:
            return
        x0, y0 = position.x - _BEREICH_WIDTH / 2, position.y - _BEREICH_HEIGHT / 2
        x1, y1 = position.x + _BEREICH_WIDTH / 2, position.y + _BEREICH_HEIGHT / 2
        tag = f"{NODE_TAG_PREFIX}{bereich_id}"
        hue = bereich_hues.get(bereich_id, _DEFAULT_BEREICH_HUE)

        rect_id = create_rounded_rectangle(self.canvas, x0, y0, x1, y1, radius=_CORNER_RADIUS, tags=(tag,))
        soft_light, soft_dark = hue_to_color_pair(hue, muted=True)
        canvas_domain_fill(self.canvas, rect_id, light_color=soft_light, dark_color=soft_dark)
        if is_selected:
            canvas_outline_color(self.canvas, rect_id, token="accent")
        else:
            vivid_light, vivid_dark = hue_to_color_pair(hue)
            canvas_domain_outline(self.canvas, rect_id, light_color=vivid_light, dark_color=vivid_dark)
        self.canvas.itemconfigure(rect_id, width=2.5 if is_selected else 1.5)

        text_id = self.canvas.create_text(
            position.x,
            position.y,
            text=_truncate(bereich.title, _MAX_BEREICH_LABEL_CHARS),
            width=_BEREICH_WIDTH - 10,
            tags=(tag, LABEL_TAG),
        )
        canvas_text_fill(self.canvas, text_id, token="fg_primary")

        self.canvas.tag_bind(tag, "<Button-1>", lambda _event, bid=bereich_id: self._on_node_click(bid))
        if self._tooltip is not None:
            self._tooltip.bind_node(tag, f"{bereich.title} ({bereich.kuerzel})" if bereich.kuerzel else bereich.title)

    def _update_scrollregion(self, layout: KompetenzGraphLayout) -> None:
        all_positions = [*layout.positions.values(), *layout.unresolved_marker_positions.values()]
        if not all_positions:
            self.canvas.configure(scrollregion=(0, 0, 0, 0))
            return
        margin = 120.0
        min_x = min(p.x for p in all_positions) - _NODE_WIDTH - margin
        max_x = max(p.x for p in all_positions) + _NODE_WIDTH + margin
        min_y = min(p.y for p in all_positions) - _NODE_HEIGHT - margin
        max_y = max(p.y for p in all_positions) + _NODE_HEIGHT + margin
        self.canvas.configure(scrollregion=(min_x, min_y, max_x, max_y))
