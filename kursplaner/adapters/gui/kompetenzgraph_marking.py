"""Markieren von Kompetenzen im Kompetenznetz-Popup (für die Übernahme in eine Sequenzleiter).

Reine Zustandsänderungen auf `KompetenzGraphUiState.marked_ids`; keine Tk-,
keine Datei-Logik. „Alle gefilterten markieren“ nimmt nur echte Filtertreffer
(`visible.primary_ids`), keine gedimmten Kontextknoten, und nur
Kompetenz-Knoten (keine Bereichs-Hubs). Was überhaupt markierbar ist, entscheidet
das übergebene Prädikat *markable* (in der Übernahme-Leiste:
`sequence_ladder_import.ladder_import_problem` – z. B. keine inhaltsbezogenen
Hauptkompetenzen); nicht markierbare Kompetenzen werden still übergangen.
"""

from __future__ import annotations

from collections.abc import Callable

from kursplaner.adapters.gui.kompetenzgraph_ui_state import KompetenzGraphUiState
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.kompetenzgraph_view import KompetenzGraphView


def _always(_node_id: str) -> bool:
    return True


def toggle_mark(
    state: KompetenzGraphUiState,
    snapshot: KompetenzGraphSnapshot,
    node_id: str,
    markable: Callable[[str], bool] = _always,
) -> None:
    """Schaltet die Markierung einer Kompetenz um (Bereichs-Hubs und nicht markierbare werden ignoriert).

    Eine bereits markierte Kompetenz lässt sich immer abwählen.
    """
    if node_id in state.marked_ids:
        state.marked_ids = state.marked_ids - {node_id}
    elif node_id in snapshot.nodes and markable(node_id):
        state.marked_ids = state.marked_ids | {node_id}


def mark_visible(
    state: KompetenzGraphUiState,
    snapshot: KompetenzGraphSnapshot,
    view: KompetenzGraphView,
    markable: Callable[[str], bool] = _always,
) -> None:
    """Markiert zusätzlich alle aktuellen, markierbaren Filtertreffer (ohne Kontextknoten)."""
    state.marked_ids = state.marked_ids | {
        node_id for node_id in view.visible.primary_ids if node_id in snapshot.nodes and markable(node_id)
    }


def clear_marks(state: KompetenzGraphUiState) -> None:
    """Hebt alle Markierungen auf."""
    state.marked_ids = frozenset()
