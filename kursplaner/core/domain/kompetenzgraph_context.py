from __future__ import annotations

from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.kompetenzgraph_view_mode import bidirectional_closure


def compute_context_node_ids(
    snapshot: KompetenzGraphSnapshot,
    mode_key: str,
    primary_ids: frozenset[str],
    depth: int,
) -> frozenset[str]:
    """Berechnet die Kontextnachbarn ("Matchingtiefe") um eine Menge von Filtertreffern.

    Bei `depth == 0` (Default) ist das Ergebnis immer leer -- die bisherige
    Filterintuition ("nur was der Filter direkt trifft") bleibt dadurch
    vollständig erhalten. Bei `depth > 0` werden alle Knoten hinzugefügt,
    die von IRGENDEINEM Primärtreffer aus innerhalb von `depth` Hops
    entlang der aktiven View-Semantik erreichbar sind (Ancestor- UND
    Descendant-Richtung gleichzeitig, siehe `bidirectional_closure()`),
    OHNE selbst zu Primärtreffern zu werden.

    Fachübergreifend "by construction": diese Funktion prüft niemals
    `subject` oder irgendein anderes Filterkriterium der erreichten
    Nachbarn -- ein Nachbar aus einem anderen Fach wird ganz normal als
    Kontextknoten erreicht (siehe Kritische Modellentscheidung im
    Implementierungsplan: Wikilinks sind fachunabhängig auflösbar). Alle
    fachlichen Filterkriterien gelten ausschließlich für die Ermittlung
    von `primary_ids` durch den Aufrufer (`kompetenzgraph_filter.py`),
    nicht für diese Traversierung.

    Da `bidirectional_closure()` ausschließlich `"hierarchy"`-/
    `"prerequisite"`-Kanten folgt (niemals `"classification"`), erweitern
    `primarer_bereich`/`prozessbereiche` die Kontextmenge nie. Ebenso
    nehmen Unresolved-Link-Ziele nie teil, da sie keine echten Knoten im
    Snapshot sind, zu denen `ancestors_of`/`descendants_of` navigieren
    könnten.

    Args:
        snapshot: Das vollständige Kompetenznetz-Snapshot.
        mode_key: Der aktuell aktive View-Mode.
        primary_ids: Die Menge der aktuellen Filtertreffer.
        depth: Matchingtiefe (0 = kein Kontext, siehe oben).

    Returns:
        Die Kontextmenge -- disjunkt von `primary_ids` (ein Knoten wird
        durch Kontext-Erweiterung nie zum Primärtreffer "hochgestuft").
    """
    if depth <= 0:
        return frozenset()
    closure = bidirectional_closure(snapshot, mode_key, primary_ids, max_depth=depth)
    return closure - primary_ids
