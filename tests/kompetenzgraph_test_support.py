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
from kursplaner.core.domain.kompetenzgraph_types import KcZuordnungEintrag, SourceRef


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
