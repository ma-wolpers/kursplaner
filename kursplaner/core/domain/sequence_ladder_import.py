"""Kompetenznetz → Sequenzleiter: markierte Kompetenzen in Import-Bausteine übersetzen.

Die Spalte folgt allein aus der Art des `primarer_bereich`-Hubs (kanonische
Netzklassifikation, Schema-Invariante 9): Inhaltsbereich → links, Prozessbereich
→ rechts. Eine Kompetenz ohne auflösbaren Primärbereich wird gemeldet, nie
geraten. Der Baustein-Text ist der Kompetenz-Titel in der Form, die er nach dem
Rundweg durch die Sequenzdatei trägt (`network_block_text`).
"""

from __future__ import annotations

from collections.abc import Iterable

from kursplaner.core.domain.kompetenzgraph_node import BEREICH_KIND_INHALT, BEREICH_KIND_PROZESS
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.sequence_ladder import LadderSide
from kursplaner.core.domain.sequence_ladder_codec import network_block_text
from kursplaner.core.domain.sequence_ladder_ops import ImportedCompetence

_SIDE_BY_KIND = {BEREICH_KIND_INHALT: LadderSide.INHALT, BEREICH_KIND_PROZESS: LadderSide.PROZESS}


def competence_import_items(
    snapshot: KompetenzGraphSnapshot, kompetenz_ids: Iterable[str]
) -> tuple[tuple[ImportedCompetence, ...], tuple[str, ...]]:
    """Übersetzt Kompetenz-IDs in Import-Bausteine.

    Args:
        snapshot: Geladenes Kompetenznetz.
        kompetenz_ids: Markierte IDs in Übernahme-Reihenfolge (Duplikate werden ignoriert).

    Returns:
        ``(items, problems)`` – ``problems`` sind nutzerlesbare Meldungen zu IDs,
        die nicht übernommen werden können (unbekannt, ohne Primärbereich).
    """
    items: list[ImportedCompetence] = []
    problems: list[str] = []
    for kompetenz_id in dict.fromkeys(kompetenz_ids):
        node = snapshot.nodes.get(kompetenz_id)
        if node is None:
            problems.append(f"{kompetenz_id}: nicht im Kompetenznetz gefunden.")
            continue
        bereich = snapshot.bereiche.get(node.primarer_bereich_id or "")
        side = _SIDE_BY_KIND.get(bereich.kind) if bereich is not None else None
        if side is None:
            problems.append(f"{kompetenz_id}: kein auflösbarer Primärbereich – Spalte unklar.")
            continue
        items.append(ImportedCompetence(kompetenz_id, network_block_text(kompetenz_id, node.title), side))
    return tuple(items), tuple(problems)
