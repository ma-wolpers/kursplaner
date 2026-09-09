from __future__ import annotations

from dataclasses import dataclass

from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot


@dataclass(frozen=True)
class KompetenzGraphFilterOptions:
    """Alle aktuell im Snapshot tatsächlich vorkommenden Filter-Auswahlwerte, sortiert für stabile UI-Anzeige.

    Wird ausschließlich aus dem Snapshot abgeleitet -- niemals aus der
    (nachweislich veralteten) Kürzel-Prosa in `_Schema.md` und niemals
    auf ein einzelnes Fach hartkodiert. Damit passt sich die Filter-UI
    automatisch an jedes künftig nach demselben Schema strukturierte Fach
    an, ohne Codeänderung.

    Attributes:
        subjects: Alle im Snapshot vorkommenden Fach-Herkünfte
            (`KompetenzNode.source.subject`), z. B. `("Mathematik",)`.
        jahrgaenge: Alle vorkommenden `kc_zuordnung[].jahrgang`-Werte.
        schulformen: Alle vorkommenden `kc_zuordnung[].schulform`-Werte.
        bundeslaender: Alle vorkommenden `kc_zuordnung[].bundesland`-Werte.
        niveaus: Alle vorkommenden, nicht-leeren `kc_zuordnung[].niveau`-Werte.
        status_werte: Alle vorkommenden `KompetenzNode.status`-Werte.
        anforderungen: Alle vorkommenden `kc_zuordnung[].anforderung`-Werte.
        inhaltsbereich_ids: IDs aller Bereichs-Hubs mit `kind="inhaltsbereich"`.
        prozessbereich_ids: IDs aller Bereichs-Hubs mit `kind="prozessbereich"`.
    """

    subjects: tuple[str, ...]
    jahrgaenge: tuple[int, ...]
    schulformen: tuple[str, ...]
    bundeslaender: tuple[str, ...]
    niveaus: tuple[str, ...]
    status_werte: tuple[str, ...]
    anforderungen: tuple[str, ...]
    inhaltsbereich_ids: tuple[str, ...]
    prozessbereich_ids: tuple[str, ...]


def compute_filter_options(snapshot: KompetenzGraphSnapshot) -> KompetenzGraphFilterOptions:
    """Leitet alle Filter-Auswahllisten dynamisch aus dem aktuellen Snapshot ab."""
    subjects: set[str] = set()
    jahrgaenge: set[int] = set()
    schulformen: set[str] = set()
    bundeslaender: set[str] = set()
    niveaus: set[str] = set()
    status_werte: set[str] = set()
    anforderungen: set[str] = set()

    for node in snapshot.nodes.values():
        subjects.add(node.source.subject)
        status_werte.add(node.status)
        for entry in node.kc_zuordnung:
            if entry.jahrgang is not None:
                jahrgaenge.add(entry.jahrgang)
            if entry.schulform:
                schulformen.add(entry.schulform)
            if entry.bundesland:
                bundeslaender.add(entry.bundesland)
            if entry.niveau:
                niveaus.add(entry.niveau)
            anforderungen.add(entry.anforderung)

    inhaltsbereich_ids = {b.id for b in snapshot.bereiche.values() if b.kind == "inhaltsbereich"}
    prozessbereich_ids = {b.id for b in snapshot.bereiche.values() if b.kind == "prozessbereich"}

    return KompetenzGraphFilterOptions(
        subjects=tuple(sorted(subjects)),
        jahrgaenge=tuple(sorted(jahrgaenge)),
        schulformen=tuple(sorted(schulformen)),
        bundeslaender=tuple(sorted(bundeslaender)),
        niveaus=tuple(sorted(niveaus)),
        status_werte=tuple(sorted(status_werte)),
        anforderungen=tuple(sorted(anforderungen)),
        inhaltsbereich_ids=tuple(sorted(inhaltsbereich_ids)),
        prozessbereich_ids=tuple(sorted(prozessbereich_ids)),
    )
