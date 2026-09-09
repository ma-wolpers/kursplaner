from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.kompetenzgraph_dag import check_kompetenz_graph_for_cycles
from kursplaner.core.domain.kompetenzgraph_diagnostics import CycleDiagnostic, KompetenzFileDiagnostic
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.ports.repositories import KompetenzGraphRepository


@dataclass(frozen=True)
class KompetenzGraphLoadResult:
    """Ergebnis eines vollständigen Kompetenzgraph-Ladevorgangs, inklusive Diagnosen.

    Attributes:
        snapshot: Der vollständige, fachübergreifende Kompetenznetz-Snapshot
            -- wird immer vollständig geliefert, unabhängig davon, ob
            Zyklen gefunden wurden (siehe `cycle_diagnostics`).
        file_diagnostics: Pro-Datei-Diagnosen (Lese-/YAML-/Schema-Fehler).
        cycle_diagnostics: Reines Diagnoseinstrument (kein Render-Guard) --
            siehe `kompetenzgraph_dag.py::check_kompetenz_graph_for_cycles`.
        loaded_subjects: Die tatsächlich geladenen Fachordner.
    """

    snapshot: KompetenzGraphSnapshot
    file_diagnostics: tuple[KompetenzFileDiagnostic, ...]
    cycle_diagnostics: tuple[CycleDiagnostic, ...]
    loaded_subjects: tuple[str, ...]


class LoadKompetenzGraphUseCase:
    """Orchestriert das (gecachte) Laden des Kompetenzgraphen samt Zyklen-Diagnose.

    Ruft nach jedem Snapshot-Aufbau IMMER `check_kompetenz_graph_for_cycles()`
    auf -- die vom Nutzer gewünschte automatische DAG-Prüfung nach jedem
    (Neu-)Laden. Das Ergebnis ist rein informativ und ändert nichts am
    gelieferten `snapshot` selbst.
    """

    def __init__(self, kompetenzgraph_repo: KompetenzGraphRepository):
        """Initialisiert den Use Case mit einem `KompetenzGraphRepository`-Port."""
        self.kompetenzgraph_repo = kompetenzgraph_repo

    def execute(self, unterricht_dir: Path, subject_folders: Sequence[str] | None = None) -> KompetenzGraphLoadResult:
        """Lädt den Kompetenzgraphen (gecacht, siehe Repository) für die gegebenen Fächer.

        Args:
            unterricht_dir: Unterrichts-Basisverzeichnis (für die
                Fachinhalte-Pfadauflösung).
            subject_folders: Zu ladende Fachordner, oder `None` für alle
                automatisch erkannten strukturierten Fächer.
        """
        snapshot, file_diagnostics, loaded_subjects = self.kompetenzgraph_repo.load_snapshot(
            unterricht_dir, subject_folders
        )
        cycle_diagnostics = check_kompetenz_graph_for_cycles(snapshot)
        return KompetenzGraphLoadResult(
            snapshot=snapshot,
            file_diagnostics=file_diagnostics,
            cycle_diagnostics=cycle_diagnostics,
            loaded_subjects=loaded_subjects,
        )
