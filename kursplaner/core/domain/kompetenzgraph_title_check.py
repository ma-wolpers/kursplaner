"""Prüfung: Kompetenz-Titel und Lernziel-Formen sind pro Fach eindeutig (Schema-Invariante 17/18).

Vergleicht nach Zusammenfassen von Leerraum und ohne Groß-/Kleinschreibung,
also so streng, wie eine Sequenzleiter Baustein-Texte vergleicht. Läuft bei
jedem Laden des Netzes (`LoadKompetenzGraphUseCase`). Geprüft werden beide
Formulierungen, weil beide Baustein-Schlüssel sind: der Titel in der
Kompetenzspalte, die Lernziel-Form (`KompetenzNode.infinitive_title`) bei den
Lernzielen. Eine Gruppe, in der keiner der Knoten ein eigenes ``titel_infinitiv``
pflegt, meldet nur die Titelprüfung (die Lernziel-Form ist dort der Titel selbst).

Einzige Ausnahme (Invariante 17): Eine Hauptkompetenz und genau eine
gleichnamige Einzelkompetenz, die ihre **direkte** Teilkompetenz ist
(`oberkompetenzen`), dürfen denselben Titel tragen – die Einzelkompetenz ist
dann die Konkretisierung mit dem Wortlaut der Hauptkompetenz. Fehlt die Kante,
nennt die Diagnose sie als Lösung.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from kursplaner.core.domain.kompetenzgraph_diagnostics import (
    TITLE_FORM_INFINITIVE,
    TITLE_FORM_TITLE,
    DuplicateTitleDiagnostic,
)
from kursplaner.core.domain.kompetenzgraph_ebene import is_hauptkompetenz
from kursplaner.core.domain.kompetenzgraph_node import KompetenzNode
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot


def _normalized(title: str) -> str:
    return " ".join(str(title).split()).casefold()


def _haupt_pair_hint(snapshot: KompetenzGraphSnapshot, node_ids: list[str]) -> str | None:
    """``""`` = erlaubtes Paar, Text = Lösungsweg, ``None`` = kein Haupt/Einzel-Paar."""
    haupt = [node_id for node_id in node_ids if is_hauptkompetenz(snapshot.nodes[node_id])]
    einzel = [node_id for node_id in node_ids if node_id not in haupt]
    if len(haupt) != 1 or len(einzel) != 1:
        return None
    if haupt[0] in snapshot.nodes[einzel[0]].oberkompetenzen_ids:
        return ""
    return f"{einzel[0]} als direkte Teilkompetenz von {haupt[0]} eintragen"


def _duplicates(
    snapshot: KompetenzGraphSnapshot, text_of: Callable[[KompetenzNode], str], form: str
) -> list[DuplicateTitleDiagnostic]:
    """Diagnosen je (Fach, Text) mit mehr als einer Kompetenz, sortiert nach Fach und Text."""
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    first_text: dict[tuple[str, str], str] = {}
    for node_id in sorted(snapshot.nodes):
        node = snapshot.nodes[node_id]
        key = (node.source.subject, _normalized(text_of(node)))
        if not key[1]:
            continue
        groups[key].append(node_id)
        first_text.setdefault(key, text_of(node))
    diagnostics: list[DuplicateTitleDiagnostic] = []
    for (subject, norm), ids in sorted(groups.items()):
        if len(ids) < 2:
            continue
        if form == TITLE_FORM_INFINITIVE and not any(snapshot.nodes[i].title_infinitive for i in ids):
            continue  # Lernziel-Form = Titel bei allen – schon von der Titelprüfung gemeldet
        hint = _haupt_pair_hint(snapshot, ids)
        if hint == "":
            continue
        diagnostics.append(DuplicateTitleDiagnostic(subject, first_text[(subject, norm)], tuple(ids), hint or "", form))
    return diagnostics


def check_kompetenz_graph_for_duplicate_titles(
    snapshot: KompetenzGraphSnapshot,
) -> tuple[DuplicateTitleDiagnostic, ...]:
    """Diagnosen für doppelte Titel, danach für doppelte Lernziel-Formen (je sortiert nach Fach und Text)."""
    titles = _duplicates(snapshot, lambda node: node.title, TITLE_FORM_TITLE)
    infinitives = _duplicates(snapshot, lambda node: node.infinitive_title, TITLE_FORM_INFINITIVE)
    return tuple(titles + infinitives)
