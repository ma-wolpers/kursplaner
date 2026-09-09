from __future__ import annotations

from dataclasses import dataclass, field

from kursplaner.core.domain.kompetenzgraph_context import compute_context_node_ids
from kursplaner.core.domain.kompetenzgraph_node import KompetenzNode
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.kompetenzgraph_types import KcZuordnungEintrag


@dataclass(frozen=True)
class KompetenzGraphFilter:
    """Vollständiger Filterzustand des Kompetenzgraph-Popups.

    Attributes:
        subjects: Echte Mehrfachauswahl der Fach-Herkunft (Domain-Invariante,
            keine reine UI-Kosmetik). `None` oder eine leere Menge bedeutet
            "alle Fächer"; mehrere gesetzte Fächer werden ODER-verknüpft
            (`node.source.subject in subjects`). Alle übrigen Filterfelder
            bleiben zusätzlich UND-verknüpft -- Beispiel:
            `{"Mathematik", "Informatik"}` + `jahrgang=8` zeigt Kompetenzen
            aus Mathematik ODER Informatik, die zusätzlich Jahrgang 8
            erfüllen. Die GUI reduziert eine Mehrfachauswahl nie intern auf
            ein einzelnes Fach.
        jahrgang, schulform, bundesland, niveau, anforderung: Beziehen
            sich auf `kc_zuordnung`-Einträge. Sofern gesetzt, müssen ALLE
            hier gesetzten Kriterien GEMEINSAM auf DEMSELBEN
            `kc_zuordnung`-Eintrag erfüllt sein (siehe
            `node_matches_filter()`) -- ein Knoten mit einem Eintrag
            Niedersachsen/Jahrgang 11 und einem zweiten Eintrag
            Bayern/Jahrgang 8 darf beim Filter "Niedersachsen + Jahrgang 8"
            NICHT treffen.
        status: Bezieht sich auf das Knoten-Ebene-Feld `status` (nicht pro
            `kc_zuordnung`-Eintrag), separat UND-verknüpft.
        inhaltsbereich_id, prozessbereich_id: Beziehen sich auf
            `primarer_bereich_id`/`prozessbereich_ids` (Knoten-Ebene),
            separat UND-verknüpft.
        kontexttiefe: "Matchingtiefe" -- 0 (Default) zeigt ausschließlich
            Primärtreffer (bisherige Filterintuition bleibt erhalten);
            n>0 blendet zusätzlich Kontextnachbarn bis n Hops entlang der
            aktiven View-Semantik ein (siehe `kompetenzgraph_context.py`),
            ohne dass diese zu Primärtreffern werden.
    """

    subjects: frozenset[str] | None = None
    jahrgang: int | None = None
    schulform: str | None = None
    bundesland: str | None = None
    niveau: str | None = None
    status: str | None = None
    anforderung: str | None = None
    inhaltsbereich_id: str | None = None
    prozessbereich_id: str | None = None
    kontexttiefe: int = 0


@dataclass(frozen=True)
class KompetenzGraphVisibleSet:
    """Primär-/Kontext-Trennung der aktuell sichtbaren Knoten (vor optionalem Fokus).

    Wird von `compute_visible_set()` erzeugt und von
    `kompetenzgraph_view.py::compute_kompetenz_graph_view` ggf. mit einem
    Fokus weiter eingeschränkt (siehe dort). Die Trennung bleibt auch nach
    einer Fokus-Einschränkung erhalten, damit der Renderer Primär- und
    Kontextknoten weiterhin unterschiedlich stylen kann.

    Attributes:
        primary_ids: Knoten, die die gesetzten Filterkriterien selbst
            erfüllen.
        context_ids: Knoten, die nur über die Matchingtiefe erreicht
            wurden -- disjunkt von `primary_ids`.
    """

    primary_ids: frozenset[str]
    context_ids: frozenset[str] = field(default_factory=frozenset)

    @property
    def all_ids(self) -> frozenset[str]:
        """Vereinigung aus Primär- und Kontextknoten -- die tatsächlich anzuzeigende Menge."""
        return self.primary_ids | self.context_ids


def _entry_matches_kc_zuordnung_criteria(entry: KcZuordnungEintrag, criteria: KompetenzGraphFilter) -> bool:
    """Prüft, ob EIN `kc_zuordnung`-Eintrag alle gesetzten Kriterien gemeinsam erfüllt.

    Zentrale Umsetzung der Filter-Semantik-Invariante: wird ausschließlich
    mit einem einzelnen Eintrag aufgerufen, niemals über mehrere Einträge
    hinweg gemischt (siehe `node_matches_filter()`).
    """
    if criteria.jahrgang is not None and entry.jahrgang != criteria.jahrgang:
        return False
    if criteria.schulform is not None and entry.schulform != criteria.schulform:
        return False
    if criteria.bundesland is not None and entry.bundesland != criteria.bundesland:
        return False
    if criteria.niveau is not None and entry.niveau != criteria.niveau:
        return False
    if criteria.anforderung is not None and entry.anforderung != criteria.anforderung:
        return False
    return True


def node_matches_filter(node: KompetenzNode, filter: KompetenzGraphFilter) -> bool:
    """Prüft, ob ein Kompetenz-Knoten alle gesetzten Filterkriterien erfüllt (= Primärtreffer).

    Siehe `KompetenzGraphFilter`-Docstring für die genaue UND-/ODER-
    Semantik zwischen den Feldern und die `kc_zuordnung`-Eintrags-
    Kopplung.
    """
    if filter.subjects and node.source.subject not in filter.subjects:
        return False
    if filter.status is not None and node.status != filter.status:
        return False
    if filter.inhaltsbereich_id is not None and node.primarer_bereich_id != filter.inhaltsbereich_id:
        return False
    if filter.prozessbereich_id is not None and filter.prozessbereich_id not in node.prozessbereich_ids:
        return False

    kc_zuordnung_criteria_set = any(
        value is not None
        for value in (filter.jahrgang, filter.schulform, filter.bundesland, filter.niveau, filter.anforderung)
    )
    if not kc_zuordnung_criteria_set:
        return True
    return any(_entry_matches_kc_zuordnung_criteria(entry, filter) for entry in node.kc_zuordnung)


def compute_visible_node_ids(snapshot: KompetenzGraphSnapshot, filter: KompetenzGraphFilter) -> frozenset[str]:
    """Berechnet die Primärtreffer-Menge (ohne Matchingtiefe/Fokus) für einen Filterzustand."""
    return frozenset(node.id for node in snapshot.nodes.values() if node_matches_filter(node, filter))


def compute_visible_set(
    snapshot: KompetenzGraphSnapshot, filter: KompetenzGraphFilter, mode_key: str
) -> KompetenzGraphVisibleSet:
    """Kombiniert Filter und Matchingtiefe zur vollständigen erlaubten Sichtbarkeitsmenge.

    Dies ist die Stufe "Filter → Primärtreffer → Matchingtiefe →
    Kontext" der zentralen Sichtbarkeits-Pipeline (siehe
    `kompetenzgraph_view.py`) -- noch OHNE einen etwaigen Fokus, der erst
    dort als letzter Schritt angewendet wird.
    """
    primary_ids = compute_visible_node_ids(snapshot, filter)
    context_ids = (
        compute_context_node_ids(snapshot, mode_key, primary_ids, filter.kontexttiefe)
        if filter.kontexttiefe > 0
        else frozenset()
    )
    return KompetenzGraphVisibleSet(primary_ids=primary_ids, context_ids=context_ids)


def compute_visible_bereich_ids(snapshot: KompetenzGraphSnapshot, node_ids: frozenset[str]) -> frozenset[str]:
    """Bestimmt die sichtbaren Bereichs-Hubs für eine gegebene sichtbare Knotenmenge.

    Ein Bereichs-Hub ist sichtbar, sobald ihn irgendein Knoten aus
    `node_ids` (Primär- ODER Kontextknoten) über `primarer_bereich`/
    `prozessbereiche` referenziert. Referenzen auf nicht existierende
    Bereichs-IDs werden hier stillschweigend ausgefiltert -- die sind
    stattdessen als `UnresolvedLink`-Diagnose sichtbar (siehe
    `kompetenzgraph_snapshot_builder.py`), nicht als regulärer Bereichs-
    Knoten.
    """
    referenced: set[str] = set()
    for node_id in node_ids:
        node = snapshot.nodes.get(node_id)
        if node is None:
            continue
        if node.primarer_bereich_id is not None:
            referenced.add(node.primarer_bereich_id)
        referenced.update(node.prozessbereich_ids)
    return frozenset(bereich_id for bereich_id in referenced if bereich_id in snapshot.bereiche)
