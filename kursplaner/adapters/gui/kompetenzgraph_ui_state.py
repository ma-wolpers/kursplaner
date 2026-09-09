from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphFilter
from kursplaner.core.domain.kompetenzgraph_view_mode import MODE_OBER_TEIL


@dataclass
class KompetenzGraphUiState:
    """Veränderlicher GUI-Zustand des Kompetenzgraph-Popups.

    Bewusst NICHT `frozen` -- im Gegensatz zu den unveränderlichen
    Domain-Typen (`KompetenzGraphFilter`, `KompetenzGraphSnapshot`, ...)
    ist dies reiner, pro Popup-Instanz gehaltener GUI-Zustand, den
    `kompetenzgraph_dialog.py` bei jeder Interaktion direkt mutiert.

    Attributes:
        filter: Aktueller Filterzustand (inkl. Matchingtiefe).
        view_mode: `MODE_OBER_TEIL` oder `MODE_FORT_VORAUS`.
        selected_id: ID des per Rahmen markierten Knotens, oder `None`.
        focus_id: ID des fokussierten Knotens (Füllfarbe + eingeblendete
            Teilmenge), oder `None` ohne aktiven Fokus.
        bereich_hues: Einmalig bei Popup-Öffnung aus ALLEN
            `snapshot.bereiche`-IDs berechnete, über die gesamte Sitzung
            stabile Farbton-Zuordnung (siehe
            `kompetenzgraph_canvas_colors.py::assign_bereich_hues`) --
            bleibt unverändert über Filter-/Ansichtswechsel hinweg, damit
            ein Bereich nie die Farbe wechselt.
    """

    filter: KompetenzGraphFilter
    view_mode: str = MODE_OBER_TEIL
    selected_id: str | None = None
    focus_id: str | None = None
    bereich_hues: Mapping[str, float] = field(default_factory=dict)
