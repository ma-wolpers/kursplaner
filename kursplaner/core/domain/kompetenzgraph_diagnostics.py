from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from kursplaner.core.domain.kompetenzgraph_types import EdgeKind

FieldIssueSeverity = Literal["error", "warning"]


@dataclass(frozen=True)
class KompetenzFieldIssue:
    """Ein einzelnes, feldbezogenes Validierungsproblem beim Mapping einer Datei.

    Attributes:
        field: Name des betroffenen Frontmatter-Felds, z. B.
            ``"kc_zuordnung"`` oder ``"status"``.
        message: Für Diagnose-Anzeige geeignete, deutschsprachige
            Beschreibung des Problems.
        severity: ``"error"`` für harte Probleme, die zum Verwerfen der
            gesamten Datei führen (z. B. fehlendes `primarer_bereich`),
            ``"warning"`` für weiche Probleme, bei denen nur der
            betroffene Teil verworfen wird (z. B. ein ungültiger
            `kc_zuordnung`-Eintrag) -- siehe Fehlerklassifizierungs-
            Tabelle im Implementierungsplan.
    """

    field: str
    message: str
    severity: FieldIssueSeverity


@dataclass(frozen=True)
class KompetenzFileDiagnostic:
    """Diagnose zu genau einer Quelldatei -- deckt sowohl Mapping-Probleme als auch reine Lesefehler ab.

    Wird sowohl erzeugt, wenn eine Datei zwar gelesen, aber ihr Inhalt
    nicht schema-konform ist (`issues` nicht leer, `node_id` ggf. gesetzt,
    falls zumindest die ID aus dem Dateinamen ableitbar war), als auch,
    wenn die Datei gar nicht erst gelesen werden konnte (z. B. durch
    gleichzeitigen externen Schreibzugriff eines Sync-Programms --
    `OSError`/`UnicodeDecodeError`/`yaml.YAMLError`, siehe
    `kompetenzgraph_repository.py`). In beiden Fällen gilt: die Datei wird
    übersprungen, kein Cache-Eintrag geschrieben (automatischer Retry beim
    nächsten Laden), und der restliche Snapshot wird trotzdem vollständig
    aufgebaut -- ein Einzelfehler darf nie das gesamte Popup unbrauchbar
    machen.

    Attributes:
        source_path: Absoluter Pfad der betroffenen Datei.
        node_id: Kompetenz-/Bereichs-ID, falls aus dem Dateinamen ableitbar
            und die Datei zumindest so weit verarbeitet wurde, sonst
            `None` (z. B. bei einem reinen Lesefehler vor jeder
            Interpretation des Inhalts).
        issues: Die konkreten Feldprobleme, die zu dieser Diagnose
            geführt haben. Leer bei einem reinen Lesefehler ohne
            Feldbezug.
    """

    source_path: Path
    node_id: str | None
    issues: tuple[KompetenzFieldIssue, ...]


@dataclass(frozen=True)
class CycleDiagnostic:
    """Ein gefundener Zyklus in genau einem Kantentyp des Kompetenznetzes.

    Reines Diagnoseinstrument (siehe `kompetenzgraph_dag.py`) -- niemals
    ein Render-Guard. Ein Zyklus ist ein Datenintegritätsproblem, aber
    kein Grund, den Graphen unbrauchbar zu machen: der Snapshot wird immer
    vollständig geliefert, unabhängig davon, ob `CycleDiagnostic`-Einträge
    existieren. Layout-seitig wird eine Rückkante nur für die
    Tiefenberechnung neutralisiert (siehe `kompetenzgraph_layout.py`),
    niemals aus dem gerenderten Graphen entfernt.

    Attributes:
        edge_kind: `"hierarchy"` oder `"prerequisite"` -- niemals
            `"classification"` (Bereichs-Hubs haben keine eigenen
            Ober-/Voraussetzungs-Kanten und können daher strukturell
            nicht an einem Zyklus dieser beiden Kantentypen beteiligt
            sein).
        member_ids: IDs der am Zyklus beteiligten Kompetenzen, in der
            Reihenfolge, in der sie im Zyklus aufeinanderfolgen.
    """

    edge_kind: EdgeKind
    member_ids: tuple[str, ...]


@dataclass(frozen=True)
class UnresolvedLink:
    """Eine Wikilink-Referenz, deren Ziel-ID im aktuellen Knoten-/Bereichs-Set fehlt.

    Laut Schema ausdrücklich ZULÄSSIG (z. B. weil der Zielbereich eines
    Kerncurriculums noch nicht importiert wurde) -- kein Fehler, nur eine
    Diagnose. Wird in der GUI als gestrichelte Kante zu einem gedimmten,
    nicht interaktiven Platzhalter-Knoten dargestellt (siehe Meilenstein 5)
    und beeinflusst nie Layout, Fokus, Kontext-Matching oder Filter der
    echten Knoten.

    Attributes:
        source_id: ID der Kompetenz, die den nicht auflösbaren Link
            enthält.
        field: Feldname, in dem der Link stand (z. B.
            ``"oberkompetenzen"`` oder ``"voraussetzungen"``).
        target_id: Die referenzierte, aber nicht existierende Ziel-ID.
    """

    source_id: str
    field: str
    target_id: str


@dataclass(frozen=True)
class DuplicateIdDiagnostic:
    """Zwei oder mehr Quelldateien beanspruchen dieselbe Kompetenz-/Bereichs-ID.

    Die Vault-Invariante "ID ist eindeutig" (siehe `_Schema.md`) wird vom
    Kursplaner nicht blind vorausgesetzt -- `kompetenzgraph_snapshot_builder.py`
    erkennt Kollisionen aktiv (z. B. über Fachgrenzen hinweg) und wählt
    deterministisch einen Gewinner, statt eine Datei still zu überschreiben.

    Attributes:
        id: Die mehrfach vergebene ID.
        winning_source: Herkunft der Datei, die in den Snapshot
            übernommen wurde (deterministisch gewählt nach
            `(source.subject, source.path)`).
        discarded_sources: Herkünfte aller weiteren Dateien mit derselben
            ID, die verworfen wurden.
    """

    id: str
    winning_source: Path
    discarded_sources: tuple[Path, ...]
