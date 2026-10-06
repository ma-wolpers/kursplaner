"""Use Case: Schreiben eines einzelnen Sequenz-Zielfelds (Sequenzziel oder Leitkompetenzen).

"Goal field" meint eines der beiden Zielfelder einer Sequenz — das Sequenzziel
(ein Text) **oder** die vorrangig geförderten Kompetenzen (eine Liste) —, nicht
eine einzelne Kompetenz. Wird aufgerufen, wenn der Nutzer die spannende
Grid-Zelle für Sequenzziel oder Leitkompetenzen verlässt (Focus-Out) und sich
der Text geändert hat. Liest zuerst den aktuellen Gegenwert, damit das jeweils
andere Feld beim Schreiben nicht überschrieben wird (die Repository-
Schreibmethode erwartet immer beide Werte).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from kursplaner.core.domain.list_cell_text import parse_list_cell
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.ports.repositories import SequencePlanRepository

SequenceFieldKey = Literal["Sequenzziel", "Leitkompetenzen"]


@dataclass(frozen=True)
class UpdateSequenceGoalFieldResult:
    """Rückgabe nach dem Schreiben eines Sequenz-Zielfelds.

    Attributes:
        sequence_path: Pfad der aktualisierten Sequenz-Markdown-Datei.
        sequenzziel: Sequenzziel-Text nach dem Schreibvorgang.
        leitkompetenzen: Leitkompetenzen nach dem Schreibvorgang.
    """

    sequence_path: Path
    sequenzziel: str
    leitkompetenzen: tuple[str, ...]


class UpdateSequenceGoalFieldUseCase:
    """Aktualisiert Sequenzziel oder Leitkompetenzen einer automatisch erkannten Sequenz."""

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
        """Schreibt genau ein Sequenz-Zielfeld, ohne das jeweils andere zu verändern.

        Für ``Leitkompetenzen`` ist `value` der rohe Text der Grid-Listenzelle;
        er wird wie jede Listenzelle über `list_cell_text.parse_list_cell`
        zerlegt (Trenner: Zeile aus ≥ 2 Strichen oder ``;``). Für
        ``Sequenzziel`` wird der Text unverändert übernommen.

        Args:
            table: Aktuell geladene Planungstabelle (liefert Lerngruppe/Halbjahr
                für die Dateibenennung).
            oberthema: Oberthema-Text der Sequenz; dient als `sequence_name` für
                die Dateiauflösung.
            field_key: Welches der beiden Felder geschrieben werden soll.
            value: Neuer Zelltext für dieses Feld.

        Returns:
            Das Ergebnis mit dem aktualisierten Dateipfad und beiden aktuellen
            Feldwerten (zur direkten Übernahme in den Grid-Zustand).
        """
        sequence_path = self._sequence_plan_repo.ensure_sequence_document(table=table, sequence_name=oberthema)
        current_sequenzziel, current_leitkompetenzen = self._sequence_plan_repo.read_goal_and_focus_competencies(
            sequence_path
        )

        sequenzziel = value if field_key == "Sequenzziel" else current_sequenzziel
        leitkompetenzen = tuple(parse_list_cell(value)) if field_key == "Leitkompetenzen" else current_leitkompetenzen

        self._sequence_plan_repo.write_goal_and_focus_competencies(
            sequence_path=sequence_path,
            sequenzziel=sequenzziel,
            leitkompetenzen=leitkompetenzen,
        )
        return UpdateSequenceGoalFieldResult(
            sequence_path=sequence_path,
            sequenzziel=sequenzziel,
            leitkompetenzen=leitkompetenzen,
        )
