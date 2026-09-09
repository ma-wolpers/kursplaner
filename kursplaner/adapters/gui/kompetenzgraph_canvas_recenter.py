from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui


def recenter_on_node(canvas: ui.Canvas, node_tag: str) -> None:
    """Scrollt `canvas` so, dass das durch `node_tag` markierte Item im Sichtbereich zentriert liegt.

    Nutzt bewusst die AKTUELLEN, bereits zoom-transformierten
    Canvas-Koordinaten über `canvas.bbox(node_tag)` statt der
    ursprünglichen Layout-Weltkoordinaten -- `canvas.scale()` verändert
    Item-Koordinaten in-place, sodass nur `bbox()` die tatsächliche
    aktuelle Position kennt. Wird bei jeder pfeiltasten-getriebenen
    Selektionsänderung aufgerufen (auch im Fokus-Modus).

    Args:
        canvas: Der Graph-Canvas.
        node_tag: Das Canvas-Tag des zu zentrierenden Knotens (siehe
            `kompetenzgraph_canvas_render.py::NODE_TAG_PREFIX`).
    """
    bbox = canvas.bbox(node_tag)
    scrollregion_raw = canvas.cget("scrollregion")
    if not bbox or not scrollregion_raw:
        return

    try:
        region_x0, region_y0, region_x1, region_y1 = (float(value) for value in str(scrollregion_raw).split())
    except ValueError:
        return

    region_width = region_x1 - region_x0
    region_height = region_y1 - region_y0
    if region_width <= 0 or region_height <= 0:
        return

    node_center_x = (bbox[0] + bbox[2]) / 2
    node_center_y = (bbox[1] + bbox[3]) / 2

    viewport_width = canvas.winfo_width()
    viewport_height = canvas.winfo_height()

    target_left = node_center_x - viewport_width / 2
    target_top = node_center_y - viewport_height / 2

    fraction_x = (target_left - region_x0) / region_width
    fraction_y = (target_top - region_y0) / region_height

    canvas.xview_moveto(max(0.0, min(1.0, fraction_x)))
    canvas.yview_moveto(max(0.0, min(1.0, fraction_y)))
