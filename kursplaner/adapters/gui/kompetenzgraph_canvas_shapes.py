from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui


def create_rounded_rectangle(canvas: ui.Canvas, x0: float, y0: float, x1: float, y1: float, *, radius: float = 12.0, **kwargs) -> int:
    """Zeichnet ein abgerundetes Rechteck auf `canvas` -- tkinter.Canvas kennt keine native Rundungs-Option.

    Standard-Technik: ein Zwölf-Punkte-Polygon entlang der vier Ecken,
    per `smooth=True` zu weichen Kurven interpoliert. `radius` wird
    intern auf höchstens die halbe Breite/Höhe begrenzt, damit kleine
    Knoten (deutlich kleiner als ein Bereichs-Hub) nicht verzerrt
    ("kartoffelig") wirken.

    Args:
        canvas: Der Ziel-Canvas.
        x0, y0, x1, y1: Bounding-Box-Ecken wie bei `canvas.create_rectangle`.
        radius: Gewünschter Eckenradius in Pixeln.
        **kwargs: Wird unverändert an `canvas.create_polygon` durchgereicht
            (z. B. `fill`, `outline`, `width`, `tags`) -- Aufrufer
            behandeln das Ergebnis wie ein gewöhnliches `create_rectangle`-
            Item.

    Returns:
        Die Canvas-Item-ID des erzeugten Polygons.
    """
    width = abs(x1 - x0)
    height = abs(y1 - y0)
    effective_radius = max(0.0, min(radius, width / 2.0, height / 2.0))
    r = effective_radius
    points = [
        x0 + r, y0,
        x1 - r, y0,
        x1, y0,
        x1, y0 + r,
        x1, y1 - r,
        x1, y1,
        x1 - r, y1,
        x0 + r, y1,
        x0, y1,
        x0, y1 - r,
        x0, y0 + r,
        x0, y0,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def ray_rectangle_intersection(
    center_x: float, center_y: float, toward_x: float, toward_y: float, half_width: float, half_height: float
) -> tuple[float, float]:
    """Berechnet, wo ein Strahl vom Rechteck-Mittelpunkt Richtung `(toward_x, toward_y)` den Rechteckrand schneidet.

    Genutzt für die sichtbaren Kanten-Andockpunkte
    (`kompetenzgraph_canvas_render.py`): eine Kante wird bisher von
    Mittelpunkt zu Mittelpunkt gezeichnet (der Teil innerhalb der
    Knoten-Box ist unsichtbar, weil Knoten NACH den Kanten gezeichnet
    werden) -- der tatsächlich sichtbare Endpunkt der Linie liegt am
    Rechteckrand, nicht am Mittelpunkt. Der Eckenradius abgerundeter
    Rechtecke wird hier bewusst ignoriert (bei 10px Radius auf
    92x88/170x38-Boxen visuell vernachlässigbar) -- reine, einfache
    Rechteck-Strahl-Geometrie, kein Polygon-Schnitt.

    Args:
        center_x, center_y: Mittelpunkt des Rechtecks (Ursprung des Strahls).
        toward_x, toward_y: Punkt, auf den der Strahl zeigt (z. B. der
            Mittelpunkt des anderen Kanten-Endpunkts). Bei identischem
            Punkt (`toward == center`) wird der Mittelpunkt selbst
            zurückgegeben, statt durch Null zu teilen.
        half_width, half_height: Halbe Breite/Höhe des Rechtecks.

    Returns:
        `(x, y)`-Koordinate des Schnittpunkts auf dem Rechteckrand.
    """
    dx = toward_x - center_x
    dy = toward_y - center_y
    if dx == 0.0 and dy == 0.0:
        return (center_x, center_y)
    scale_candidates = []
    if dx != 0.0:
        scale_candidates.append(half_width / abs(dx))
    if dy != 0.0:
        scale_candidates.append(half_height / abs(dy))
    scale = min(scale_candidates)
    return (center_x + dx * scale, center_y + dy * scale)
