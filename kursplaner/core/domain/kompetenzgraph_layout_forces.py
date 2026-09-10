from __future__ import annotations

from collections.abc import Mapping

_DEFAULT_ITERATIONS = 6
"""Feste Sweep-Anzahl -- reines Performance-Budget, kein Determinismus-Selbstzweck
(siehe Modul-Docstring: bitgenaue Koordinaten-Reproduzierbarkeit über verschiedene
Layout-Läufe hinweg ist ausdrücklich KEIN Ziel dieses Moduls)."""


def _median(values: list[float]) -> float:
    """Median einer nichtleeren Werteliste -- robuster gegen Ausreißer als der Mittelwert."""
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _mean(values: list[float]) -> float:
    """Arithmetisches Mittel einer nichtleeren Werteliste."""
    return sum(values) / len(values)


def _pull_toward_neighbor_median(
    node_ids: tuple[str, ...],
    positions: Mapping[str, float],
    neighbor_map: Mapping[str, tuple[str, ...]],
) -> dict[str, float]:
    """Berechnet je Knoten die Ziel-X-Position als Median ALLER seiner tatsächlichen Nachbarn (`neighbor_map`).

    Bewusst NICHT auf eine bestimmte Nachbarschicht beschränkt: Beim
    longest-path-Layering (`layer(kind) = 1 + max(layer(eltern))`) landen
    zwei direkte Eltern eines Knotens regelmäßig in UNTERSCHIEDLICHEN
    Schichten (der Elternteil mit der tieferen Kette bestimmt die Schicht
    des Kindes, ein anderer Elternteil kann beliebig viele Schichten
    höher liegen). Eine schichtweise Beschränkung (wie sie
    `kompetenzgraph_layout_crossing.py::_reorder_by_barycenter` für die
    Crossing-Zählung korrekt verwendet, da diese inhärent paarweise pro
    Schichtgrenze definiert ist) würde solche "Schicht-überspringenden"
    Eltern/Kinder komplett ignorieren und Knoten fälschlich nur zum
    nächstgelegenen statt zum tatsächlichen Kräftegleichgewicht ziehen.

    Ein Knoten ohne jede Verbindung behält seine bisherige Position
    (`positions[node_id]`) statt an eine willkürliche Stelle zu springen.
    """
    targets: dict[str, float] = {}
    for node_id in node_ids:
        neighbor_positions = [positions[neighbor] for neighbor in neighbor_map.get(node_id, ()) if neighbor in positions]
        targets[node_id] = _median(neighbor_positions) if neighbor_positions else positions[node_id]
    return targets


def _resolve_min_spacing(node_ids: tuple[str, ...], target_x: Mapping[str, float], min_spacing: float) -> dict[str, float]:
    """Rückt Zielpositionen entlang der GEGEBENEN Reihenfolge so auseinander, dass `min_spacing` eingehalten wird.

    `node_ids` bestimmt die verbindliche Reihenfolge (z. B. die bereits
    crossing-minimierte Schicht-Reihenfolge) -- diese Funktion verändert sie
    nie, sondern schiebt bei Bedarf nur nachfolgende Knoten weiter nach
    rechts. Einfacher, deterministischer Links-nach-rechts-Sweep statt
    symmetrischer Verteilung -- für eine reine Darstellungsentscheidung
    ausreichend (siehe Modul-Docstring).
    """
    resolved: dict[str, float] = {}
    previous_x: float | None = None
    for node_id in node_ids:
        x = target_x[node_id]
        if previous_x is not None and x < previous_x + min_spacing:
            x = previous_x + min_spacing
        resolved[node_id] = x
        previous_x = x
    return resolved


def relax_horizontal_positions(
    sorted_layers: Mapping[int, tuple[str, ...]],
    edges: Mapping[str, tuple[str, ...]],
    *,
    iterations: int = _DEFAULT_ITERATIONS,
    min_spacing: float = 170.0,
) -> dict[str, float]:
    """Weist Schicht-internen Knoten eine an ihre Nachbarn angenäherte X-Position statt starrer Slot-Indizes zu.

    Ersetzt die bisherige "Slot-Index × fester Abstand"-Platzierung durch
    eine kräfte-inspirierte Relaxation: abwechselnde Top-Down-/Bottom-Up-
    Sweeps ziehen jeden Knoten Richtung Median-X ALLER seiner Eltern- bzw.
    Kindknoten -- unabhängig davon, in welcher Schicht diese liegen (siehe
    `_pull_toward_neighbor_median`-Docstring: ein Elternteil kann beim
    longest-path-Layering beliebig viele Schichten über dem Kind liegen,
    eine Beschränkung auf die unmittelbar benachbarte Schicht würde solche
    Eltern/Kinder ignorieren und zu falschem Kräfteungleichgewicht führen),
    gefolgt von einer schichtinternen Mindestabstands-Auflösung
    (`_resolve_min_spacing`).

    **Harte Invariante:** Die in `sorted_layers` gegebene Reihenfolge pro
    Schicht (bereits crossing-minimiert) wird NIE verändert -- nur die
    Abstände passen sich an. Es besteht ausdrücklich KEIN Anspruch auf
    bitgenau reproduzierbare Koordinaten über mehrere separate Aufrufe
    hinweg (z. B. bei unterschiedlicher sichtbarer Knotenmenge); Stabilität
    wird nur innerhalb eines einzelnen Aufrufs garantiert.

    Args:
        sorted_layers: Schicht-Index → bereits crossing-minimierte
            Knoten-Reihenfolge dieser Schicht.
        edges: Knoten-ID → Tupel der Eltern-IDs (Kind→Eltern-Richtung,
            wie von `ancestors_of()`/`kompetenzgraph_layout.py` geliefert;
            bewusst das VOLLE Kantenbild inkl. Rückkanten, analog zur
            Crossing-Minimierung).
        iterations: Anzahl der Sweeps (Performance-Budget). `0` liefert
            reine Slot-Index-Startpositionen ohne Relaxation -- genutzt für
            sehr große sichtbare Mengen oberhalb des Crossing-Minimierungs-
            Budgets.
        min_spacing: Mindestabstand zwischen zwei benachbarten Knoten
            derselben Schicht.

    Returns:
        Knoten-ID → berechnete X-Position (nur Hierarchie-Schichten, keine
        Bereichs-Hubs -- siehe `compute_bereich_centroid_positions` dafür).
    """
    layer_indices = sorted(sorted_layers)
    positions: dict[str, float] = {}
    for layer_index in layer_indices:
        for position_index, node_id in enumerate(sorted_layers[layer_index]):
            positions[node_id] = position_index * min_spacing

    if len(layer_indices) < 2 or iterations <= 0:
        return positions

    children_of: dict[str, list[str]] = {}
    for node_id, parents in edges.items():
        for parent in parents:
            children_of.setdefault(parent, []).append(node_id)
    children_of_tuples = {parent: tuple(children) for parent, children in children_of.items()}

    for sweep_index in range(iterations):
        if sweep_index % 2 == 0:
            # Top-Down: Schichten aufsteigend, jeder Knoten wird Richtung des Medians ALLER
            # seiner Eltern gezogen (gleich welcher Schicht) -- Eltern liegen beim
            # longest-path-Layering immer in einer strikt kleineren Schicht und sind in
            # diesem Sweep bereits aktualisiert (Gauss-Seidel-Stil).
            for layer_index in layer_indices[1:]:
                targets = _pull_toward_neighbor_median(sorted_layers[layer_index], positions, edges)
                positions.update(_resolve_min_spacing(sorted_layers[layer_index], targets, min_spacing))
        else:
            # Bottom-Up: Schichten absteigend, Richtung Median ALLER Kinder.
            for layer_index in reversed(layer_indices[:-1]):
                targets = _pull_toward_neighbor_median(sorted_layers[layer_index], positions, children_of_tuples)
                positions.update(_resolve_min_spacing(sorted_layers[layer_index], targets, min_spacing))

    return positions


def compute_bereich_centroid_positions(
    bereich_ids: frozenset[str],
    node_x_by_id: Mapping[str, float],
    classification_edges: Mapping[str, tuple[str, ...]],
    *,
    min_spacing: float = 170.0,
) -> dict[str, float]:
    """Positioniert Bereichs-Hubs über dem Schwerpunkt der sie klassifizierenden Kompetenzen statt alphabetisch.

    X-Position = arithmetisches Mittel der X-Positionen aller sichtbaren
    Kompetenzen, deren `primarer_bereich`/`prozessbereiche` auf diesen Hub
    zeigt (`classification_edges`). Ein Hub ohne sichtbare klassifizierte
    Kompetenz (z. B. isoliert über den Filter erreichbar) fällt auf `0.0`
    zurück. Anschließende Mindestabstands-Auflösung wie bei
    `relax_horizontal_positions`, Reihenfolge nach Schwerpunkt (Tie-Break
    über die ID für Stabilität bei Gleichstand).

    Args:
        bereich_ids: Aktuell sichtbare Bereichs-Hub-IDs.
        node_x_by_id: Bereits berechnete X-Positionen der Kompetenz-Knoten
            (aus `relax_horizontal_positions`).
        classification_edges: Bereichs-ID → Tupel der sie klassifizierenden,
            sichtbaren Kompetenz-IDs.
        min_spacing: Mindestabstand zwischen zwei benachbarten Hubs.

    Returns:
        Bereichs-ID → berechnete X-Position.
    """
    centroid_by_id: dict[str, float] = {}
    for bereich_id in bereich_ids:
        member_positions = [node_x_by_id[node_id] for node_id in classification_edges.get(bereich_id, ()) if node_id in node_x_by_id]
        centroid_by_id[bereich_id] = _mean(member_positions) if member_positions else 0.0

    ordered_ids = tuple(sorted(bereich_ids, key=lambda bereich_id: (centroid_by_id[bereich_id], bereich_id)))
    return _resolve_min_spacing(ordered_ids, centroid_by_id, min_spacing)
