"""Smiley-Symbole (😊 😐 ☹) als reportlab-Zeichnungen für Selbsteinschätzungsspalten.

Ausgelagert aus `expected_horizon_pdf_renderer.py`. Wie dort ist `reportlab`
optional: Fehlt es, bleibt das Modul importierbar, nur `face_symbol` darf dann
nicht aufgerufen werden (die Verfügbarkeitsprüfung liegt in `wiring.py`).
"""

from __future__ import annotations

try:
    from reportlab.graphics.shapes import Circle, Drawing, Line  # type: ignore[import-not-found]
    from reportlab.lib import colors  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - Umgebung ohne reportlab
    pass


def face_symbol(kind: str) -> "Drawing":
    """Zeichnet ein 16×16-pt-Gesicht für den Tabellenkopf.

    Args:
        kind: ``"happy"``, ``"neutral"`` oder (jeder andere Wert) traurig.

    Returns:
        Eine reportlab-``Drawing``, direkt als Tabellenzelle verwendbar.
    """
    drawing = Drawing(16, 16)
    drawing.add(Circle(8, 8, 7, strokeColor=colors.black, fillColor=None, strokeWidth=1))
    drawing.add(Circle(5.5, 10.5, 0.8, strokeColor=colors.black, fillColor=colors.black, strokeWidth=0.6))
    drawing.add(Circle(10.5, 10.5, 0.8, strokeColor=colors.black, fillColor=colors.black, strokeWidth=0.6))

    if kind == "happy":
        drawing.add(Line(4.4, 5.2, 6.5, 3.8, strokeColor=colors.black, strokeWidth=1.1))
        drawing.add(Line(6.5, 3.8, 9.5, 3.6, strokeColor=colors.black, strokeWidth=1.1))
        drawing.add(Line(9.5, 3.6, 11.6, 5.0, strokeColor=colors.black, strokeWidth=1.1))
    elif kind == "neutral":
        drawing.add(Line(4.8, 4.4, 11.2, 4.4, strokeColor=colors.black, strokeWidth=1))
    else:
        drawing.add(Line(4.8, 3.8, 8.0, 5.4, strokeColor=colors.black, strokeWidth=1))
        drawing.add(Line(8.0, 5.4, 11.2, 3.8, strokeColor=colors.black, strokeWidth=1))

    return drawing
