from __future__ import annotations

from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.kompetenzgraph_view_mode import ancestor_closure, descendant_closure


def compute_focus_visible_ids(snapshot: KompetenzGraphSnapshot, mode_key: str, focus_id: str) -> frozenset[str]:
    """Berechnet die im Fokus-Modus sichtbare Teilmenge für einen fokussierten Knoten.

    Enthält `focus_id` selbst sowie alle transitiv (über beliebig viele
    Generationen) mit ihm hierarchisch verwandten Knoten entlang der
    aktiven View-Semantik -- Vorfahren UND Nachfahren, aber NICHT "über
    Eck" verbundene Geschwister/Cousinen (Knoten, die nur einen
    gemeinsamen Vorfahren teilen, ohne selbst auf dem eigenen Ancestor-/
    Descendant-Pfad von `focus_id` zu liegen).

    Bewusst zwei GETRENNTE, nicht mischende Traversierungen
    (`ancestor_closure()` UND `descendant_closure()`, jeweils NUR in eine
    Richtung) statt einer gemischten `bidirectional_closure()`: eine
    gemischte BFS würde bei einem Schritt hoch zu einem Vorfahren und von
    dort einen Schritt wieder hinunter genau die verbotenen Geschwister
    erreichen ("über Eck") -- das ist für Kontext-Matching
    (`kompetenzgraph_context.py`) fachlich gewollt, für den Fokus-Modus
    aber ausdrücklich NICHT.

    Args:
        snapshot: Das vollständige Kompetenznetz-Snapshot.
        mode_key: Der aktuell aktive View-Mode (bestimmt, ob "verwandt"
            Ober-/Teilkompetenz oder Fort-/Voraussetzung bedeutet).
        focus_id: Die ID des fokussierten Knotens.

    Returns:
        Die vollständige Fokus-Sichtbarkeitsmenge, inklusive `focus_id`.
    """
    seed = frozenset({focus_id})
    return ancestor_closure(snapshot, mode_key, seed) | descendant_closure(snapshot, mode_key, seed)
