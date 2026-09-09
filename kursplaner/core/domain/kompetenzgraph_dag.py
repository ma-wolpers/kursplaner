from __future__ import annotations

from collections.abc import Iterator, Mapping

from kursplaner.core.domain.kompetenzgraph_diagnostics import CycleDiagnostic
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.kompetenzgraph_types import EdgeKind

_WHITE, _GRAY, _BLACK = 0, 1, 2


def _traverse(edges: Mapping[str, tuple[str, ...]]) -> tuple[frozenset[tuple[str, str]], tuple[tuple[str, ...], ...]]:
    """Einmalige iterative DFS-Traversierung mit weiß/grau/schwarz-Färbung.

    Gemeinsame Grundlage für `find_back_edges()` und `find_cycles()` --
    beide Ergebnisse fallen aus derselben Traversierung ab, ohne den
    Graphen zweimal zu durchlaufen. Iterativ (expliziter Stack statt
    Rekursion), damit auch sehr tiefe Ketten keinen Python-Rekursions-
    limit-Fehler auslösen.

    Jeder Knoten wird über die gesamte Traversierung hinweg genau einmal
    besucht (klassische DFS-Wald-Eigenschaft) -- dadurch wird auch kein
    Zyklus mehrfach über unterschiedliche Startknoten hinweg gemeldet;
    zwei sich überlappende, aber tatsächlich unterschiedliche Zyklen
    (z. B. ein 2er- und ein 3er-Zyklus, die einen Knoten teilen) werden
    dagegen bewusst beide gemeldet, da es sich um zwei verschiedene
    Rückkanten handelt.

    Args:
        edges: Vorwärtskanten-Mapping (Knoten-ID → Tupel der Ziel-IDs).
            Zielwerte, die selbst kein Schlüssel in `edges` sind (z. B.
            weil sie außerhalb des betrachteten Kantentyps liegen oder
            unresolved sind), werden als Senke ohne eigene ausgehende
            Kanten behandelt.

    Returns:
        `(back_edges, cycles)` -- `back_edges` sind alle Kanten, die
        während der DFS auf einen noch offenen (grauen) Vorfahren
        trafen; `cycles` sind die daraus rekonstruierten
        Knoten-Mitgliedschaften (Reihenfolge = Pfad vom Zyklus-Eintritt
        bis zur schließenden Rückkante).
    """
    color: dict[str, int] = {node_id: _WHITE for node_id in edges}
    back_edges: set[tuple[str, str]] = set()
    cycles: list[tuple[str, ...]] = []

    for start in edges:
        if color.get(start, _WHITE) != _WHITE:
            continue

        color[start] = _GRAY
        stack_nodes: list[str] = [start]
        stack_frames: list[Iterator[str]] = [iter(edges.get(start, ()))]

        while stack_frames:
            neighbor = next(stack_frames[-1], None)
            if neighbor is None:
                color[stack_nodes[-1]] = _BLACK
                stack_nodes.pop()
                stack_frames.pop()
                continue

            neighbor_color = color.get(neighbor, _WHITE)
            if neighbor_color == _WHITE:
                color[neighbor] = _GRAY
                stack_nodes.append(neighbor)
                stack_frames.append(iter(edges.get(neighbor, ())))
            elif neighbor_color == _GRAY:
                back_edges.add((stack_nodes[-1], neighbor))
                cycle_start_index = stack_nodes.index(neighbor)
                cycles.append(tuple(stack_nodes[cycle_start_index:]))
            # _BLACK: bereits vollständig ausgewertetes Teilgraph -- Vorwärts-/Querkante, kein Zyklus.

    return frozenset(back_edges), tuple(cycles)


def find_back_edges(edges: Mapping[str, tuple[str, ...]]) -> frozenset[tuple[str, str]]:
    """Liefert alle Rückkanten eines gerichteten Kantenbilds (klassische DFS-Zyklenerkennung).

    Wird von `check_kompetenz_graph_for_cycles()` (reine Diagnose) UND von
    `kompetenzgraph_layout.py` (Zyklen für die Tiefenberechnung neutral
    machen, niemals fürs Rendering) genutzt -- eine gemeinsame
    Implementierung statt zweier unabhängiger DFS-Varianten.
    """
    back_edges, _cycles = _traverse(edges)
    return back_edges


def find_cycles(edges: Mapping[str, tuple[str, ...]]) -> tuple[tuple[str, ...], ...]:
    """Liefert die Knoten-Mitgliedschaften aller gefundenen Zyklen eines Kantenbilds."""
    _back_edges, cycles = _traverse(edges)
    return cycles


def check_kompetenz_graph_for_cycles(snapshot: KompetenzGraphSnapshot) -> tuple[CycleDiagnostic, ...]:
    """Prüft `oberkompetenzen`- und `voraussetzungen`-Kanten getrennt auf Zyklen.

    Reines Diagnoseinstrument, KEIN Render-Guard: das Ergebnis wird von
    `LoadKompetenzGraphUseCase` unverändert an die GUI weitergereicht
    (Warnbanner), beeinflusst aber niemals, ob oder wie vollständig der
    Snapshot selbst aufgebaut/angezeigt wird. Ein Zyklus in
    `voraussetzungen` hat keinerlei Auswirkung auf die
    `oberkompetenzen`-Prüfung und umgekehrt, da beide Kantentypen
    unabhängig voneinander traversiert werden.

    Args:
        snapshot: Das vollständig aufgebaute Kompetenznetz-Snapshot.

    Returns:
        Eine `CycleDiagnostic` pro gefundenem Zyklus, über beide
        Kantentypen hinweg, in stabiler Reihenfolge (erst `hierarchy`,
        dann `prerequisite`).
    """
    edge_kind_to_edges: dict[EdgeKind, dict[str, tuple[str, ...]]] = {
        "hierarchy": {node.id: node.oberkompetenzen_ids for node in snapshot.nodes.values()},
        "prerequisite": {node.id: node.voraussetzungen_ids for node in snapshot.nodes.values()},
    }

    diagnostics: list[CycleDiagnostic] = []
    for edge_kind in ("hierarchy", "prerequisite"):
        for cycle_members in find_cycles(edge_kind_to_edges[edge_kind]):
            diagnostics.append(CycleDiagnostic(edge_kind=edge_kind, member_ids=cycle_members))
    return tuple(diagnostics)
