from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from kursplaner.core.domain.kompetenzgraph_types import KcZuordnungEintrag, SourceRef


@dataclass(frozen=True)
class KompetenzNode:
    """Eine einzelne Kompetenz aus dem Kompetenznetz (z. B. Datei `GF-49.md`).

    Reines Domain-Objekt ohne I/O -- wird ausschließlich von
    `kompetenzgraph_mapping.py::parse_kompetenz_node_from_raw` aus bereits
    eingelesenem YAML-Frontmatter + Body-Text erzeugt. Enthält bewusst
    KEIN `body_markdown`-Feld: der vollständige Markdown-Body wird lazy
    über `LoadKompetenzNodeBodyUseCase` nachgeladen, sobald ein Knoten im
    Detailbereich der GUI geöffnet wird, statt für alle ~500 Knoten eager
    im Speicher/Cache gehalten zu werden (siehe Meilenstein 2 des
    Implementierungsplans, Abschnitt "Lazy Body").

    Attributes:
        id: Vault-weit eindeutige Kompetenz-ID (Dateiname ohne `.md`,
            z. B. ``"GF-49"``). Die einzige fachliche Identität dieser
            Kompetenz -- `source.subject` ist nur Herkunftsmetadatum.
        source: Physische Herkunft der Quelldatei (Pfad/mtime/size/Fach).
        primarer_bereich_id: ID des Bereichs-Hubs aus `primarer_bereich`
            (Ziel einer `"classification"`-Kante), oder `None`, wenn das
            Pflichtfeld fehlte (in diesem Fall wurde der Knoten laut
            Fehlerklassifizierung bereits hart verworfen und existiert
            nicht im Snapshot -- das Feld ist hier trotzdem optional
            typisiert, um Zwischenzustände während des Mappings robust
            abzubilden).
        prozessbereich_ids: IDs der Bereichs-Hubs aus `prozessbereiche`
            (0..n weitere `"classification"`-Kanten).
        oberkompetenzen_ids: IDs der Elternkompetenzen aus `oberkompetenzen`
            (`"hierarchy"`-Kanten, Kind→Eltern). Mehrere Einträge sind ein
            Multi-Parent-DAG, kein Baum.
        voraussetzungen_ids: IDs der Vorbedingungs-Kompetenzen aus
            `voraussetzungen` (`"prerequisite"`-Kanten, Kind→Vorbedingung).
        offene_voraussetzungen: Freitext-Vorbedingungen ohne existierendes
            Linkziel (noch nicht importierter, späterer Import-Batch).
            Ausdrücklich KEINE Graph-Kante -- niemals als ID-Referenz
            interpretieren oder in Ancestor-/Descendant-/Kontext-
            Berechnungen einbeziehen.
        kc_zuordnung: Mindestens ein Eintrag; jede curriculare
            Zuordnung dieser Kompetenz zu Bundesland/Schulform/Niveau/
            Jahrgang/Anforderung samt Zitat.
        status: Einer von `STATUS_VALUES`.
        title: Erste nicht-leere Überschriftzeile des Markdown-Body (die
            einzige Body-Information, die eager gehalten wird -- eine
            kurze Zeile, kein Vault-Duplikat). Fällt beim Mapping auf den
            ersten nicht-leeren `kc_verweis` bzw. zuletzt auf die ID
            selbst zurück, falls der Body keine Überschrift enthält.
    """

    id: str
    source: SourceRef
    primarer_bereich_id: str | None
    prozessbereich_ids: tuple[str, ...]
    oberkompetenzen_ids: tuple[str, ...]
    voraussetzungen_ids: tuple[str, ...]
    offene_voraussetzungen: tuple[str, ...]
    kc_zuordnung: tuple[KcZuordnungEintrag, ...]
    status: str
    title: str


@dataclass(frozen=True)
class BereichNode:
    """Ein Bereichs-Hub (Inhalts- oder Prozessbereich), z. B. Datei `Bereiche/I-Raum und Form.md`.

    Ziel der `"classification"`-Kanten `primarer_bereich`/`prozessbereiche`
    von `KompetenzNode` aus. Bereichs-Dateien haben laut Schema KEIN
    YAML-Frontmatter -- nur Titel, eine `Kürzel:`-Zeile und Freitext.
    Bleibt im Gegensatz zu `KompetenzNode` bewusst mit vollständigem,
    eager gehaltenem `body_markdown`: es gibt nur ~11 solcher Dateien pro
    Fach, klein und stabil in der Anzahl -- die Lazy-Body-Sonderbehandlung
    für `KompetenzNode` (Meilenstein 2) wäre hier unnötiger Mehraufwand
    ohne relevanten Cache-Größenvorteil.

    Ein Bereichs-Hub bleibt im Domainmodell ein ganz normaler
    `"classification"`-Zielknoten -- eine etwaige besondere Darstellung
    (z. B. als feste obere Zeile im Graph-Layout) ist ausschließlich eine
    Rendering-/Layout-Entscheidung (Meilenstein 4), keine hier verankerte
    Graph-Invariante.

    Attributes:
        id: Vault-weit eindeutiger Bereichs-Name (Dateiname ohne `.md`,
            z. B. ``"I-Raum und Form"``).
        source: Physische Herkunft der Quelldatei.
        kuerzel: Das 2-3-stellige Bereichs-Kürzel aus der `Kürzel:`-Zeile
            im Body, z. B. ``"RF"``. Bestimmt bei Kompetenz-Dateien, deren
            `primarer_bereich` auf diesen Hub zeigt, das ID-Präfix.
        kind: ``"inhaltsbereich"`` (ID-Präfix `I-`) oder
            ``"prozessbereich"`` (ID-Präfix `P-`).
        title: Anzeigename des Bereichs (erste Überschriftzeile des Body).
        body_markdown: Vollständiger Freitext-Body (Beschreibung,
            Hinweise, Dataview-Abfrage) -- siehe Klassen-Docstring zur
            bewussten Ausnahme von der Lazy-Body-Regel.
    """

    id: str
    source: SourceRef
    kuerzel: str
    kind: Literal["inhaltsbereich", "prozessbereich"]
    title: str
    body_markdown: str
