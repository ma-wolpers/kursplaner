from __future__ import annotations

from pathlib import Path

from kursplaner.core.ports.repositories import KompetenzGraphRepository

_UNREADABLE_BODY_PLACEHOLDER = "(Inhalt konnte nicht geladen werden -- Datei nicht lesbar oder verschoben.)"


class LoadKompetenzNodeBodyUseCase:
    """Lädt den vollständigen Markdown-Body EINER Kompetenz-Datei bei Bedarf nach (Lazy Body).

    Wird ausschließlich vom Detailbereich der GUI für den gerade
    ausgewählten Knoten aufgerufen -- niemals für alle Knoten eines
    Snapshots, siehe die Lazy-Body-Entscheidung im Implementierungsplan.
    """

    def __init__(self, kompetenzgraph_repo: KompetenzGraphRepository):
        """Initialisiert den Use Case mit einem `KompetenzGraphRepository`-Port."""
        self.kompetenzgraph_repo = kompetenzgraph_repo

    def execute(self, source_path: Path) -> str:
        """Liest den Body frisch von der Platte; ein Lesefehler liefert einen Platzhaltertext statt zu werfen.

        Args:
            source_path: `KompetenzNode.source.path` des gerade
                ausgewählten Knotens.
        """
        try:
            return self.kompetenzgraph_repo.read_body(source_path)
        except OSError:
            return _UNREADABLE_BODY_PLACEHOLDER
