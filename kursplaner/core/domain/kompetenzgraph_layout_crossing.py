from __future__ import annotations

from collections.abc import Mapping

MAX_NODES_FOR_CROSSING_MINIMIZATION = 2000
"""Performance-Budget (technische Grenze, KEINE fachliche): oberhalb dieser sichtbaren
Knotenzahl wird `minimize_crossings()` vom Layout-Orchestrator (`kompetenzgraph_layout.py`)
gar nicht erst aufgerufen -- es bleibt bei der deterministisch Tie-Break-sortierten
Schichtreihenfolge. In der Praxis unkritisch, da Filter/Fokus/Matchingtiefe die sichtbare
Menge im Normalfall klein halten; verhindert aber, dass ein sehr großes, künftig
fachübergreifendes Vault die Berechnung unbegrenzt verlängert."""

_DEFAULT_MAX_SWEEPS = 8


def count_crossings(layers: Mapping[int, tuple[str, ...]], edges: Mapping[str, tuple[str, ...]]) -> int:
    """Zählt Kantenkreuzungen zwischen JEWEILS BENACHBARTEN Schichten.

    Kanten, die mehr als eine Schicht überspringen (Multi-Parent-DAGs mit
    unterschiedlich tiefen Elternpfaden), tragen nicht zur Zählung bei --
    sie werden weiterhin vollständig gerendert (`kompetenzgraph_canvas_render.py`),
    beeinflussen aber nicht die Optimierung der Schichtreihenfolge. Das ist
    eine bewusste Vereinfachung gegenüber "echtem" Sugiyama-Layout (das
    solche Kanten über Dummy-Knoten durch jede übersprungene Schicht führt)
    -- angemessen für das Ziel "sichtbar gute, reproduzierbare Ergebnisse",
    nicht "mathematisch perfektes Crossing-Minimum".

    Args:
        layers: Schicht-Index → geordnete Knoten-IDs dieser Schicht.
        edges: Knoten-ID → Tupel der Eltern-IDs (Kind→Eltern-Richtung, wie
            von `ancestors_of()` geliefert).

    Returns:
        Gesamtzahl der Kreuzungen über alle Schichtgrenzen hinweg.
    """
    sorted_indices = sorted(layers)
    total = 0
    for i in range(len(sorted_indices) - 1):
        total += _count_crossings_between(layers[sorted_indices[i]], layers[sorted_indices[i + 1]], edges)
    return total


def _count_crossings_between(
    upper: tuple[str, ...], lower: tuple[str, ...], edges: Mapping[str, tuple[str, ...]]
) -> int:
    """Zählt Kreuzungen zwischen genau zwei benachbarten Schichten in O(E log E).

    Klassischer Bilayer-Cross-Counting-Algorithmus (Barth/Mutzel/Jünger):
    pro Knoten der unteren Schicht werden die Positionen seiner Eltern in
    der oberen Schicht aufsteigend sortiert gesammelt (verhindert
    Scheinkreuzungen zwischen Kanten, die im selben unteren Knoten
    zusammenlaufen), die Teilsequenzen in Reihenfolge der unteren Schicht
    aneinandergehängt, und die Gesamtzahl der Inversionen der
    resultierenden Sequenz per Merge-Sort gezählt -- äquivalent zur
    naiven O(E²)-Paarprüfung, aber praktikabel für größere Graphen.
    """
    upper_position = {node_id: index for index, node_id in enumerate(upper)}
    sequence: list[int] = []
    for lower_node in lower:
        connected_upper_positions = sorted(
            upper_position[parent] for parent in edges.get(lower_node, ()) if parent in upper_position
        )
        sequence.extend(connected_upper_positions)
    return _count_inversions(sequence)


def _count_inversions(sequence: list[int]) -> int:
    """Zählt Inversionen einer Zahlenfolge per Merge-Sort (O(n log n))."""
    if len(sequence) < 2:
        return 0
    _merged, inversions = _merge_sort_count(sequence)
    return inversions


def _merge_sort_count(sequence: list[int]) -> tuple[list[int], int]:
    if len(sequence) <= 1:
        return sequence, 0
    mid = len(sequence) // 2
    left, left_inversions = _merge_sort_count(sequence[:mid])
    right, right_inversions = _merge_sort_count(sequence[mid:])

    merged: list[int] = []
    inversions = left_inversions + right_inversions
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            j += 1
            inversions += len(left) - i
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged, inversions


def _reorder_by_barycenter(
    node_ids: tuple[str, ...], other_layer_position: Mapping[str, int], neighbor_map: Mapping[str, tuple[str, ...]]
) -> tuple[str, ...]:
    """Sortiert eine Schicht nach dem Baryzentrum (Mittelwert der Nachbarpositionen in der Nachbarschicht).

    Ein Knoten ohne jede Verbindung zur Nachbarschicht behält seine
    bisherige relative Position (Fallback auf den aktuellen eigenen Index)
    statt an eine willkürliche feste Stelle zu springen.
    """
    current_position = {node_id: index for index, node_id in enumerate(node_ids)}

    def sort_key(node_id: str) -> tuple[float, str]:
        neighbor_positions = [
            other_layer_position[neighbor]
            for neighbor in neighbor_map.get(node_id, ())
            if neighbor in other_layer_position
        ]
        barycenter = (
            sum(neighbor_positions) / len(neighbor_positions)
            if neighbor_positions
            else float(current_position[node_id])
        )
        return (barycenter, node_id)

    return tuple(sorted(node_ids, key=sort_key))


def minimize_crossings(
    layers: Mapping[int, tuple[str, ...]],
    edges: Mapping[str, tuple[str, ...]],
    *,
    max_sweeps: int = _DEFAULT_MAX_SWEEPS,
) -> dict[int, tuple[str, ...]]:
    """Barycenter-Heuristik zur Reduktion von Schicht-Kreuzungen -- garantiert nie schlechter als die Eingabe.

    Abwechselnde Top-Down-/Bottom-Up-Sweeps: bei einem Top-Down-Sweep wird
    jede Schicht (von oben nach unten) anhand der bereits fixierten
    Nachbarschicht darüber neu sortiert (Baryzentrum der Elternpositionen);
    bei Bottom-Up umgekehrt (Baryzentrum der Kindpositionen). Nach jedem
    Sweep wird die neue Kreuzungszahl geprüft: nur Verbesserungen werden
    übernommen (der nächste Sweep setzt darauf auf), eine Verschlechterung
    oder ein Gleichstand beendet die Optimierung sofort -- das
    Endergebnis ist damit garantiert nie schlechter als die
    Eingangsreihenfolge. Alle Sortierungen nutzen einen stabilen,
    ID-basierten Tie-Break: identischer Input liefert immer identischen
    Output (Determinismus-Pflicht).

    Args:
        layers: Schicht-Index → initiale (z. B. nach `(bereich_id, id)`
            sortierte) Knotenreihenfolge dieser Schicht.
        edges: Knoten-ID → Tupel der Eltern-IDs.
        max_sweeps: Obergrenze der Sweeps (Performance-Budget, technische
            Grenze).

    Returns:
        Die (ggf. unveränderte) optimierte Schichtreihenfolge.
    """
    sorted_indices = sorted(layers)
    best_order: dict[int, tuple[str, ...]] = {index: tuple(layers[index]) for index in sorted_indices}
    if len(sorted_indices) < 2:
        return best_order

    best_crossings = count_crossings(best_order, edges)
    if best_crossings == 0:
        return best_order

    children_of: dict[str, tuple[str, ...]] = {}
    children_accumulator: dict[str, list[str]] = {}
    for node_id, parents in edges.items():
        for parent in parents:
            children_accumulator.setdefault(parent, []).append(node_id)
    for parent_id, children in children_accumulator.items():
        children_of[parent_id] = tuple(sorted(children))

    current = dict(best_order)
    for sweep_index in range(max_sweeps):
        if sweep_index % 2 == 0:
            for i in range(1, len(sorted_indices)):
                upper_index, lower_index = sorted_indices[i - 1], sorted_indices[i]
                upper_position = {node_id: pos for pos, node_id in enumerate(current[upper_index])}
                current[lower_index] = _reorder_by_barycenter(current[lower_index], upper_position, edges)
        else:
            for i in range(len(sorted_indices) - 2, -1, -1):
                upper_index, lower_index = sorted_indices[i], sorted_indices[i + 1]
                lower_position = {node_id: pos for pos, node_id in enumerate(current[lower_index])}
                current[upper_index] = _reorder_by_barycenter(current[upper_index], lower_position, children_of)

        candidate_crossings = count_crossings(current, edges)
        if candidate_crossings < best_crossings:
            best_crossings = candidate_crossings
            best_order = dict(current)
        else:
            break

    return best_order
