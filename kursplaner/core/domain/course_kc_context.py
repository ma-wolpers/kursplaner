"""KC-Kontext eines Kurses: Bundesland und Schulform (einzige Quelle der Feldnamen und der Abgleichsregel).

Ein Kurs trägt in seiner Plan-Datei optional ``Bundesland`` und ``Schulform``.
Sie bestimmen, welche `kc_zuordnung`-Einträge des Kompetenznetzes für den Kurs
gelten – für den Startfilter des Kompetenznetzes und für die Frage, ob eine
Kompetenz im Kurs Haupt- oder Einzelkompetenz ist.

Abgleich mit dem Netz: Das Netz führt neben echten Schulformen (``IGS`` …) die
Stufenangaben ``SekI``/``SekII`` für KCs, die für mehrere Schulformen gemeinsam
gelten. Welche Schulformen eine Stufenangabe umfasst, steht allein in
`STUFEN_SCHULFORMEN`; die Stufe selbst grenzt der Jahrgang ab.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

BUNDESLAND_KEY = "Bundesland"
"""Frontmatter-Feld der Plan-Datei für das Bundesland des Kurses."""

SCHULFORM_KEY = "Schulform"
"""Frontmatter-Feld der Plan-Datei für die Schulform des Kurses."""

STUFEN_SCHULFORMEN: dict[str, frozenset[str] | None] = {
    "SekI": None,
    "SekII": frozenset({"Gymnasium", "Gesamtschule", "IGS", "KGS", "Abendgymnasium", "Kolleg"}),
}
"""Stufenangaben in `kc_zuordnung.schulform` → umfasste Kurs-Schulformen (``None`` = alle).

Quellen im Vault: ``SekI`` – Informatik-KC SekI gilt schulformübergreifend
(``Informatik/_Schema.md``); ``SekII`` – Sek-II-KC Mathematik für „Gymnasium,
Gesamtschule, Abendgymnasium und Kolleg“, ausdrücklich nicht Berufliches
Gymnasium (``Mathematik/_Import-Entscheidungen-Log.md`` #36). IGS und KGS sind
Gesamtschulen.
"""


@dataclass(frozen=True)
class CourseKcContext:
    """Bundesland und Schulform eines Kurses; ``None`` = nicht festgelegt (passt zu allem)."""

    bundesland: str | None = None
    schulform: str | None = None


def _clean(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def course_kc_context(metadata: Mapping[str, object]) -> CourseKcContext:
    """Liest den KC-Kontext aus den Metadaten einer Plan-Datei (fehlende Felder → ``None``)."""
    return CourseKcContext(_clean(metadata.get(BUNDESLAND_KEY)), _clean(metadata.get(SCHULFORM_KEY)))


def kc_context_fields(context: CourseKcContext) -> tuple[tuple[str, str], ...]:
    """Gesetzte Felder als ``(Frontmatter-Key, Wert)`` in Schreibreihenfolge (fehlende entfallen)."""
    pairs = ((BUNDESLAND_KEY, context.bundesland), (SCHULFORM_KEY, context.schulform))
    return tuple((key, value) for key, value in pairs if value)


def schulform_matches(entry_schulform: str | None, wanted: str | None) -> bool:
    """Ob ein `kc_zuordnung`-Eintrag mit *entry_schulform* zur gesuchten Schulform passt.

    Ohne gesuchte Schulform passt alles; eine Stufenangabe passt zu den Schulformen,
    die `STUFEN_SCHULFORMEN` ihr zuordnet.
    """
    if wanted is None or entry_schulform == wanted:
        return True
    if entry_schulform not in STUFEN_SCHULFORMEN:
        return False
    covered = STUFEN_SCHULFORMEN[entry_schulform]
    return covered is None or wanted in covered
