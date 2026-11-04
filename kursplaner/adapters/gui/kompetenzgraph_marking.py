"""Markieren von Kompetenzen im Kompetenznetz-Popup (für die Übernahme in eine Sequenzleiter).

Reine Zustandsänderungen auf `KompetenzGraphUiState.marked_ids`; keine Tk-,
keine Datei-Logik. „Alle gefilterten markieren“ nimmt nur echte Filtertreffer
(`visible.primary_ids`), keine gedimmten Kontextknoten, und nur
Kompetenz-Knoten (keine Bereichs-Hubs).
"""

from __future__ import annotations

from kursplaner.adapters.gui.kompetenzgraph_ui_state import KompetenzGraphUiState
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.kompetenzgraph_view import KompetenzGraphView


def toggle_mark(state: KompetenzGraphUiState, snapshot: KompetenzGraphSnapshot, node_id: str) -> None:
    """Schaltet die Markierung einer Kompetenz um (Bereichs-Hubs werden ignoriert)."""
    if node_id in snapshot.nodes:
        state.marked_ids = state.marked_ids ^ {node_id}


def mark_visible(state: KompetenzGraphUiState, snapshot: KompetenzGraphSnapshot, view: KompetenzGraphView) -> None:
    """Markiert zusätzlich alle aktuellen Filtertreffer (ohne Kontextknoten)."""
    state.marked_ids = state.marked_ids | {node_id for node_id in view.visible.primary_ids if node_id in snapshot.nodes}


def clear_marks(state: KompetenzGraphUiState) -> None:
    """Hebt alle Markierungen auf."""
    state.marked_ids = frozenset()
