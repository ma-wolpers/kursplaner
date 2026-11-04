"""Prüfung: Kompetenz-Titel sind pro Fach eindeutig (Schema-Invariante 17).

Vergleicht Titel nach Zusammenfassen von Leerraum und ohne Groß-/Kleinschreibung,
also so streng, wie eine Sequenzleiter Baustein-Texte vergleicht. Läuft bei
jedem Laden des Netzes (`LoadKompetenzGraphUseCase`).

Einzige Ausnahme (Invariante 17): Eine Hauptkompetenz und genau eine
gleichnamige Einzelkompetenz, die ihre **direkte** Teilkompetenz ist
(`oberkompetenzen`), dürfen denselben Titel tragen – die Einzelkompetenz ist
dann die Konkretisierung mit dem Wortlaut der Hauptkompetenz. Fehlt die Kante,
nennt die Diagnose sie als Lösung.
"""

from __future__ import annotations

from collections import defaultdict

from kursplaner.core.domain.kompetenzgraph_diagnostics import DuplicateTitleDiagnostic
from kursplaner.core.domain.kompetenzgraph_ebene import is_hauptkompetenz
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
    diagnostics: list[DuplicateTitleDiagnostic] = []
    for (subject, norm), ids in sorted(groups.items()):
        if len(ids) < 2:
            continue
        hint = _haupt_pair_hint(snapshot, ids)
        if hint == "":
            continue
        diagnostics.append(DuplicateTitleDiagnostic(subject, first_title[(subject, norm)], tuple(ids), hint or ""))
    return tuple(diagnostics)
