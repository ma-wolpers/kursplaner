from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui

_ZOOM_STEP = 1.1
_MIN_SCALE = 0.2
_MAX_SCALE = 3.0


class KompetenzGraphCanvasZoomPan:
    """Bindet Zoom (Strg+/-, Strg+Mausrad) und Scroll (Mausrad/Shift+Mausrad) an einen Canvas.

    Rein darstellungsseitige Interaktion ohne fachliche Entscheidung --
    die Knotenpositionen selbst kommen unverändert aus
    `compute_layered_layout()`; Zoom ist ausschließlich eine
    Koordinatentransformation über `canvas.scale()`. Alle Bindings sind
    lokal auf den übergebenen Canvas beschränkt, nicht global.
    """

    def __init__(self, canvas: ui.Canvas):
        """Bindet alle Zoom-/Scroll-Events an `canvas`."""
        self.canvas = canvas
        self._scale = 1.0
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
