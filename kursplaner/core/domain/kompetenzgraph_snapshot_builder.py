from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Protocol, TypeVar

from kursplaner.core.domain.kompetenzgraph_diagnostics import DuplicateIdDiagnostic, UnresolvedLink
from kursplaner.core.domain.kompetenzgraph_node import BereichNode, KompetenzNode
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.kompetenzgraph_types import SourceRef


class _IdentifiedBySource(Protocol):
    """Struktureller Vertrag für Dedup: alles mit vault-weiter ID + Herkunft."""

    id: str
    source: SourceRef


_T = TypeVar("_T", bound=_IdentifiedBySource)


def _dedupe_by_id(items: Sequence[_T]) -> tuple[dict[str, _T], list[DuplicateIdDiagnostic]]:
    """Löst ID-Kollisionen zwischen mehreren Quelldateien deterministisch auf.

    Die Vault-Invariante "jede ID ist eindeutig" (siehe `_Schema.md`) wird
    hier nicht blind vorausgesetzt: kommt eine ID mehrfach vor (z. B. weil
    zwei Fachordner versehentlich dieselbe ID vergeben), gewinnt
    deterministisch der nach `(source.subject, source.path)` sortiert
    erste Kandidat; alle weiteren werden als `DuplicateIdDiagnostic`
    gemeldet statt still überschrieben.

    Returns:
        `(by_id, diagnostics)` -- `by_id` enthält genau einen Eintrag pro
        ID (den Gewinner), `diagnostics` eine Meldung pro Kollision.
    """
    grouped: dict[str, list[_T]] = {}
    for item in items:
        grouped.setdefault(item.id, []).append(item)

    by_id: dict[str, _T] = {}
    diagnostics: list[DuplicateIdDiagnostic] = []
    for item_id, candidates in grouped.items():
        if len(candidates) == 1:
            by_id[item_id] = candidates[0]
            continue
        ordered = sorted(candidates, key=lambda candidate: (candidate.source.subject, str(candidate.source.path)))
        winner, *losers = ordered
        by_id[item_id] = winner
        diagnostics.append(
            DuplicateIdDiagnostic(
                id=item_id,
                winning_source=winner.source.path,
                discarded_sources=tuple(loser.source.path for loser in losers),
            )
        )
    return by_id, diagnostics


def _build_backlinks(
    node_ids: Sequence[str], forward_edges: Mapping[str, tuple[str, ...]]
) -> MappingProxyType[str, tuple[str, ...]]:
    """Invertiert ein Vorwärtskanten-Mapping zur abgeleiteten Rückkante.

    Laut Schema werden Rückkanten (`teilkompetenzen`/`weiterfuehrung`)
    NIE persistiert -- sie werden hier bei jedem Snapshot-Aufbau frisch
    aus den gespeicherten Vorwärtskanten (`oberkompetenzen`/
    `voraussetzungen`) abgeleitet. Jede ID aus `node_ids` erhält einen
    Eintrag (ggf. leeres Tupel), damit Aufrufer ohne `.get(id, ())`-
    Absicherung direkt indizieren können.
    """
    backlinks: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for child_id, parent_ids in forward_edges.items():
        for parent_id in parent_ids:
            if parent_id in backlinks:
                backlinks[parent_id].append(child_id)
    return MappingProxyType({parent_id: tuple(sorted(children)) for parent_id, children in backlinks.items()})


def _find_unresolved_links(
    nodes_by_id: Mapping[str, KompetenzNode], bereiche_by_id: Mapping[str, BereichNode]
) -> tuple[UnresolvedLink, ...]:
    """Erkennt Wikilinks, deren Ziel-ID im aktuellen Knoten-/Bereichs-Bestand fehlt.

    Laut Schema ausdrücklich zulässig (z. B. unvollständiger Import-Batch)
    -- diese Funktion erzeugt daher nur Diagnosen, keine Fehler, und wird
    von keiner anderen Stelle (Layout/Fokus/Kontext/Filter) als
    Voraussetzung für deren eigene Korrektheit benötigt.
    """
    unresolved: list[UnresolvedLink] = []
    for node in nodes_by_id.values():
        for target in node.oberkompetenzen_ids:
            if target not in nodes_by_id:
                unresolved.append(UnresolvedLink(node.id, "oberkompetenzen", target))
        for target in node.voraussetzungen_ids:
            if target not in nodes_by_id:
                unresolved.append(UnresolvedLink(node.id, "voraussetzungen", target))
        if node.primarer_bereich_id is not None and node.primarer_bereich_id not in bereiche_by_id:
            unresolved.append(UnresolvedLink(node.id, "primarer_bereich", node.primarer_bereich_id))
        for target in node.prozessbereich_ids:
            if target not in bereiche_by_id:
                unresolved.append(UnresolvedLink(node.id, "prozessbereiche", target))
    unresolved.sort(key=lambda link: (link.source_id, link.field, link.target_id))
    return tuple(unresolved)


def build_kompetenz_graph_snapshot(
    nodes: Sequence[KompetenzNode], bereiche: Sequence[BereichNode]
) -> KompetenzGraphSnapshot:
    """Baut aus bereits erfolgreich gemappten Knoten das unveränderliche Kompetenznetz-Snapshot.

    Einzige Konstruktionsstelle von `KompetenzGraphSnapshot` (siehe dessen
    Docstring). Nimmt bewusst Sequenzen statt vorab geschlüsselter
    Mappings entgegen, um ID-Kollisionen selbst zu erkennen (siehe
    `_dedupe_by_id`) -- der Aufrufer (i. d. R. das Repository nach dem
    Mapping aller Rohdateien mehrerer Fachordner) muss dafür nicht selbst
    schon eindeutig geschlüsselt haben.

    Args:
        nodes: Alle erfolgreich gemappten Kompetenz-Knoten (über beliebig
            viele Fächer hinweg -- der Snapshot ist von Natur aus
            fachübergreifend).
        bereiche: Alle erfolgreich gemappten Bereichs-Hub-Knoten.

    Returns:
        Das vollständige, unveränderliche Snapshot -- inklusive
        abgeleiteter Rückkanten, Unresolved-Link- und Duplicate-ID-
        Diagnosen. Wird immer vollständig geliefert, auch wenn das
        Kantenbild Zyklen enthält (die Zyklen-Diagnose ist ein separater
        Schritt, siehe `kompetenzgraph_dag.py`).
    """
    nodes_by_id, node_duplicates = _dedupe_by_id(nodes)
    bereiche_by_id, bereich_duplicates = _dedupe_by_id(bereiche)

    node_ids = tuple(nodes_by_id.keys())
    oberkompetenzen_edges = {node.id: node.oberkompetenzen_ids for node in nodes_by_id.values()}
    voraussetzungen_edges = {node.id: node.voraussetzungen_ids for node in nodes_by_id.values()}

    return KompetenzGraphSnapshot(
        nodes=MappingProxyType(dict(nodes_by_id)),
        bereiche=MappingProxyType(dict(bereiche_by_id)),
        teilkompetenzen_by_id=_build_backlinks(node_ids, oberkompetenzen_edges),
        weiterfuehrung_by_id=_build_backlinks(node_ids, voraussetzungen_edges),
        unresolved_links=_find_unresolved_links(nodes_by_id, bereiche_by_id),
        duplicate_ids=tuple(node_duplicates) + tuple(bereich_duplicates),
    )
