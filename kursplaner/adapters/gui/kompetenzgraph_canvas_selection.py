from __future__ import annotations

from kursplaner.adapters.gui.kompetenzgraph_ui_state import KompetenzGraphUiState
from kursplaner.core.domain.kompetenzgraph_arrow_navigation import find_nearest_node_in_direction
from kursplaner.core.domain.kompetenzgraph_layout import KompetenzGraphLayout
from kursplaner.core.domain.kompetenzgraph_view import KompetenzGraphView


def handle_single_click(state: KompetenzGraphUiState, node_id: str) -> None:
    """Einfacher Klick: setzt NUR die Auswahl (Rahmen), ein bestehender Fokus bleibt unverändert.

    Spezifikation: "Bei einfachem Klick auf eine andere Kompetenz wird
    diese andere Kompetenz zwar ausgewählt ..., der Fokus ... bleibt
    jedoch beim alten."
    """
    state.selected_id = node_id


def handle_double_click_or_enter(state: KompetenzGraphUiState, node_id: str | None = None) -> None:
    """Doppelklick (auf `node_id`) oder Enter (auf der aktuellen Auswahl, `node_id=None`) togglet den Fokus.

    - Ziel ist bereits der aktuelle Fokus → Fokus wird aufgehoben (zweiter
      Doppelklick/Enter auf denselben Knoten schließt die Fokusansicht).
    - Ziel ist ein ANDERER Knoten als der bisherige Fokus (oder es gibt
      noch keinen Fokus) → dieser wird der neue Fokus UND die neue
      Auswahl (ein Doppelklick wählt implizit auch aus, falls noch nicht
      geschehen).

    Args:
        state: Der zu mutierende UI-Zustand.
        node_id: Bei Doppelklick die angeklickte Knoten-ID; bei Enter
            `None` (dann wird `state.selected_id` als Ziel verwendet).
    """
    target = node_id if node_id is not None else state.selected_id
    if target is None:
        return
    if state.focus_id == target:
        state.focus_id = None
    else:
        state.focus_id = target
        state.selected_id = target


def select_nearest_in_direction(
    state: KompetenzGraphUiState,
    layout: KompetenzGraphLayout,
    view: KompetenzGraphView,
    direction: tuple[float, float],
) -> bool:
    """Bewegt `state.selected_id` auf den nächstgelegenen sichtbaren Knoten im 60°-Kegel Richtung `direction`.

    Ausgelagert aus `kompetenzgraph_dialog.py` (300-Zeilen-Budget) --
    reine Zustandsmutation ohne Canvas-Zugriff, damit sie unabhängig vom
    Dialog testbar bleibt. Kandidaten kommen aus der übergebenen
    Momentaufnahme (`layout`/`view`, im Dialog `self._last_layout`/
    `self._last_view`) -- Bereich-Hubs sind nie Kandidaten, da sie nicht
    in `view.visible.all_ids` (nur Kompetenz-Knoten) auftauchen.

    Returns:
        `True`, wenn ein näherer Knoten gefunden und `state.selected_id`
        entsprechend geändert wurde; `False`, wenn keine Bewegung
        stattfand (keine Auswahl, keine Position, kein Kandidat im
        Kegel) -- der Aufrufer soll dann kein Re-Render/Recenter auslösen.
    """
    if state.selected_id is None:
        return False
    current_position = layout.positions.get(state.selected_id)
    if current_position is None:
        return False

    candidates = {
        node_id: (position.x, position.y)
        for node_id, position in layout.positions.items()
        if node_id != state.selected_id and node_id in view.visible.all_ids
    }
    nearest_id = find_nearest_node_in_direction((current_position.x, current_position.y), candidates, direction)
    if nearest_id is None:
        return False

    state.selected_id = nearest_id
    return True
