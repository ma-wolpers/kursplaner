"""Kanten-Andockgeometrie des Kompetenznetz-Canvas.

Abgerundete Knoten-Rechtecke kommen aus bw-gui (`bw_gui.widgets.canvas_shapes`).
"""

from __future__ import annotations


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
