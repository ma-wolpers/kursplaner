"""Kompetenznetz → Sequenzleiter: markierte Kompetenzen in Import-Bausteine übersetzen.

Die Spalte folgt aus der Art des `primarer_bereich`-Hubs (kanonische
Netzklassifikation, Schema-Invariante 9): Inhaltsbereich → links, Prozessbereich
→ rechts. Ausnahme: Gehören die Bereiche einer Kompetenz (primär und
`prozessbereiche`) zu **beiden** Arten (`has_both_sides`), darf die Nutzerin
beim Übernehmen eine Spalte für alle solchen Kompetenzen wählen (`mixed_side`;
ohne Wahl gilt der Primärbereich). Eine Kompetenz ohne auflösbaren Primärbereich
wird gemeldet, nie geraten. Inhaltsbezogene Hauptkompetenzen (`kompetenzgraph_ebene`) werden über
Einzelkompetenzen erworben und sind nicht übernehmbar; prozessbezogene
Hauptkompetenzen sind genau die „vorrangig geförderten Kompetenzen“ der rechten
Spalte und bleiben übernehmbar. `ladder_import_problem` ist die einzige Stelle
dieser Regel (Markieren im Netz und Import fragen beide hier). Der Baustein-Text
ist der Kompetenz-Titel in der Form, die er nach dem Rundweg durch die
Sequenzdatei trägt (`network_block_text`).
"""

from __future__ import annotations

from collections.abc import Iterable

from kursplaner.core.domain.course_kc_context import CourseKcContext
from kursplaner.core.domain.kompetenzgraph_ebene import is_hauptkompetenz
from kursplaner.core.domain.kompetenzgraph_node import BEREICH_KIND_INHALT, BEREICH_KIND_PROZESS, KompetenzNode
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.sequence_ladder import COMPETENCE_SIDES, LadderSide
from kursplaner.core.domain.sequence_ladder_entries import network_block_text
from kursplaner.core.domain.sequence_ladder_ops import ImportedCompetence

_SIDE_BY_KIND = {BEREICH_KIND_INHALT: LadderSide.INHALT, BEREICH_KIND_PROZESS: LadderSide.PROZESS}


def _bereich_side(snapshot: KompetenzGraphSnapshot, bereich_id: str | None) -> LadderSide | None:
    bereich = snapshot.bereiche.get(bereich_id or "")
    return _SIDE_BY_KIND.get(bereich.kind) if bereich is not None else None


def _side(snapshot: KompetenzGraphSnapshot, node: KompetenzNode) -> LadderSide | None:
    return _bereich_side(snapshot, node.primarer_bereich_id)


def has_both_sides(snapshot: KompetenzGraphSnapshot, node: KompetenzNode) -> bool:
    """Ob die Bereiche der Kompetenz (primär und sekundär) zu beiden Spalten passen – einzige Stelle der Regel.

    Beispiel: `primarer_bereich` ist ein Inhaltsbereich, unter `prozessbereiche`
    steht ein Prozessbereich. Nur für solche Kompetenzen ist die Spalte wählbar.
    """
    sides = {_bereich_side(snapshot, bereich_id) for bereich_id in node.referenced_bereich_ids}
    return set(COMPETENCE_SIDES) <= sides


def ladder_import_problem(
    snapshot: KompetenzGraphSnapshot, kompetenz_id: str, context: CourseKcContext = CourseKcContext()
) -> str | None:
    """Warum eine Kompetenz nicht in eine Leiter übernommen werden kann, sonst ``None``.

    Args:
        snapshot: Geladenes Kompetenznetz.
        kompetenz_id: Zu prüfende Kompetenz.
        context: KC-Kontext des Kurses der Ziel-Sequenz (bestimmt Haupt/Einzel).
    """
    node = snapshot.nodes.get(kompetenz_id)
    if node is None:
        return f"{kompetenz_id}: nicht im Kompetenznetz gefunden."
    side = _side(snapshot, node)
    if side is None:
        return f"{kompetenz_id}: kein auflösbarer Primärbereich – Spalte unklar."
    if side is LadderSide.INHALT and is_hauptkompetenz(node, context):
        return f"{kompetenz_id}: Hauptkompetenz – wird über ihre Einzelkompetenzen erworben, nicht übernommen."
    return None


def mixed_side_ids(
    snapshot: KompetenzGraphSnapshot, kompetenz_ids: Iterable[str], context: CourseKcContext = CourseKcContext()
) -> tuple[str, ...]:
    """Übernehmbare IDs mit Inhalts- und Prozessbereich (`has_both_sides`) – nur dann wird nach der Spalte gefragt.

    Args:
        snapshot: Geladenes Kompetenznetz.
        kompetenz_ids: Markierte IDs (Duplikate werden ignoriert).
        context: KC-Kontext des Kurses der Ziel-Sequenz.
    """
    return tuple(
        kompetenz_id
        for kompetenz_id in dict.fromkeys(kompetenz_ids)
        if ladder_import_problem(snapshot, kompetenz_id, context) is None
        and has_both_sides(snapshot, snapshot.nodes[kompetenz_id])
    )


def competence_import_items(
    snapshot: KompetenzGraphSnapshot,
    kompetenz_ids: Iterable[str],
    context: CourseKcContext = CourseKcContext(),
    mixed_side: LadderSide | None = None,
) -> tuple[tuple[ImportedCompetence, ...], tuple[str, ...]]:
    """Übersetzt Kompetenz-IDs in Import-Bausteine.

    Args:
        snapshot: Geladenes Kompetenznetz.
        kompetenz_ids: Markierte IDs in Übernahme-Reihenfolge (Duplikate werden ignoriert).
        context: KC-Kontext des Kurses der Ziel-Sequenz.
        mixed_side: Gewählte Spalte für Kompetenzen mit Inhalts- und
            Prozessbereich (`has_both_sides`); ``None`` = Spalte des Primärbereichs.

    Returns:
        ``(items, problems)`` – ``problems`` sind nutzerlesbare Meldungen zu IDs,
        die nicht übernommen werden können (`ladder_import_problem`).
    """
    items: list[ImportedCompetence] = []
    problems: list[str] = []
    for kompetenz_id in dict.fromkeys(kompetenz_ids):
        problem = ladder_import_problem(snapshot, kompetenz_id, context)
        if problem is not None:
            problems.append(problem)
            continue
        node = snapshot.nodes[kompetenz_id]
        side = mixed_side if mixed_side is not None and has_both_sides(snapshot, node) else _side(snapshot, node)
        assert side is not None
        items.append(ImportedCompetence(kompetenz_id, network_block_text(kompetenz_id, node.title), side))
    return tuple(items), tuple(problems)
