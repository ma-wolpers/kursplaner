from __future__ import annotations

from dataclasses import dataclass

from kursplaner.core.domain.kompetenzgraph_filter import (
    KompetenzGraphFilter,
    KompetenzGraphVisibleSet,
    compute_visible_bereich_ids,
    compute_visible_set,
)
from kursplaner.core.domain.kompetenzgraph_focus import compute_focus_visible_ids
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot


@dataclass(frozen=True)
class KompetenzGraphView:
    """Das fertige, render-bereite Ergebnis der zentralen Sichtbarkeits-Pipeline.

    Attributes:
        visible: Primär-/Kontext-Trennung der final sichtbaren Kompetenz-
            Knoten -- nach Filter, Matchingtiefe UND einem etwaigen Fokus.
        visible_bereich_ids: Die zu `visible.all_ids` gehörenden sichtbaren
            Bereichs-Hubs.
    """

    visible: KompetenzGraphVisibleSet
    visible_bereich_ids: frozenset[str]


def compute_kompetenz_graph_view(
    snapshot: KompetenzGraphSnapshot,
    filter: KompetenzGraphFilter,
    mode_key: str,
    focus_id: str | None,
) -> KompetenzGraphView:
    """Einziger Ort, an dem Filter, Matchingtiefe und Fokus zu einer Ansicht kombiniert werden.

    Pipeline (siehe Implementierungsplan):

        Filter → primary_ids → (Matchingtiefe) → context_ids
               → allowed_ids = primary_ids ∪ context_ids
               → (optionaler Fokus, NUR innerhalb allowed_ids) → finale visible_ids

    Die GUI (Meilensteine 3-5) ruft AUSSCHLIESSLICH diese Funktion auf,
    statt Filter+Kontext+Fokus an mehreren Stellen selbst zusammenzubauen
    -- so ist die Reihenfolge und die Nicht-Umgehbarkeit der Filter durch
    den Fokus an genau einer Stelle garantiert:

    - Ein Knoten wird durch Kontext-Erweiterung oder Fokus NIE nachträglich
      zum Primärtreffer.
    - Der Fokus kann die gesetzten Filter (inkl. Matchingtiefe) niemals
      umgehen -- er kann die bereits erlaubte Menge nur EINSCHRÄNKEN
      (Schnittmenge), nie erweitern. Ist `focus_id` gesetzt, aber selbst
      außerhalb der erlaubten Menge (sollte durch die GUI-seitige
      Selektions-/Fokus-Gültigkeitsregel aus Meilenstein 5 bereits
      verhindert sein), wird der Fokus hier defensiv wie "kein Fokus"
      behandelt, statt eine leere oder inkonsistente Ansicht zu erzeugen.
    - Primär-/Kontext-Kennzeichnung bleibt auch innerhalb eines aktiven
      Fokus erhalten (jeweils separat mit der Fokus-Hülle geschnitten),
      damit der Renderer Primär- und Kontextknoten weiterhin
      unterschiedlich stylen kann.

    Args:
        snapshot: Das vollständige Kompetenznetz-Snapshot.
        filter: Der aktuelle Filterzustand (inkl. Matchingtiefe).
        mode_key: Der aktuell aktive View-Mode.
        focus_id: Die ID des fokussierten Knotens, oder `None` ohne
            aktiven Fokus.

    Returns:
        Die fertige, render-bereite `KompetenzGraphView`.
    """
    allowed = compute_visible_set(snapshot, filter, mode_key)

    if focus_id is not None and focus_id in allowed.all_ids:
        focus_closure = compute_focus_visible_ids(snapshot, mode_key, focus_id)
        final_visible = KompetenzGraphVisibleSet(
            primary_ids=allowed.primary_ids & focus_closure,
            context_ids=allowed.context_ids & focus_closure,
        )
    else:
        final_visible = allowed

    visible_bereich_ids = compute_visible_bereich_ids(snapshot, final_visible.all_ids)
    return KompetenzGraphView(visible=final_visible, visible_bereich_ids=visible_bereich_ids)
