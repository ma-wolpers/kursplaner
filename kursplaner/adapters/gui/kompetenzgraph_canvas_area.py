from __future__ import annotations

from collections.abc import Callable

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets

from kursplaner.adapters.gui.kompetenzgraph_canvas_arrow_nav import KompetenzGraphCanvasArrowNav
from kursplaner.adapters.gui.kompetenzgraph_canvas_render import KompetenzGraphCanvasRenderer
from kursplaner.adapters.gui.kompetenzgraph_canvas_tooltip import KompetenzGraphCanvasTooltip
from kursplaner.adapters.gui.kompetenzgraph_canvas_zoom_pan import KompetenzGraphCanvasZoomPan


class KompetenzGraphCanvasArea:
    """Baut den Graph-Canvas samt Scrollbars, Tooltip, Renderer, Zoom/Pan und Pfeiltasten-Navigation.

    Ausgelagert aus `kompetenzgraph_dialog.py`, um dessen 300-Zeilen-Budget
    einzuhalten -- rein UI-Aufbau-Verantwortung (Widget-Erzeugung +
    Verdrahtung der Callbacks an die vom Dialog übergebenen Handler),
    keine eigene Fach- oder Zustandslogik.
    """

    def __init__(
        self,
        parent,
        *,
        on_node_click: Callable[[str], None],
        on_node_double_click: Callable[[str], None],
        on_arrow_direction: Callable[[tuple[float, float]], None],
        on_enter_key: Callable,
    ):
        """Baut den Canvas-Bereich in `parent` und verdrahtet ihn mit den übergebenen Dialog-Callbacks."""
        canvas_container = widgets.Frame(parent)
        canvas_container.pack(fill="both", expand=True)
        self.canvas = ui.Canvas(canvas_container, highlightthickness=0)
        h_scroll = widgets.Scrollbar(canvas_container, orient="horizontal", command=self.canvas.xview)
        v_scroll = widgets.Scrollbar(canvas_container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        canvas_container.rowconfigure(0, weight=1)
        canvas_container.columnconfigure(0, weight=1)

        self.tooltip = KompetenzGraphCanvasTooltip(self.canvas)
        self.renderer = KompetenzGraphCanvasRenderer(
            self.canvas, on_node_click=on_node_click, on_node_double_click=on_node_double_click, tooltip=self.tooltip
        )
        self.zoom_pan = KompetenzGraphCanvasZoomPan(self.canvas)
        self._arrow_nav = KompetenzGraphCanvasArrowNav(self.canvas, on_direction=on_arrow_direction)
        self.canvas.bind("<Return>", on_enter_key)
        self.canvas.bind("<KP_Enter>", on_enter_key)
