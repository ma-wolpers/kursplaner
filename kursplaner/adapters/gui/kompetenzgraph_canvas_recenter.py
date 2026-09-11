from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui

from kursplaner.adapters.gui.kompetenzgraph_canvas_render import NODE_TAG_PREFIX


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


def is_node_fully_visible(canvas: ui.Canvas, node_tag: str) -> bool:
    """Prüft, ob das durch `node_tag` markierte Item vollständig im aktuell sichtbaren Ausschnitt liegt.

    Genutzt für das "sanfte" Recenter nach einem passiven Rebuild
    (Filter-/Ansichtswechsel, siehe `kompetenzgraph_dialog.py::
    _recenter_if_offscreen()`): bleibt die Auswahl im Sichtfeld, soll die
    Ansicht NICHT scrollen; nur wenn sie tatsächlich aus dem Sichtbereich
    herausfällt, greift `recenter_on_node()`. Anders als dort wird hier
    nicht die `scrollregion`, sondern der über `canvas.canvasx()`/
    `canvas.canvasy()` ermittelte TATSÄCHLICH sichtbare Ausschnitt
    herangezogen (unabhängig von der aktuellen Scroll-Position korrekt).

    Args:
        canvas: Der Graph-Canvas.
        node_tag: Das Canvas-Tag des zu prüfenden Knotens.

    Returns:
        `True`, wenn das Item existiert und vollständig sichtbar ist;
        `False` bei fehlendem Item oder auch nur teilweiser Verdeckung.
    """
    bbox = canvas.bbox(node_tag)
    if not bbox:
        return False

    visible_left = canvas.canvasx(0)
    visible_top = canvas.canvasy(0)
    visible_right = canvas.canvasx(canvas.winfo_width())
    visible_bottom = canvas.canvasy(canvas.winfo_height())

    node_left, node_top, node_right, node_bottom = bbox
    return (
        node_left >= visible_left
        and node_right <= visible_right
        and node_top >= visible_top
        and node_bottom <= visible_bottom
    )


def recenter_on_selection(canvas: ui.Canvas, selected_id: str | None) -> None:
    """Zentriert die Ansicht bedingungslos auf `selected_id`, sofern gesetzt.

    Dünner Aufbau des Knoten-Tags über `NODE_TAG_PREFIX` um `recenter_on_node()`
    -- für AKTIVE Navigation (Pfeiltasten, Fokus-Toggle in
    `kompetenzgraph_dialog.py`), wo der ausgewählte Knoten immer sichtbar
    in die Mitte rücken soll. Für passiven Rebuild (Filter-/Ansichtswechsel)
    siehe stattdessen `recenter_on_selection_if_offscreen()`.
    """
    if selected_id is not None:
        recenter_on_node(canvas, f"{NODE_TAG_PREFIX}{selected_id}")


def recenter_on_selection_if_offscreen(canvas: ui.Canvas, selected_id: str | None) -> None:
    """Zentriert nur, wenn `selected_id` gerade nicht vollständig sichtbar ist.

    Genutzt nach PASSIVEM Rebuild (`kompetenzgraph_dialog.py::
    _recompute_and_redraw()`, z. B. Filter-/Ansichts-/Matchingtiefe-
    Wechsel): bleibt die ausgewählte Kompetenz im Sichtfeld, bleibt die
    Ansicht unverändert stehen -- ein Filterwechsel soll nicht automatisch
    wegscrollen, nur weil sich die Position geringfügig verschoben hat.
    """
    if selected_id is None:
        return
    tag = f"{NODE_TAG_PREFIX}{selected_id}"
    if not is_node_fully_visible(canvas, tag):
        recenter_on_node(canvas, tag)
