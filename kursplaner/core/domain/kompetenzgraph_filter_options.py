from __future__ import annotations

from dataclasses import dataclass

from kursplaner.core.domain.course_subject import subject_short_or_name, subject_sort_key
from kursplaner.core.domain.kompetenzgraph_node import BereichNode
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot


@dataclass(frozen=True)
class BereichFilterOption:
    """Ein auswählbarer Bereichs-Hub im Inhalts-/Prozessbereich-Filter.

    Trennt bewusst Identität (`id`) von Darstellung (`label`): Die GUI
    zeigt nur `label` an und löst die Auswahl über die Position in der
    Optionsliste zurück auf `id` auf -- NIE über den Label-Text. Doppelte
    oder nachträglich geänderte Bereichstitel (Daten-Drift in den
    `Bereiche/*.md`-Dateien) können so keine falsche Filter-ID erzeugen.

    Attributes:
        id: Vault-weit eindeutige Bereichs-ID, z. B. ``"P-Kommunizieren"``.
        subject: Fach-Herkunft des Bereichs (`BereichNode.source.subject`).
        label: Anzeigetext mit Fachkürzel-Präfix, z. B.
            ``"Mat · Kommunizieren (KO)"``.
    """

    id: str
    subject: str
    label: str


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
            (`KompetenzNode.source.subject`), alphabetisch (umlaut-robust,
            siehe `subject_sort_key`), z. B. `("Informatik", "Mathematik")`.
        jahrgaenge: Alle vorkommenden `kc_zuordnung[].jahrgang`-Werte.
        schulformen: Alle vorkommenden `kc_zuordnung[].schulform`-Werte.
        bundeslaender: Alle vorkommenden `kc_zuordnung[].bundesland`-Werte.
        niveaus: Alle vorkommenden, nicht-leeren `kc_zuordnung[].niveau`-Werte.
        status_werte: Alle vorkommenden `KompetenzNode.status`-Werte.
        anforderungen: Alle vorkommenden `kc_zuordnung[].anforderung`-Werte.
        inhaltsbereiche: Alle Bereichs-Hubs mit `kind="inhaltsbereich"`,
            nach Fach gruppiert (siehe `_bereich_options`).
        prozessbereiche: Alle Bereichs-Hubs mit `kind="prozessbereich"`,
            nach Fach gruppiert.
    """

    subjects: tuple[str, ...]
    jahrgaenge: tuple[int, ...]
    schulformen: tuple[str, ...]
    bundeslaender: tuple[str, ...]
    niveaus: tuple[str, ...]
    status_werte: tuple[str, ...]
    anforderungen: tuple[str, ...]
    inhaltsbereiche: tuple[BereichFilterOption, ...]
    prozessbereiche: tuple[BereichFilterOption, ...]


def _bereich_options(snapshot: KompetenzGraphSnapshot, kind: str) -> tuple[BereichFilterOption, ...]:
    """Baut die sortierten Filteroptionen aller Bereichs-Hubs einer Art.

    Sortierung: erst nach Fach (voller Fachname, umlaut-robust -- also
    "Darstellendes Spiel" vor "Deutsch" vor "Englisch"), dann nach
    Bereichstitel, zuletzt nach ID als eindeutigem Tie-Breaker, damit die
    Reihenfolge auch bei gleichen Titeln deterministisch bleibt.

    Args:
        snapshot: Aktueller Kompetenznetz-Snapshot.
        kind: ``"inhaltsbereich"`` oder ``"prozessbereich"``.

    Returns:
        Sortierte `BereichFilterOption`s.
    """
    bereiche: list[BereichNode] = [b for b in snapshot.bereiche.values() if b.kind == kind]
    bereiche.sort(key=lambda b: (subject_sort_key(b.source.subject), subject_sort_key(b.title), b.id))
    return tuple(
        BereichFilterOption(
            id=b.id,
            subject=b.source.subject,
            label=f"{subject_short_or_name(b.source.subject)} · {b.title}",
        )
        for b in bereiche
    )


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

    return KompetenzGraphFilterOptions(
        subjects=tuple(sorted(subjects, key=lambda s: (subject_sort_key(s), s))),
        jahrgaenge=tuple(sorted(jahrgaenge)),
        schulformen=tuple(sorted(schulformen)),
        bundeslaender=tuple(sorted(bundeslaender)),
        niveaus=tuple(sorted(niveaus)),
        status_werte=tuple(sorted(status_werte)),
        anforderungen=tuple(sorted(anforderungen)),
        inhaltsbereiche=_bereich_options(snapshot, "inhaltsbereich"),
        prozessbereiche=_bereich_options(snapshot, "prozessbereich"),
    )
