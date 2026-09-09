from __future__ import annotations

import re

from kursplaner.core.domain.kompetenzgraph_diagnostics import KompetenzFieldIssue
from kursplaner.core.domain.kompetenzgraph_node import BereichNode
from kursplaner.core.domain.kompetenzgraph_types import SourceRef

_HEADING_RE = re.compile(r"^\s*#{1,6}\s*(.+?)\s*$")
_KUERZEL_RE = re.compile(r"^\s*K[uü]rzel\s*:\s*`?([A-Za-z]{1,4})`?\s*$", re.IGNORECASE)


def _derive_bereich_title(body_text: str, node_id: str) -> str:
    """Leitet den Anzeigetitel eines Bereichs-Hubs aus der ersten Überschriftzeile ab.

    Fällt auf die ID selbst zurück, falls der Body (entgegen der
    Konvention) keine Überschrift enthält.
    """
    for line in body_text.splitlines():
        match = _HEADING_RE.match(line)
        if match and match.group(1).strip():
            return match.group(1).strip()
    return node_id


def _derive_kuerzel(body_text: str) -> str | None:
    """Sucht die dokumentierte Kürzel-Zeile (Muster "Kürzel: `XY`") im Body eines Bereichs-Hubs."""
    for line in body_text.splitlines():
        match = _KUERZEL_RE.match(line)
        if match:
            return match.group(1).strip().upper()
    return None


def parse_bereich_node_from_raw(
    body_text: str,
    *,
    node_id: str,
    source: SourceRef,
) -> tuple[BereichNode | None, tuple[KompetenzFieldIssue, ...]]:
    """Mappt den Rohinhalt einer `Bereiche/*.md`-Datei auf ein `BereichNode`-Domain-Objekt.

    Bereichs-Dateien haben laut Schema kein YAML-Frontmatter -- ihr
    gesamter Inhalt ist Freitext-Body. `kind` wird ausschließlich aus dem
    ID-Präfix abgeleitet (`I-` = Inhaltsbereich, `P-` = Prozessbereich),
    nicht aus einer Interpretation des Freitexts, um robust gegen
    abweichende Formulierungen im Beschreibungstext zu bleiben.

    Args:
        body_text: Vollständiger Dateiinhalt (kein Frontmatter zu
            entfernen).
        node_id: Bereichs-ID (Dateiname ohne `.md`, z. B.
            ``"I-Raum und Form"``).
        source: Physische Herkunft dieser Datei.

    Returns:
        `(node, issues)` -- `node` ist `None`, wenn `node_id` keinem der
        bekannten Präfixe entspricht (harter Fehler: die Datei kann dann
        keinem Kantentyp zugeordnet werden).
    """
    if node_id.startswith("I-"):
        kind = "inhaltsbereich"
    elif node_id.startswith("P-"):
        kind = "prozessbereich"
    else:
        return None, (
            KompetenzFieldIssue(
                field="id",
                message=f"Bereichs-ID {node_id!r} hat kein bekanntes Präfix ('I-'/'P-').",
                severity="error",
            ),
        )

    kuerzel = _derive_kuerzel(body_text)
    issues: tuple[KompetenzFieldIssue, ...] = ()
    if kuerzel is None:
        kuerzel = ""
        issues = (
            KompetenzFieldIssue(
                field="body",
                message="Keine 'Kürzel:'-Zeile im Bereichs-Body gefunden.",
                severity="warning",
            ),
        )

    node = BereichNode(
        id=node_id,
        source=source,
        kuerzel=kuerzel,
        kind=kind,
        title=_derive_bereich_title(body_text, node_id),
        body_markdown=body_text,
    )
    return node, issues
