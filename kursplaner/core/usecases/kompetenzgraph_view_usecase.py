from __future__ import annotations

from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphFilter
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.kompetenzgraph_view import KompetenzGraphView, compute_kompetenz_graph_view


class ComputeKompetenzGraphViewUseCase:
    """Dünner Usecase-Wrapper um die reine Domain-Pipeline `compute_kompetenz_graph_view()`.

    Ohne eigene Port-Abhängigkeit (die Berechnung ist vollständig I/O-frei),
    aber dennoch als Usecase modelliert (analog `RowDisplayModeUseCase`):
    die GUI (`kompetenzgraph_dialog.py`) ruft bei jeder Filter-/View-Mode-/
    Fokus-Änderung ausschließlich diesen einen Usecase auf, statt die
    Domain-Funktion direkt zu importieren -- konsistent mit der
    REINE-GUI-Regel, dass die GUI stets genau einen fachlich passenden
    UseCase pro Interaktion aufruft.
    """

    def execute(
        self,
        snapshot: KompetenzGraphSnapshot,
        filter: KompetenzGraphFilter,
        mode_key: str,
        focus_id: str | None,
        *,
        text_search_matches: frozenset[str] | None = None,
    ) -> KompetenzGraphView:
        """Berechnet die aktuell sichtbare Ansicht für den gegebenen Filter-/Modus-/Fokus-/Textsuche-Zustand."""
        return compute_kompetenz_graph_view(
            snapshot, filter, mode_key, focus_id, text_search_matches=text_search_matches
        )
