from __future__ import annotations

import math
from collections.abc import Mapping

_INV_SQRT2 = math.sqrt(0.5)

DIRECTION_VECTORS: dict[str, tuple[float, float]] = {
    "N": (0.0, -1.0),
    "NE": (_INV_SQRT2, -_INV_SQRT2),
    "E": (1.0, 0.0),
    "SE": (_INV_SQRT2, _INV_SQRT2),
    "S": (0.0, 1.0),
    "SW": (-_INV_SQRT2, _INV_SQRT2),
    "W": (-1.0, 0.0),
    "NW": (-_INV_SQRT2, -_INV_SQRT2),
}
"""Normierte Richtungsvektoren für die Pfeiltasten-Navigation, in Canvas-Koordinaten
(y wächst nach unten, wie bei tkinter.Canvas üblich -- "N"/oben ist daher (0, -1)).

Die GUI-Schicht (`kompetenzgraph_canvas_arrow_nav.py`, Meilenstein 5) kombiniert
gleichzeitig gehaltene Pfeiltasten (z. B. Oben+Rechts für "obenrechts") zu einem
addierten, hier NICHT vordefinierten Vektor und übergibt diesen direkt an
`find_nearest_node_in_direction()` -- diese Konstante dient als Nachschlagewerk
für den einfachen Einzeltasten-Fall bzw. als Referenz für die erwartete
Koordinatenkonvention, nicht als abschließende Liste erlaubter Richtungen."""


def _normalize(vector: tuple[float, float]) -> tuple[float, float] | None:
    """Normiert einen Vektor auf Länge 1, oder `None` für den Nullvektor (keine Richtung)."""
    x, y = vector
    length = math.hypot(x, y)
    if length == 0.0:
        return None
    return x / length, y / length


def _angle_between_degrees(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Berechnet den Winkel zwischen zwei bereits normierten Vektoren in Grad (0-180)."""
    dot_product = a[0] * b[0] + a[1] * b[1]
    cos_theta = max(-1.0, min(1.0, dot_product))  # Fließkomma-Rundung kann knapp außerhalb [-1, 1] liegen
    return math.degrees(math.acos(cos_theta))


def find_nearest_node_in_direction(
    current_pos: tuple[float, float],
    candidates: Mapping[str, tuple[float, float]],
    direction: tuple[float, float],
    *,
    cone_half_angle_degrees: float = 30.0,
) -> str | None:
    """Findet den optisch nächstgelegenen Kandidaten innerhalb eines Kegels um `direction`.

    Reine, tkinter-freie Funktion für die Pfeiltasten-Navigation: berechnet
    für jeden Kandidaten den Winkel zwischen seinem Richtungsvektor (relativ
    zu `current_pos`) und `direction`; Kandidaten außerhalb des Kegels
    (`cone_half_angle_degrees` auf beiden Seiten von `direction`, macht
    insgesamt einen 60°-Kegel bei Standardwert 30°) werden ignoriert.
    Unter den verbleibenden gewinnt der euklidisch nächste, bei Gleichstand
    der mit dem kleineren Winkel, bei erneutem Gleichstand die
    lexikalisch kleinere ID (stabiler, deterministischer Tie-Break).

    `candidates` sollte den aktuell ausgewählten Knoten selbst NICHT
    enthalten -- ein Kandidat exakt an `current_pos` (Vektor-Länge 0) wird
    aber defensiv ohnehin übersprungen, da für ihn kein Winkel definiert
    ist.

    Args:
        current_pos: `(x, y)`-Position des aktuell ausgewählten Knotens.
        candidates: Zu prüfende Kandidaten, ID → `(x, y)`-Position. Sollte
            immer nur die aktuell sichtbare Knotenmenge enthalten (siehe
            `KompetenzGraphView.visible.all_ids`), nie Unresolved-Link-
            Platzhalter.
        direction: Gewünschte Bewegungsrichtung (muss nicht normiert
            sein, nur nicht der Nullvektor).
        cone_half_angle_degrees: Halber Öffnungswinkel des Kegels in
            Grad.

    Returns:
        Die ID des gewählten Kandidaten, oder `None`, wenn `direction`
        der Nullvektor ist oder kein Kandidat im Kegel liegt (Taste dann
        ohne Effekt).
    """
    normalized_direction = _normalize(direction)
    if normalized_direction is None:
        return None

    best_key: tuple[float, float, str] | None = None
    best_id: str | None = None

    for candidate_id, candidate_pos in candidates.items():
        offset = (candidate_pos[0] - current_pos[0], candidate_pos[1] - current_pos[1])
        normalized_offset = _normalize(offset)
        if normalized_offset is None:
            continue

        angle = _angle_between_degrees(normalized_offset, normalized_direction)
        if angle > cone_half_angle_degrees:
            continue

        distance = math.hypot(*offset)
        key = (distance, angle, candidate_id)
        if best_key is None or key < best_key:
            best_key = key
            best_id = candidate_id

    return best_id
