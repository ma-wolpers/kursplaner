from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from kursplaner.core.domain.kompetenzgraph_diagnostics import DuplicateIdDiagnostic, UnresolvedLink
from kursplaner.core.domain.kompetenzgraph_node import BereichNode, KompetenzNode


@dataclass(frozen=True)
class KompetenzGraphSnapshot:
    """Unveränderliches Read-Model des gesamten (fachübergreifenden) Kompetenznetzes.

    Einzige Konstruktionsstelle ist `kompetenzgraph_snapshot_builder.py::build_kompetenz_graph_snapshot` --
    kein Aufrufer darf `nodes`/`bereiche`/die abgeleiteten Rückkanten-
    Mappings nachträglich ergänzen oder entfernen. Dafür genügt eine
    leichte Stdlib-Lösung (`types.MappingProxyType` für die Mappings,
    Tupel für die Listen) statt eines zusätzlichen Immutability-
    Frameworks.

    Enthält bewusst KEIN `subject`-Feld: der Snapshot ist von Natur aus
    fachübergreifend (siehe Kritische Modellentscheidung im
    Implementierungsplan) -- welchem Fach ein Knoten physisch entstammt,
    steht an `KompetenzNode.source.subject`/`BereichNode.source.subject`.

    Attributes:
        nodes: Alle Kompetenz-Knoten, geschlüsselt nach ID.
        bereiche: Alle Bereichs-Hub-Knoten, geschlüsselt nach ID.
        teilkompetenzen_by_id: Abgeleitete Rückkante zu `oberkompetenzen`
            (`"hierarchy"`) -- für Eltern-ID X die IDs aller Kinder, die
            X in ihrem `oberkompetenzen_ids` führen. Wird laut Schema
            NIE persistiert, sondern immer frisch aus `nodes` abgeleitet.
        weiterfuehrung_by_id: Abgeleitete Rückkante zu `voraussetzungen`
            (`"prerequisite"`) -- für Vorbedingungs-ID X die IDs aller
            Kompetenzen, die X in ihrem `voraussetzungen_ids` führen.
        unresolved_links: Wikilinks, deren Ziel-ID im aktuellen
            `nodes`/`bereiche`-Bestand fehlt -- keine Fehler, nur
            Diagnosen (siehe `UnresolvedLink`).
        duplicate_ids: Diagnosen zu IDs, die von mehr als einer Quelldatei
            beansprucht wurden.
    """

    nodes: MappingProxyType[str, KompetenzNode]
    bereiche: MappingProxyType[str, BereichNode]
    teilkompetenzen_by_id: MappingProxyType[str, tuple[str, ...]]
    weiterfuehrung_by_id: MappingProxyType[str, tuple[str, ...]]
    unresolved_links: tuple[UnresolvedLink, ...]
    duplicate_ids: tuple[DuplicateIdDiagnostic, ...]
