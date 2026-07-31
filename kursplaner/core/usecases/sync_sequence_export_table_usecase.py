"""Use Case: Aktualisieren der persistenten Sequenzdatei beim Export einer Sequenz.

Kapselt den Ablauf "Sequenzdatei sicherstellen → Export-Tabelle einsetzen →
aktuelles Sequenzziel/Leitkompetenz auslesen" als einen einzigen, von
`ExportTopicUnitsPdfUseCase` wiederverwendbaren Schritt. Die eigentliche
Tabellen-/Feld-Fachlogik (welche Zeilen exportiert werden) bleibt beim
aufrufenden Export-Use-Case; dieser Use Case kennt nur die Sequenzdatei.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.ports.repositories import SequencePlanRepository


@dataclass(frozen=True)
class SequenceExportSyncResult:
    """Rückgabe nach Aktualisierung der persistenten Sequenzdatei.

    Attributes:
        sequence_path: Pfad der aktualisierten Sequenz-Markdown-Datei.
        sequenzziel: Aktuell in der Sequenzdatei hinterlegtes Sequenzziel.
        leitkompetenz: Aktuell in der Sequenzdatei hinterlegte Leitkompetenz.
    """

    sequence_path: Path
    sequenzziel: str
    leitkompetenz: str


class SyncSequenceExportTableUseCase:
    """Schreibt die Export-Tabelle einer Sequenz in deren persistente Markdown-Datei."""

    def __init__(self, sequence_plan_repo: SequencePlanRepository) -> None:
        """Initialisiert den Use Case mit dem Sequenzdatei-Repository.

        Args:
            sequence_plan_repo: Repository für Lebenszyklus und Inhalt der
                persistenten Sequenz-Markdown-Dateien.
        """
        self._sequence_plan_repo = sequence_plan_repo

    def execute(
        self,
        *,
        table: PlanTableData,
        oberthema: str,
        headers: list[str],
        rows: list[list[str]],
    ) -> SequenceExportSyncResult:
        """Stellt die Sequenzdatei sicher und ersetzt darin die Export-Tabelle.

        Args:
            table: Aktuell geladene Planungstabelle (liefert Lerngruppe/Halbjahr
                für die Dateibenennung).
            oberthema: Oberthema-Text der Sequenz; dient als `sequence_name` für
                die Dateiauflösung.
            headers: Spaltenüberschriften der Export-Tabelle.
            rows: Zeilenwerte der Export-Tabelle, spaltenweise passend zu `headers`.

        Returns:
            Ergebnis mit Dateipfad und aktuellem Sequenzziel/Leitkompetenz, zur
            direkten Weiterverwendung im PDF-/Markdown-Export.
        """
        sequence_path = self._sequence_plan_repo.ensure_sequence_document(table=table, sequence_name=oberthema)
        table_lines = self._sequence_plan_repo.render_markdown_table(headers=headers, rows=rows)
        self._sequence_plan_repo.replace_trailing_table(sequence_path=sequence_path, table_lines=table_lines)
        sequenzziel, leitkompetenz = self._sequence_plan_repo.read_goal_and_focus_competency(sequence_path)
        return SequenceExportSyncResult(
            sequence_path=sequence_path,
            sequenzziel=sequenzziel,
            leitkompetenz=leitkompetenz,
        )
