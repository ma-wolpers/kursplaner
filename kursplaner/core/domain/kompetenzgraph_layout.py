from __future__ import annotations

from dataclasses import dataclass

from kursplaner.core.domain.kompetenzgraph_dag import find_back_edges
from kursplaner.core.domain.kompetenzgraph_diagnostics import UnresolvedLink
from kursplaner.core.domain.kompetenzgraph_layout_crossing import (
    MAX_NODES_FOR_CROSSING_MINIMIZATION,
    minimize_crossings,
)
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.kompetenzgraph_view_mode import ancestors_of

_LAYER_SPACING = 150.0
_NODE_SPACING = 170.0
_BEREICH_ROW_Y = -220.0
_UNRESOLVED_MARKER_OFFSET_X = 90.0
_UNRESOLVED_MARKER_OFFSET_Y = 60.0


@dataclass(frozen=True)
class GraphNodePosition:
    """Eine berechnete Bildschirm-/Weltkoordinate (kein Zoom/Pan-Zustand -- das ist Sache des Canvas-Renderers)."""

    x: float
    y: float


@dataclass(frozen=True)
class KompetenzGraphLayout:
    """Vollständiges Layout-Ergebnis für eine aktuell sichtbare Knotenmenge.

    Attributes:
        positions: Positionen aller echten Kompetenz- UND Bereichs-Hub-
            Knoten (Bereich-Hubs immer in einer festen Zeile, siehe
            Modul-Konstante `_BEREICH_ROW_Y` -- eine reine
            Rendering-Entscheidung dieses Koordinatenzuweisungs-Schritts,
            keine Graph-Invariante).
        unresolved_marker_positions: Positionen für Unresolved-Link-
            Platzhalter, versetzt neben dem jeweils referenzierenden
            echten Knoten. Nehmen nie an Schichtzuordnung/Crossing-
            Minimierung teil und beeinflussen nie die Positionen echter
            Knoten.
    """

    positions: dict[str, GraphNodePosition]
    unresolved_marker_positions: dict[UnresolvedLink, GraphNodePosition]


def _build_visible_parent_edges(
    snapshot: KompetenzGraphSnapshot, mode_key: str, visible_node_ids: frozenset[str]
) -> dict[str, tuple[str, ...]]:
    """Baut das Eltern-Kantenbild (Kind→Eltern) beschränkt auf die aktuell sichtbare Knotenmenge."""
    return {
        node_id: tuple(parent for parent in ancestors_of(snapshot, mode_key, node_id) if parent in visible_node_ids)
        for node_id in visible_node_ids
    }


def _assign_layers(
    visible_node_ids: frozenset[str], acyclic_parent_edges: dict[str, tuple[str, ...]]
) -> dict[str, int]:
    """Topologische (Kahn-artige) Schichtzuordnung: `layer(node) = 1 + max(layer(eltern))`, 0 ohne Eltern.

    Iterativ statt rekursiv (kein Python-Rekursionslimit-Risiko bei tiefen
    Ketten). Erwartet ein bereits azyklisches Kantenbild (Rückkanten vorher
    über `find_back_edges()` entfernt) -- sonst würde kein Knoten des
    Zyklus je Eingrad 0 erreichen.
    """
    children_of: dict[str, list[str]] = {node_id: [] for node_id in visible_node_ids}
    in_degree: dict[str, int] = {}
    for node_id in visible_node_ids:
        parents = acyclic_parent_edges.get(node_id, ())
        in_degree[node_id] = len(parents)
        for parent in parents:
            children_of.setdefault(parent, []).append(node_id)

    layer: dict[str, int] = {}
    remaining_in_degree = dict(in_degree)
    frontier = sorted(node_id for node_id, degree in in_degree.items() if degree == 0)

    while frontier:
        next_frontier: list[str] = []
        for node_id in frontier:
            parents = acyclic_parent_edges.get(node_id, ())
            layer[node_id] = 1 + max(layer[parent] for parent in parents) if parents else 0
            for child in children_of.get(node_id, ()):
                remaining_in_degree[child] -= 1
                if remaining_in_degree[child] == 0:
                    next_frontier.append(child)
        frontier = sorted(next_frontier)

    return layer


def compute_layered_layout(
    snapshot: KompetenzGraphSnapshot,
    mode_key: str,
    visible_node_ids: frozenset[str],
    visible_bereich_ids: frozenset[str],
) -> KompetenzGraphLayout:
    """Berechnet das vollständige Sugiyama-artige Layout für die aktuell sichtbare Menge.

    Pipeline: (1) Rückkanten nur für die Tiefenberechnung neutralisieren
    (`find_back_edges`, geteilt mit der Zyklen-Diagnose), (2) topologische
    Schichtzuordnung, (3) deterministisch nach `(primarer_bereich_id, id)`
    initial sortieren, (4) Crossing-Minimierung (übersprungen oberhalb von
    `MAX_NODES_FOR_CROSSING_MINIMIZATION` -- Performance-Budget, keine
    fachliche Grenze), (5) Koordinatenzuweisung. Bereich-Hubs bekommen
    unabhängig davon immer eine feste eigene Zeile.

    Args:
        snapshot: Das vollständige Kompetenznetz-Snapshot.
        mode_key: Der aktuell aktive View-Mode.
        visible_node_ids: Aktuell sichtbare Kompetenz-Knoten (Primär- UND
            Kontextknoten, siehe `KompetenzGraphVisibleSet.all_ids`).
        visible_bereich_ids: Aktuell sichtbare Bereichs-Hubs.

    Returns:
        Das vollständige `KompetenzGraphLayout`.
    """
    parent_edges = _build_visible_parent_edges(snapshot, mode_key, visible_node_ids)
    back_edges = find_back_edges(parent_edges)
    acyclic_parent_edges = {
        node_id: tuple(parent for parent in parents if (node_id, parent) not in back_edges)
        for node_id, parents in parent_edges.items()
    }

    layer_by_node = _assign_layers(visible_node_ids, acyclic_parent_edges)

    layers: dict[int, list[str]] = {}
    for node_id in visible_node_ids:
        layers.setdefault(layer_by_node[node_id], []).append(node_id)

    sorted_layers: dict[int, tuple[str, ...]] = {}
    for layer_index, node_ids in layers.items():
        sorted_layers[layer_index] = tuple(
            sorted(node_ids, key=lambda nid: (snapshot.nodes[nid].primarer_bereich_id or "", nid))
        )

    if len(visible_node_ids) <= MAX_NODES_FOR_CROSSING_MINIMIZATION:
        # Crossing-Minimierung nutzt bewusst das VOLLE Kantenbild (inkl. der als
        # Rückkante klassifizierten Kanten) -- die Rückkanten-Klassifikation gilt
        # nur für die Tiefenberechnung, nicht für die Rendering-/Layout-Qualität.
        sorted_layers = minimize_crossings(sorted_layers, parent_edges)

    positions: dict[str, GraphNodePosition] = {}
    for layer_index in sorted(sorted_layers):
        for position_index, node_id in enumerate(sorted_layers[layer_index]):
            positions[node_id] = GraphNodePosition(x=position_index * _NODE_SPACING, y=layer_index * _LAYER_SPACING)

    for position_index, bereich_id in enumerate(sorted(visible_bereich_ids)):
        positions[bereich_id] = GraphNodePosition(x=position_index * _NODE_SPACING, y=_BEREICH_ROW_Y)

    unresolved_marker_positions: dict[UnresolvedLink, GraphNodePosition] = {}
    marker_index_by_source: dict[str, int] = {}
    for link in snapshot.unresolved_links:
        source_position = positions.get(link.source_id)
        if source_position is None:
            continue
        marker_index = marker_index_by_source.get(link.source_id, 0)
        marker_index_by_source[link.source_id] = marker_index + 1
        unresolved_marker_positions[link] = GraphNodePosition(
            x=source_position.x + _UNRESOLVED_MARKER_OFFSET_X,
            y=source_position.y + _UNRESOLVED_MARKER_OFFSET_Y * (marker_index + 1),
        )

    return KompetenzGraphLayout(positions=positions, unresolved_marker_positions=unresolved_marker_positions)
