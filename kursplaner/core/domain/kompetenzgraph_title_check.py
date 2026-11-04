"""Prüfung: Kompetenz-Titel sind pro Fach eindeutig (Schema-Invariante 16).

Vergleicht Titel nach Zusammenfassen von Leerraum und ohne Groß-/Kleinschreibung,
also so streng, wie eine Sequenzleiter Baustein-Texte als Primärschlüssel
vergleicht. Läuft bei jedem Laden des Netzes (`LoadKompetenzGraphUseCase`).
"""

from __future__ import annotations

from collections import defaultdict

from kursplaner.core.domain.kompetenzgraph_diagnostics import DuplicateTitleDiagnostic
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot


def _normalized(title: str) -> str:
    return " ".join(str(title).split()).casefold()


def check_kompetenz_graph_for_duplicate_titles(
    snapshot: KompetenzGraphSnapshot,
) -> tuple[DuplicateTitleDiagnostic, ...]:
    """Liefert je (Fach, Titel) mit mehr als einer Kompetenz eine Diagnose, sortiert nach Fach und Titel."""
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    first_title: dict[tuple[str, str], str] = {}
    for node_id in sorted(snapshot.nodes):
        node = snapshot.nodes[node_id]
        key = (node.source.subject, _normalized(node.title))
        if not key[1]:
            continue
        groups[key].append(node_id)
        first_title.setdefault(key, node.title)
    return tuple(
        DuplicateTitleDiagnostic(subject, first_title[(subject, norm)], tuple(ids))
        for (subject, norm), ids in sorted(groups.items())
        if len(ids) > 1
    )
