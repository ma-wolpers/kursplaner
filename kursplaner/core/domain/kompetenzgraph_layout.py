from __future__ import annotations

from dataclasses import dataclass

from kursplaner.core.domain.kompetenzgraph_dag import find_back_edges
from kursplaner.core.domain.kompetenzgraph_diagnostics import UnresolvedLink
from kursplaner.core.domain.kompetenzgraph_layout_forces import (
    MAX_NODES_FOR_RELAXATION,
    compute_bereich_centroid_positions,
    relax_horizontal_positions,
)
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.kompetenzgraph_view_mode import ancestors_of

_LAYER_SPACING = 180.0
_NODE_SPACING = 110.0
_BEREICH_SPACING = 190.0
"""Mindestabstand zwischen Bereich-Hub-Mittelpunkten: 170.0 (muss mit
`kompetenzgraph_canvas_render.py::_BEREICH_WIDTH` übereinstimmen) + 20.0 sichtbarer Zwischenraum.
Eigene Konstante statt Wiederverwendung von `_NODE_SPACING` (110.0, für die schmaleren
92px-Kompetenz-Boxen bemessen) -- deren Wiederverwendung erzeugte real 5 von 8 überlappenden
Hub-Paaren im Informatik-Vault (Bereich-Hubs sind mit 170px deutlich breiter als Kompetenz-Knoten).
Diese Datei (core/domain) darf `_BEREICH_WIDTH` nicht importieren (Hexagonal-Architektur: Domain
importiert nicht aus adapters/gui) -- die Übereinstimmung wird stattdessen durch einen bewussten
Cross-Layer-Contract-Test erzwungen, siehe
`test_bereich_spacing_constant_stays_wider_than_render_width` in test_kompetenzgraph_layout.py."""
_BEREICH_ROW_Y = -220.0
_UNRESOLVED_MARKER_OFFSET_X = 90.0
_UNRESOLVED_MARKER_OFFSET_Y = 60.0
_VERTICAL_JITTER_PATTERN: tuple[float, ...] = (-20.0, 0.0, 20.0)
"""Kleiner, deterministischer Y-Versatz innerhalb einer Schicht (zyklisch nach Position in der
bereits kräfte-relaxierten Reihenfolge zugewiesen) -- lockert die strenge "eine Reihe"-Optik auf,
ohne die Schicht-Semantik (Y = Hierarchietiefe) zu verletzen: `_LAYER_SPACING` ist bewusst groß
genug gewählt, dass selbst der maximale Versatz nie eine Schichtgrenze überschreitet (siehe
`compute_layered_layout`-Docstring)."""


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
            echten Knoten. Nehmen nie an Schichtzuordnung/Kräfte-Relaxation
            teil und beeinflussen nie die Positionen echter Knoten.
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


def _build_bereich_classification_edges(
    snapshot: KompetenzGraphSnapshot, visible_node_ids: frozenset[str], visible_bereich_ids: frozenset[str]
) -> dict[str, tuple[str, ...]]:
    """Baut das Klassifikations-Kantenbild (Bereich→klassifizierende Kompetenzen) für die Bereichs-Zentroid-Positionierung.

    Berücksichtigt sowohl `primarer_bereich` als auch `prozessbereiche` --
    ein Bereichs-Hub wird also von jeder sichtbaren Kompetenz "angezogen",
    die ihn in einem der beiden Felder referenziert, nicht nur von seiner
    kanonischen (`primarer_bereich`) Klassifikation.
    """
    members: dict[str, list[str]] = {bereich_id: [] for bereich_id in visible_bereich_ids}
    for node_id in visible_node_ids:
        node = snapshot.nodes.get(node_id)
        if node is None:
            continue
        if node.primarer_bereich_id is not None and node.primarer_bereich_id in members:
            members[node.primarer_bereich_id].append(node_id)
        for prozessbereich_id in node.prozessbereich_ids:
            if prozessbereich_id in members:
                members[prozessbereich_id].append(node_id)
    return {bereich_id: tuple(sorted(ids)) for bereich_id, ids in members.items()}


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
    initial sortieren (dient nur als Sweep-0-Startpunkt für Schritt 4, keine
    über den Lauf fixierte Vorgabe -- siehe unten), (4) Koordinatenzuweisung:
    horizontale Position je Schicht per Kräfte-Relaxation
    (`kompetenzgraph_layout_forces.py::relax_horizontal_positions`, zieht
    Knoten Richtung des Medians ihrer verbundenen Nachbarn UND sortiert die
    Schicht dabei nach diesem Ziel neu -- Reihenfolge ist bewusst KEIN
    eigener Optimierungsgegenstand mehr, siehe die ausführliche Begründung
    dort; **Kantenkreuzungen werden dadurch nicht mehr aktiv minimiert**,
    ein bewusst in Kauf genommener, rein visueller Trade-off, die
    tatsächliche Verbindung bleibt über Kante + sichtbaren Andockpunkt am
    Knotenrand erkennbar), oberhalb von `MAX_NODES_FOR_RELAXATION`
    (Performance-Budget, keine fachliche Grenze) bleibt es bei den reinen
    Slot-Index-Startpositionen. Zusätzlich fließt eine Primärbereich-Kohäsion in dieselbe
    Relaxation ein (`bereich_of_node`, ausschließlich `primarer_bereich_id`): verankert Knoten
    ohne jeden sichtbaren Hierarchie-Nachbarn (typisch nach einem Filter, der ihren echten
    Elternteil oder alle Kinder entfernt hat) an ihrem Bereich statt sie arbiträr einzufrieren --
    siehe `kompetenzgraph_layout_forces.py::_apply_bereich_cohesion()` für die vollständige
    Bereichsgruppe/Bereichswaise-Fallunterscheidung. Bereich-Hubs bekommen eine feste eigene
    Zeile, positioniert über dem Schwerpunkt der sie klassifizierenden
    Kompetenzen (`compute_bereich_centroid_positions`) statt alphabetisch.
    Zusätzlich bekommt jeder Kompetenz-Knoten (NICHT die Bereich-Hub-Zeile)
    einen kleinen, zyklischen Y-Versatz (`_VERTICAL_JITTER_PATTERN`) nach
    Position in der Schicht -- rein kosmetisch gegen die sonst sehr
    "reihenartige" Optik, `_LAYER_SPACING` ist bewusst groß genug gewählt,
    dass dabei nie eine Schichtgrenze überschritten wird (Knoten aus
    Schicht N erscheinen nie tiefer als Knoten aus Schicht N+1). Bitgenaue
    Koordinaten-Reproduzierbarkeit über verschiedene Aufrufe hinweg ist
    dabei kein Ziel -- nur innerhalb eines einzelnen Aufrufs verhält sich
    die Positionierung nachvollziehbar deterministisch.

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

    within_performance_budget = len(visible_node_ids) <= MAX_NODES_FOR_RELAXATION
    # `bereich_of_node` treibt die Primärbereich-Kohäsion in `relax_horizontal_positions()` --
    # ausschließlich `primarer_bereich_id`, niemals `prozessbereiche` (siehe dortige Docstrings
    # für die vollständige Bereichsgruppe/Bereichswaise-Fallunterscheidung). Verankert Knoten, die
    # durch einen Filter zu Hierarchie-Waisen wurden, an ihrem Bereich statt sie an ihrer
    # arbiträren Slot-Index-Startposition einfrieren zu lassen.
    bereich_of_node = {
        node_id: snapshot.nodes[node_id].primarer_bereich_id
        for node_id in visible_node_ids
        if snapshot.nodes[node_id].primarer_bereich_id is not None
    }
    # `sorted_layers` dient `relax_horizontal_positions()` nur als Sweep-0-Startpunkt -- die
    # Reihenfolge ist danach kein eigener Optimierungsgegenstand mehr, sie folgt den Kräften
    # (siehe dortige Begründung). Oberhalb des Performance-Budgets bleibt es bei den reinen
    # Slot-Index-Startpositionen (iterations=0).
    x_by_node = relax_horizontal_positions(
        sorted_layers,
        parent_edges,
        iterations=6 if within_performance_budget else 0,
        min_spacing=_NODE_SPACING,
        bereich_of_node=bereich_of_node,
    )

    positions: dict[str, GraphNodePosition] = {}
    for layer_index, node_ids in layers.items():
        # Für den Y-Versatz (rein kosmetisch) nach der TATSÄCHLICHEN finalen X-Position
        # sortieren, nicht nach der längst überholten Sweep-0-Startreihenfolge.
        final_order = sorted(node_ids, key=lambda nid: (x_by_node[nid], nid))
        for position_index, node_id in enumerate(final_order):
            jitter = _VERTICAL_JITTER_PATTERN[position_index % len(_VERTICAL_JITTER_PATTERN)]
            positions[node_id] = GraphNodePosition(x=x_by_node[node_id], y=layer_index * _LAYER_SPACING + jitter)

    bereich_classification_edges = _build_bereich_classification_edges(snapshot, visible_node_ids, visible_bereich_ids)
    node_x_by_id = {node_id: position.x for node_id, position in positions.items()}
    bereich_x_by_id = compute_bereich_centroid_positions(
        visible_bereich_ids, node_x_by_id, bereich_classification_edges, min_spacing=_BEREICH_SPACING
    )
    for bereich_id, x in bereich_x_by_id.items():
        positions[bereich_id] = GraphNodePosition(x=x, y=_BEREICH_ROW_Y)

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
