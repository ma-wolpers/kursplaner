"""Gemeinsame Fixture-Fabriken für die Kompetenzgraph-Testsuite.

Kein `test_`-Präfix -- wird von pytest nicht als eigenständiges Testmodul
eingesammelt, nur von den `test_kompetenzgraph_*.py`-Dateien importiert.
Bündelt die sonst in fast jedem Testfall wiederholte, verbose Konstruktion
von `KompetenzNode`/`BereichNode`/`SourceRef`/`KcZuordnungEintrag` an einer
Stelle (ARCHITEKTUR_KERN §27: wiederverwendbare Logik nicht duplizieren).
"""

from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.kompetenzgraph_node import BereichNode, KompetenzNode
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from kursplaner.core.domain.kompetenzgraph_types import KcZuordnungEintrag, SourceRef

_SYNTHETIC_INFORMATIK_TOTAL_NODES = 144
_SYNTHETIC_INFORMATIK_NUM_LAYERS = 6
_SYNTHETIC_INFORMATIK_NODES_PER_LAYER = _SYNTHETIC_INFORMATIK_TOTAL_NODES // _SYNTHETIC_INFORMATIK_NUM_LAYERS
_SYNTHETIC_INFORMATIK_NUM_BEREICHE = 9


def make_source_ref(node_id: str, *, subject: str = "Mathematik", mtime_ns: int = 1, size: int = 1) -> SourceRef:
    """Baut eine `SourceRef` mit sinnvollen Testdefaults, Pfad aus `node_id` abgeleitet."""
    return SourceRef(path=Path(f"{subject}/{node_id}.md"), mtime_ns=mtime_ns, size=size, subject=subject)


def make_kc_zuordnung(
    *,
    bundesland: str | None = "Niedersachsen",
    schulform: str | None = "Gymnasium",
    niveau: str | None = None,
    jahrgang: int | None = 8,
    anforderung: str = "basis",
    kc_verweis: str = "Beispiel-Zitat.",
) -> KcZuordnungEintrag:
    """Baut einen `KcZuordnungEintrag` mit sinnvollen Testdefaults."""
    return KcZuordnungEintrag(
        bundesland=bundesland,
        schulform=schulform,
        niveau=niveau,
        jahrgang=jahrgang,
        anforderung=anforderung,
        kc_verweis=kc_verweis,
    )


def make_node(
    node_id: str,
    *,
    subject: str = "Mathematik",
    primarer_bereich_id: str = "I-Test",
    prozessbereich_ids: tuple[str, ...] = (),
    oberkompetenzen_ids: tuple[str, ...] = (),
    voraussetzungen_ids: tuple[str, ...] = (),
    offene_voraussetzungen: tuple[str, ...] = (),
    kc_zuordnung: tuple[KcZuordnungEintrag, ...] | None = None,
    status: str = "entwurf",
    title: str | None = None,
    source: SourceRef | None = None,
) -> KompetenzNode:
    """Baut einen `KompetenzNode` mit sinnvollen Testdefaults -- ein gültiger `kc_zuordnung`-Eintrag inklusive."""
    return KompetenzNode(
        id=node_id,
        source=source if source is not None else make_source_ref(node_id, subject=subject),
        primarer_bereich_id=primarer_bereich_id,
        prozessbereich_ids=prozessbereich_ids,
        oberkompetenzen_ids=oberkompetenzen_ids,
        voraussetzungen_ids=voraussetzungen_ids,
        offene_voraussetzungen=offene_voraussetzungen,
        kc_zuordnung=kc_zuordnung if kc_zuordnung is not None else (make_kc_zuordnung(),),
        status=status,
        title=title if title is not None else f"Titel von {node_id}",
    )


def make_bereich(
    node_id: str,
    *,
    subject: str = "Mathematik",
    kuerzel: str = "T",
    kind: str = "inhaltsbereich",
    title: str | None = None,
    body_markdown: str = "",
    source: SourceRef | None = None,
) -> BereichNode:
    """Baut einen `BereichNode` mit sinnvollen Testdefaults."""
    return BereichNode(
        id=node_id,
        source=source if source is not None else make_source_ref(node_id, subject=subject),
        kuerzel=kuerzel,
        kind=kind,  # type: ignore[arg-type]
        title=title if title is not None else f"Titel von {node_id}",
        body_markdown=body_markdown,
    )


def make_synthetic_informatik_like_snapshot() -> KompetenzGraphSnapshot:
    """Baut eine synthetische Struktur, die die echten Informatik-Vault-Kennzahlen nachbildet:
    144 Knoten / 9 Bereiche / 6 Schichten / ~67% der Knoten mit mehreren Prozessbereichen (real:
    96 von 144 = 67%) -- deterministisch generiert, keine Abhängigkeit von echten Dateien.

    Gemeinsam genutzt von `test_kompetenzgraph_layout_smoke.py` (Gesamt-Pipeline-Smoke-Test) und
    `test_kompetenzgraph_layout_forces.py` (Primärbereich-Kohäsion auf realistischer Skala,
    insbesondere der Filter-Waise-Fall E) -- deshalb hier statt lokal in einer der beiden Dateien.
    """
    bereich_ids = [f"BEREICH-{i}" for i in range(_SYNTHETIC_INFORMATIK_NUM_BEREICHE)]
    bereiche = [make_bereich(bereich_id) for bereich_id in bereich_ids]

    nodes = []
    previous_layer_ids: list[str] = []
    node_index = 0
    for _layer in range(_SYNTHETIC_INFORMATIK_NUM_LAYERS):
        current_layer_ids: list[str] = []
        for _position in range(_SYNTHETIC_INFORMATIK_NODES_PER_LAYER):
            node_id = f"NODE-{node_index}"
            primarer_bereich_id = bereich_ids[node_index % _SYNTHETIC_INFORMATIK_NUM_BEREICHE]
            oberkompetenzen_ids: tuple[str, ...] = ()
            if previous_layer_ids:
                parent_id = previous_layer_ids[node_index % len(previous_layer_ids)]
                oberkompetenzen_ids = (parent_id,)
            prozessbereich_ids: tuple[str, ...] = ()
            if node_index % 3 != 0:  # ~2/3 der Knoten bekommen mehrere Prozessbereiche
                other_bereiche = [bid for bid in bereich_ids if bid != primarer_bereich_id]
                prozessbereich_ids = tuple(other_bereiche[:2])
            nodes.append(
                make_node(
                    node_id,
                    primarer_bereich_id=primarer_bereich_id,
                    oberkompetenzen_ids=oberkompetenzen_ids,
                    prozessbereich_ids=prozessbereich_ids,
                )
            )
            current_layer_ids.append(node_id)
            node_index += 1
        previous_layer_ids = current_layer_ids

    return build_kompetenz_graph_snapshot(nodes, bereiche)
