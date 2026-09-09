from __future__ import annotations

import time
from collections.abc import Callable

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui

from kursplaner.core.domain.kompetenzgraph_arrow_navigation import DIRECTION_VECTORS

_COMBINE_WINDOW_SECONDS = 0.15
"""Zeitfenster, innerhalb dessen mehrere Pfeiltasten als "gleichzeitig gedrückt" gelten
(ermöglicht Diagonalen wie "obenrechts" bei annähernd gleichzeitigem Tastendruck)."""

_KEYSYM_TO_VECTOR: dict[str, tuple[float, float]] = {
    "Up": DIRECTION_VECTORS["N"],
    "Down": DIRECTION_VECTORS["S"],
    "Left": DIRECTION_VECTORS["W"],
    "Right": DIRECTION_VECTORS["E"],
}


class KompetenzGraphCanvasArrowNav:
    """Kombiniert kurz gemeinsam gehaltene Pfeiltasten zu einem addierten Richtungsvektor.

    Reine Timing-/Kombinationslogik -- ruft `on_direction(vektor)` bei
    jedem Pfeiltastendruck mit der Summe aller innerhalb von
    `_COMBINE_WINDOW_SECONDS` gehaltenen Richtungen auf. Die eigentliche
    Kegel-/Distanz-/Tie-Break-Auswahl geschieht extern über die bereits
    domain-seitig getestete, reine Funktion
    `kompetenzgraph_arrow_navigation.find_nearest_node_in_direction()`
    -- diese Klasse kennt weder Knotenpositionen noch Auswahlzustand.
    """

    def __init__(self, canvas: ui.Canvas, *, on_direction: Callable[[tuple[float, float]], None]):
        """Bindet Pfeiltasten-Presses auf `canvas`.

        Args:
            canvas: Der Canvas, der den Tastaturfokus für die Navigation
                trägt.
            on_direction: Wird mit dem kombinierten `(dx, dy)`-Vektor
                aufgerufen, sobald eine Pfeiltaste gedrückt wird.
        """
        self.canvas = canvas
        self._on_direction = on_direction
        self._held_keys: dict[str, float] = {}
        for keysym in _KEYSYM_TO_VECTOR:
            canvas.bind(f"<KeyPress-{keysym}>", self._on_key_press, add="+")

    def _on_key_press(self, event) -> str:
        now = time.monotonic()
        self._held_keys = {
            key: pressed_at
            for key, pressed_at in self._held_keys.items()
            if now - pressed_at <= _COMBINE_WINDOW_SECONDS
        }
        self._held_keys[event.keysym] = now

        combined_x = sum(_KEYSYM_TO_VECTOR[key][0] for key in self._held_keys)
        combined_y = sum(_KEYSYM_TO_VECTOR[key][1] for key in self._held_keys)
        self._on_direction((combined_x, combined_y))
        return "break"
