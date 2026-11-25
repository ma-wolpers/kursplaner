"""Originale der Netz-Bausteine: Puffer über dem zuletzt geladenen Kompetenznetz (§37).

Die Sequenzleiter zeigt unter einem bearbeiteten Netz-Baustein sein Original aus
dem Kompetenznetz – die Variante seiner Seite aus der `CompetenceWording`. Damit das Neuladen der Leiter nach jeder Bearbeitung
nichts kostet, schlägt `CompetenceOriginalsBuffer.original` nur im Snapshot nach,
den `LoadKompetenzGraphUseCase` zuletzt geladen hat (`last_snapshot`) – es gibt
keine eigene Titel-Tabelle (SSOT: das Netz bleibt die einzige Quelle).

Geladen wird nur an zwei Stellen: beim **ersten** Öffnen der Leiter in einer
Sitzung (`ensure_loaded`, vom `SequenceLadderHost`) und – ohnehin – bei jedem
Öffnen/Neuaufbau des Kompetenznetzes, aus dem auch jedes Einfügen in die Leiter
stammt (das hält den Puffer aktuell). Ein Laden kostet am echten Netz
(≈1200 Kompetenzen, warmer Datei-Cache) rund 0,4 s, das erste im Prozess rund
0,7 s; bei jedem Einblenden der Leiter neu zu laden, würde das Umschalten
spürbar verlangsamen. Das Nachschlagen selbst kostet Mikrosekunden.
"""

from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.competence_wording import CompetenceWording, wording_of
from kursplaner.core.usecases.kompetenzgraph_load_usecase import LoadKompetenzGraphUseCase


class CompetenceOriginalsBuffer:
    """Erfüllt den Port `CompetenceOriginals` des Leiter-Lade-Use-Cases.

    Ohne Kompetenznetz-Unterstützung (`load_usecase is None`, PyYAML fehlt)
    liefert er nie ein Original – die Leiter zeigt dann einfach keine
    Originale an, statt abzustürzen.
    """

    def __init__(self, load_usecase: LoadKompetenzGraphUseCase | None) -> None:
        """Bindet den Puffer an den zentralen Kompetenznetz-Lade-Use-Case.

        Args:
            load_usecase: Lade-Use-Case, dessen `last_snapshot` der Puffer ist; ``None`` ohne PyYAML.
        """
        self._load = load_usecase

    def ensure_loaded(self, unterricht_dir: Path) -> None:
        """Lädt das Kompetenznetz, falls in dieser Sitzung noch keines geladen wurde; sonst nichts.

        Ein Lesefehler des Dateisystems wird geschluckt (kein Snapshot, also
        keine Originale; der nächste Aufruf versucht es erneut): die Leiter soll
        wegen eines fehlenden Netzes nie unbenutzbar werden.

        Args:
            unterricht_dir: Unterrichts-Basisverzeichnis (Fachinhalte-Auflösung wie im Kompetenznetz-Dialog).
        """
        if self._load is None or self._load.last_snapshot is not None:
            return
        try:
            self._load.execute(unterricht_dir)
        except OSError:
            return

    def original(self, kompetenz_id: str) -> CompetenceWording | None:
        """Formulierung zu *kompetenz_id* oder ``None`` (unbekannt, Netz nicht geladen).

        Das Original einer Seite liefert `CompetenceWording.for_side` – normalisiert
        wie beim Import, damit ein unveränderter Baustein exakt gleicht und nicht als
        bearbeitet gilt.
        """
        snapshot = self._load.last_snapshot if self._load is not None else None
        node = snapshot.nodes.get(kompetenz_id) if snapshot is not None else None
        return wording_of(node) if node is not None else None
