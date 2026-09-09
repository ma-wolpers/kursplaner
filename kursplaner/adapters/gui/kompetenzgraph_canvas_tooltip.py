from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui
from bw_gui.theming import canvas_fill, canvas_outline_color, canvas_text_fill

_TOOLTIP_PADDING = 6.0
_TOOLTIP_OFFSET = 14.0
_TOOLTIP_WRAP_WIDTH = 260


class KompetenzGraphCanvasTooltip:
    """Hover-Overlay direkt auf dem Canvas -- zeigt den vollständigen Kompetenztext bei Mouse-Over.

    Bewusst KEIN `HoverTooltip`-Reuse (das ist `tk.Widget.bind`-basiert;
    Canvas-Items sind keine eigenständigen Widgets). Stattdessen
    zusätzliche, obenliegende Canvas-Items (Rechteck + Text), die bei
    `<Leave>` wieder entfernt werden -- einfachere Koordinatenmathematik
    unter Zoom/Pan als ein separates `Toplevel`-Fenster.
    """

    def __init__(self, canvas: ui.Canvas):
        self.canvas = canvas
        self._item_ids: list[int] = []

    def bind_node(self, tag: str, text: str) -> None:
        """Registriert Hover-Bindings für ein Canvas-Tag; `text` ist der vollständige, anzuzeigende Text."""
        self.canvas.tag_bind(tag, "<Enter>", lambda event, shown_text=text: self._show(event, shown_text))
        self.canvas.tag_bind(tag, "<Leave>", lambda _event: self.hide())

    def hide(self) -> None:
        """Entfernt ein evtl. aktuell sichtbares Tooltip-Overlay."""
        for item_id in self._item_ids:
            self.canvas.delete(item_id)
        self._item_ids = []

    def _show(self, event, text: str) -> None:
        self.hide()
        x = self.canvas.canvasx(event.x) + _TOOLTIP_OFFSET
        y = self.canvas.canvasy(event.y) + _TOOLTIP_OFFSET

        text_id = self.canvas.create_text(x, y, text=text, anchor="nw", width=_TOOLTIP_WRAP_WIDTH)
        canvas_text_fill(self.canvas, text_id, token="fg_primary")
        bbox = self.canvas.bbox(text_id)
        if bbox is None:
            self.canvas.delete(text_id)
            return

        rect_id = self.canvas.create_rectangle(
            bbox[0] - _TOOLTIP_PADDING,
            bbox[1] - _TOOLTIP_PADDING,
            bbox[2] + _TOOLTIP_PADDING,
            bbox[3] + _TOOLTIP_PADDING,
        )
        canvas_fill(self.canvas, rect_id, token="bg_panel")
        canvas_outline_color(self.canvas, rect_id, token="border")
        self.canvas.tag_raise(text_id, rect_id)
        self._item_ids = [rect_id, text_id]
