from __future__ import annotations

from collections.abc import Callable

from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot

MODE_OBER_TEIL = "ober_teil"
"""Ansicht Ober-/Teilkompetenzen: `oberkompetenzen` (gespeichert) zeigt nach oben/allgemeiner,
die abgeleitete Rückkante `teilkompetenzen` nach unten/atomarer."""

MODE_FORT_VORAUS = "fort_voraus"
"""Ansicht Fort-/Voraussetzung: `voraussetzungen` (gespeichert) zeigt nach unten/niedrigschwelliger,
die abgeleitete Rückkante `weiterfuehrung` nach oben/fortgeschrittener -- GENAU UMGEKEHRTE
Vorwärts-/Rückwärts-Zuordnung gegenüber `MODE_OBER_TEIL`, siehe `ancestors_of()`/`descendants_of()`."""

VIEW_MODES: tuple[str, ...] = (MODE_OBER_TEIL, MODE_FORT_VORAUS)


def _require_valid_mode(mode_key: str) -> None:
    if mode_key not in VIEW_MODES:
        raise ValueError(f"Unbekannter Kompetenzgraph-View-Mode: {mode_key!r} (erwartet: {VIEW_MODES!r}).")


def ancestors_of(snapshot: KompetenzGraphSnapshot, mode_key: str, node_id: str) -> tuple[str, ...]:
    """Liefert die direkten hierarchisch-höheren Nachbarn eines Knotens für den gegebenen View-Mode.

    "Höher" bedeutet je nach Modus etwas fachlich anderes: in
    `MODE_OBER_TEIL` die allgemeineren Oberkompetenzen (`oberkompetenzen`,
    gespeicherte Vorwärtskante), in `MODE_FORT_VORAUS` die fortgeschritteneren
    Weiterführungen (`weiterfuehrung`, abgeleitete Rückkante zu
    `voraussetzungen`) -- **niemals** `"classification"`-Kanten
    (`primarer_bereich`/`prozessbereiche`), unabhängig vom Modus. Diese
    Funktion ist die einzige Stelle, an der diese Richtungssemantik
    entschieden wird -- Fokus-, Kontext-, Layout- und Pfeiltasten-Code
    rufen ausschließlich sie (bzw. `descendants_of()`) auf, statt die
    Feldwahl selbst zu treffen.

    Returns:
        Leeres Tupel, wenn `node_id` nicht im Snapshot existiert (z. B.
        ein Unresolved-Link-Ziel) -- kein Fehler.
    """
    _require_valid_mode(mode_key)
    if mode_key == MODE_OBER_TEIL:
        node = snapshot.nodes.get(node_id)
        return node.oberkompetenzen_ids if node is not None else ()
    return snapshot.weiterfuehrung_by_id.get(node_id, ())


def descendants_of(snapshot: KompetenzGraphSnapshot, mode_key: str, node_id: str) -> tuple[str, ...]:
    """Liefert die direkten hierarchisch-niedrigeren Nachbarn eines Knotens für den gegebenen View-Mode.

    Spiegelbildlich zu `ancestors_of()`: in `MODE_OBER_TEIL` die
    atomareren Teilkompetenzen (`teilkompetenzen`, abgeleitete Rückkante
    zu `oberkompetenzen`), in `MODE_FORT_VORAUS` die niedrigschwelligeren
    Voraussetzungen (`voraussetzungen`, gespeicherte Vorwärtskante).
    Niemals `"classification"`-Kanten.
    """
    _require_valid_mode(mode_key)
    if mode_key == MODE_OBER_TEIL:
        return snapshot.teilkompetenzen_by_id.get(node_id, ())
    node = snapshot.nodes.get(node_id)
    return node.voraussetzungen_ids if node is not None else ()


def _closure(
    snapshot: KompetenzGraphSnapshot,
    mode_key: str,
    seed_ids: frozenset[str],
    neighbor_fns: tuple[Callable[[KompetenzGraphSnapshot, str, str], tuple[str, ...]], ...],
    *,
    max_depth: int | None,
) -> frozenset[str]:
    """Gemeinsame BFS-Maschine für alle Closure-Varianten dieses Moduls (privat).

    Iterative Breitensuche mit Visited-Set (zyklensicher durch
    Konstruktion -- ein Zyklus im zugrunde liegenden Kantenbild führt nie
    zu einer Endlosschleife, sondern lediglich dazu, dass die beteiligten
    Knoten korrekt alle Teil des Ergebnisses werden). `neighbor_fns`
    bestimmt, welche Nachbarschaftsfunktion(en) pro Schritt befragt
    werden -- genau eine für `ancestor_closure()`/`descendant_closure()`,
    beide für `bidirectional_closure()`.
    """
    visited: set[str] = set(seed_ids)
    frontier: set[str] = set(seed_ids)
    depth = 0
    while frontier and (max_depth is None or depth < max_depth):
        next_frontier: set[str] = set()
        for node_id in frontier:
            for neighbor_fn in neighbor_fns:
                for neighbor in neighbor_fn(snapshot, mode_key, node_id):
                    if neighbor not in visited:
                        next_frontier.add(neighbor)
        visited |= next_frontier
        frontier = next_frontier
        depth += 1
    return frozenset(visited)


def ancestor_closure(
    snapshot: KompetenzGraphSnapshot, mode_key: str, seed_ids: frozenset[str], *, max_depth: int | None = None
) -> frozenset[str]:
    """Transitive Hülle AUSSCHLIESSLICH entlang `ancestors_of()`, ausgehend von `seed_ids`.

    Wird von `kompetenzgraph_focus.py` genutzt: die Traversierung bewegt
    sich immer nur weiter nach "oben", niemals seitwärts über einen
    gemeinsamen Vorfahren zu dessen anderen Nachfahren (Geschwistern) --
    im Gegensatz zu `bidirectional_closure()`, die genau das für
    Kontext-Matching bewusst zulässt.
    """
    _require_valid_mode(mode_key)
    return _closure(snapshot, mode_key, seed_ids, (ancestors_of,), max_depth=max_depth)


def descendant_closure(
    snapshot: KompetenzGraphSnapshot, mode_key: str, seed_ids: frozenset[str], *, max_depth: int | None = None
) -> frozenset[str]:
    """Transitive Hülle AUSSCHLIESSLICH entlang `descendants_of()`, ausgehend von `seed_ids`.

    Spiegelbildlich zu `ancestor_closure()` -- siehe dortigen Docstring.
    """
    _require_valid_mode(mode_key)
    return _closure(snapshot, mode_key, seed_ids, (descendants_of,), max_depth=max_depth)


def bidirectional_closure(
    snapshot: KompetenzGraphSnapshot,
    mode_key: str,
    seed_ids: frozenset[str],
    *,
    max_depth: int | None = None,
) -> frozenset[str]:
    """BFS über Ancestor- UND Descendant-Kanten gleichzeitig, gemischt bei jedem Schritt.

    Genutzt von `kompetenzgraph_context.py` (Matchingtiefe): ein
    Kontextnachbar darf innerhalb der erlaubten Hop-Zahl über eine
    BELIEBIGE Mischung aus Auf- und Abwärtsschritten erreicht werden
    (z. B. ein Hop hoch zum gemeinsamen Vorfahren, dann ein Hop runter zu
    dessen anderem Kind = ein "Geschwister" innerhalb von 2 Hops) --
    fachlich gewollt für Kontext-Matching, im Unterschied zum Fokus-Modus
    (siehe `ancestor_closure()`/`descendant_closure()`, die NICHT
    mischen). Das Ergebnis schließt die Startmenge selbst mit ein
    ("Closure" im mathematischen Sinn) -- `kompetenzgraph_context.py`
    zieht `seed_ids` (die Primärtreffer) am Ende wieder ab, um die reine
    Kontextmenge zu erhalten.

    Args:
        snapshot: Das vollständige Kompetenznetz-Snapshot.
        mode_key: `MODE_OBER_TEIL` oder `MODE_FORT_VORAUS`.
        seed_ids: Startknoten der BFS.
        max_depth: Maximale Anzahl an Hops von der Startmenge aus, oder
            `None` für unbeschränkte Tiefe (volle transitive Hülle).

    Returns:
        Alle innerhalb `max_depth` Hops erreichbaren Knoten-IDs,
        einschließlich `seed_ids`.
    """
    _require_valid_mode(mode_key)
    return _closure(snapshot, mode_key, seed_ids, (ancestors_of, descendants_of), max_depth=max_depth)
