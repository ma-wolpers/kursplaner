from __future__ import annotations

from kursplaner.adapters.gui.kompetenzgraph_ui_state import KompetenzGraphUiState


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
