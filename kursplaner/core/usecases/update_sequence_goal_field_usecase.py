"""Use Case: Schreiben eines einzelnen Sequenzfelds (Sequenzziel oder Leitkompetenz).

Wird aufgerufen, wenn der Nutzer die spannende Grid-Zelle für Sequenzziel oder
Leitkompetenz verlässt (Focus-Out) und sich der Text geändert hat. Liest zuerst
den aktuellen Gegenwert, damit das jeweils andere Feld beim Schreiben nicht
überschrieben wird (die Repository-Schreibmethode erwartet immer beide Werte).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.ports.repositories import SequencePlanRepository

SequenceFieldKey = Literal["Sequenzziel", "Leitkompetenz"]


@dataclass(frozen=True)
class UpdateSequenceGoalFieldResult:
    """Rückgabe nach dem Schreiben eines Sequenzfelds.

    Attributes:
        sequence_path: Pfad der aktualisierten Sequenz-Markdown-Datei.
        sequenzziel: Sequenzziel-Text nach dem Schreibvorgang.
        leitkompetenz: Leitkompetenz-Text nach dem Schreibvorgang.
    """

    sequence_path: Path
    sequenzziel: str
    leitkompetenz: str


class UpdateSequenceGoalFieldUseCase:
    """Aktualisiert Sequenzziel oder Leitkompetenz einer automatisch erkannten Sequenz."""

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
        field_key: SequenceFieldKey,
        value: str,
    ) -> UpdateSequenceGoalFieldResult:
        """Schreibt genau ein Sequenzfeld, ohne das jeweils andere zu verändern.

        Args:
            table: Aktuell geladene Planungstabelle (liefert Lerngruppe/Halbjahr
                für die Dateibenennung).
            oberthema: Oberthema-Text der Sequenz; dient als `sequence_name` für
                die Dateiauflösung.
            field_key: Welches der beiden Felder geschrieben werden soll.
            value: Neuer Text für dieses Feld.

        Returns:
            Das Ergebnis mit dem aktualisierten Dateipfad und beiden aktuellen
            Feldwerten (zur direkten Übernahme in den Grid-Zustand).
        """
        sequence_path = self._sequence_plan_repo.ensure_sequence_document(table=table, sequence_name=oberthema)
        current_sequenzziel, current_leitkompetenz = self._sequence_plan_repo.read_goal_and_focus_competency(
            sequence_path
        )

        sequenzziel = value if field_key == "Sequenzziel" else current_sequenzziel
        leitkompetenz = value if field_key == "Leitkompetenz" else current_leitkompetenz

        self._sequence_plan_repo.write_goal_and_focus_competency(
            sequence_path=sequence_path,
            sequenzziel=sequenzziel,
            leitkompetenz=leitkompetenz,
        )
        return UpdateSequenceGoalFieldResult(
            sequence_path=sequence_path,
            sequenzziel=sequenzziel,
            leitkompetenz=leitkompetenz,
        )
