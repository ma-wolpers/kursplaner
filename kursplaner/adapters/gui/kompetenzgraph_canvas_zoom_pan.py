from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui

from kursplaner.adapters.gui.kompetenzgraph_canvas_render import LABEL_TAG

_ZOOM_STEP = 1.1
_MIN_SCALE = 0.03
"""Deutlich unter dem ursprünglichen 0.2 -- bei mehreren hundert Knoten reichte 0.2 nicht aus,
um den gesamten Graphen ins Sichtfeld zu bekommen."""
_MAX_SCALE = 3.0
_LABEL_HIDE_BELOW_SCALE = 0.6
"""Unterhalb dieser Skalierung werden Knoten-Beschriftungen ausgeblendet (sie würden
ohnehin unlesbar) -- der volle Titel bleibt über den Hover-Tooltip abrufbar. Bewusst
eine leicht anpassbare Konstante statt eines fest verdrahteten Werts, siehe Modul-Docstring."""


class KompetenzGraphCanvasZoomPan:
    """Bindet Zoom (Strg+/-, Strg+Mausrad) und Scroll (Mausrad/Shift+Mausrad) an einen Canvas.

    Rein darstellungsseitige Interaktion ohne fachliche Entscheidung --
    die Knotenpositionen selbst kommen unverändert aus
    `compute_layered_layout()`; Zoom ist ausschließlich eine
    Koordinatentransformation über `canvas.scale()`. Alle Bindings sind
    lokal auf den übergebenen Canvas beschränkt, nicht global.

    Blendet zusätzlich Knoten-Beschriftungen aus, sobald die Skalierung
    unter `_LABEL_HIDE_BELOW_SCALE` fällt (und wieder ein, sobald sie
    diese Schwelle wieder übersteigt) -- ein einziger tag-basierter
    `itemconfigure`-Aufruf über `kompetenzgraph_canvas_render.LABEL_TAG`,
    ausgelöst nur bei tatsächlichem Schwellen-Übergang, nicht bei jedem
    Zoom-Tick.
    """

    def __init__(self, canvas: ui.Canvas):
        """Bindet alle Zoom-/Scroll-Events an `canvas`."""
        self.canvas = canvas
        self._scale = 1.0
        self._labels_hidden = False
        self._bind()

    def _bind(self) -> None:
        for sequence in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            self.canvas.bind(sequence, self._zoom_in)
        for sequence in ("<Control-minus>", "<Control-KP_Subtract>"):
            self.canvas.bind(sequence, self._zoom_out)
        self.canvas.bind("<Control-MouseWheel>", self._on_ctrl_mousewheel)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)

    def _zoom_in(self, _event=None) -> str:
        self._apply_zoom(_ZOOM_STEP, anchor=self._viewport_center())
        return "break"

    def _zoom_out(self, _event=None) -> str:
        self._apply_zoom(1.0 / _ZOOM_STEP, anchor=self._viewport_center())
        return "break"

    def _on_ctrl_mousewheel(self, event) -> str:
        factor = _ZOOM_STEP if event.delta > 0 else 1.0 / _ZOOM_STEP
        anchor = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        self._apply_zoom(factor, anchor=anchor)
        return "break"

    def _on_mousewheel(self, event) -> str:
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _on_shift_mousewheel(self, event) -> str:
        self.canvas.xview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _viewport_center(self) -> tuple[float, float]:
        return (
            self.canvas.canvasx(self.canvas.winfo_width() / 2),
            self.canvas.canvasy(self.canvas.winfo_height() / 2),
        )

    def _apply_zoom(self, factor: float, *, anchor: tuple[float, float]) -> None:
        new_scale = self._scale * factor
        if new_scale < _MIN_SCALE or new_scale > _MAX_SCALE:
            return
        self._scale = new_scale
        self.canvas.scale("all", anchor[0], anchor[1], factor, factor)
        bbox = self.canvas.bbox("all")
        if bbox is not None:
            self.canvas.configure(scrollregion=bbox)
        self._update_label_visibility()

    def _update_label_visibility(self) -> None:
        """Blendet Beschriftungen bei tatsächlichem Schwellen-Übergang aus/ein -- kein Aufruf im selben Zustand."""
        should_hide = self._scale < _LABEL_HIDE_BELOW_SCALE
        if should_hide == self._labels_hidden:
            return
        self._labels_hidden = should_hide
        self.canvas.itemconfigure(LABEL_TAG, state="hidden" if should_hide else "normal")

    def reapply_label_visibility(self) -> None:
        """Wendet den aktuellen Label-Sichtbarkeitszustand erneut an.

        Nötig nach jedem vollen Canvas-Redraw: `KompetenzGraphCanvasRenderer.render()`
        löscht und erzeugt alle Canvas-Items neu (auch die Label-Textitems), die dabei
        wieder im Default-Zustand `state="normal"` entstehen -- unabhängig von der
        aktuellen Zoomstufe. `kompetenzgraph_dialog.py` ruft dies nach jedem
        `render()`-Aufruf auf.
        """
        self.canvas.itemconfigure(LABEL_TAG, state="hidden" if self._labels_hidden else "normal")
