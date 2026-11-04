"""Haupt- und Einzelkompetenzen: einzige Auswertung von `kc_zuordnung[].ebene`.

Eine Hauptkompetenz ist eine übergreifende Kompetenz eines KCs, die über viele
Einzelkompetenzen hinweg erworben wird (Informatik: KC Kap. 3.1/3.2). Die Ebene
steht je `kc_zuordnung`-Eintrag, weil verschiedene KCs dieselbe Kompetenz
unterschiedlich einordnen können. Maßgeblich sind die Einträge, die zum
KC-Kontext eines Kurses passen (`relevant_entries`); passt keiner, zählen alle.
"""

from __future__ import annotations

from kursplaner.core.domain.course_kc_context import CourseKcContext, schulform_matches
from kursplaner.core.domain.kompetenzgraph_node import KompetenzNode
from kursplaner.core.domain.kompetenzgraph_types import EBENE_HAUPT, KcZuordnungEintrag


def relevant_entries(node: KompetenzNode, context: CourseKcContext) -> tuple[KcZuordnungEintrag, ...]:
    """`kc_zuordnung`-Einträge, die zu Bundesland/Schulform des Kontexts passen; sonst alle."""
    matching = tuple(
        entry
        for entry in node.kc_zuordnung
        if (context.bundesland is None or entry.bundesland == context.bundesland)
        and schulform_matches(entry.schulform, context.schulform)
    )
    return matching or node.kc_zuordnung


def is_hauptkompetenz(node: KompetenzNode, context: CourseKcContext = CourseKcContext()) -> bool:
    """Ob *node* im Kontext eine Hauptkompetenz ist: alle maßgeblichen Einträge tragen ``ebene: haupt``.

    Sobald ein maßgebliches KC die Kompetenz als Einzelkompetenz führt, ist sie
    keine Hauptkompetenz. Ohne Kontext zählen alle Einträge.
    """
    entries = relevant_entries(node, context)
    return bool(entries) and all(entry.ebene == EBENE_HAUPT for entry in entries)
