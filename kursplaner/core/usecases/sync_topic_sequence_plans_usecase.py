"""Use Case: automatisches Erkennen und Anlegen von Themen-Sequenz-Dateien.

Dieser Use Case verbindet die reine Adjazenz-Erkennung aus
`kursplaner.core.domain.topic_sequence_runs` mit der persistenten
Sequenz-Dateiablage (`SequencePlanRepository`): für jeden erkannten Lauf von
mindestens zwei benachbarten, gleichthematischen Einheiten wird sichergestellt,
dass eine Sequenzdatei existiert, und deren aktuelles Sequenzziel/Leitkompetenz
wird für die Grid-Anzeige geladen.

Hält zusätzlich die `## Export`-Tabelle jeder Sequenzdatei aktuell (dieselbe
Zeilenlogik wie beim manuellen "Exportieren als..." über
`ExportTopicUnitsPdfUseCase`/`SyncSequenceExportTableUseCase`), damit eine
Sequenz-md schon bei jedem automatischen Sync die aktuell zugehörigen
Einheiten zeigt, statt nur nach einem manuell ausgelösten Export.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.topic_sequence_runs import (
    EXPORT_TABLE_HEADERS,
    TopicSequenceRun,
    build_export_rows_for_run,
    compute_topic_sequence_runs,
)
from kursplaner.core.ports.repositories import SequencePlanRepository
from kursplaner.core.usecases.sync_sequence_export_table_usecase import SyncSequenceExportTableUseCase

MIN_SEQUENCE_MEMBER_COUNT = 2
"""Mindestanzahl an Kettenmitgliedern, ab der ein Lauf als "Sequenz" gilt."""


@dataclass(frozen=True)
class TopicSequencePlanView:
    """Anzeige-/Bearbeitungszustand einer einzelnen Sequenz für das Grid.

    Attributes:
        run: Der zugrunde liegende, fachlich erkannte Sequenz-Lauf.
        sequence_path: Pfad der zugehörigen, persistenten Sequenz-Markdown-Datei.
        sequenzziel: Aktueller Sequenzziel-Text (kann leer sein).
        leitkompetenz: Aktueller Leitkompetenz-Text (kann leer sein).
    """

    run: TopicSequenceRun
    sequence_path: Path
    sequenzziel: str
    leitkompetenz: str

    @property
    def is_incomplete(self) -> bool:
        """Prüft, ob Sequenzziel oder Leitkompetenz noch unausgefüllt sind."""
        return not self.sequenzziel.strip() or not self.leitkompetenz.strip()


class SyncTopicSequencePlansUseCase:
    """Ermittelt alle relevanten Sequenzen einer Planungstabelle und hält deren Dateien aktuell.

    Wird nach jedem Neuladen der Tagesliste aufgerufen (z. B. nach Edits oder
    Sichtbarkeits-Toggles), damit neu entstandene Sequenzen sofort eine
    Sequenzdatei erhalten (`ensure_sequence_document` ist idempotent und bei
    bereits existierender Datei ein günstiger Dateisystem-Check).
    """

    def __init__(
        self,
        sequence_plan_repo: SequencePlanRepository,
        sequence_export_sync: SyncSequenceExportTableUseCase,
    ) -> None:
        """Initialisiert den Use Case mit Sequenzdatei-Repository und Export-Sync.

        Args:
            sequence_plan_repo: Repository für Lebenszyklus und Inhalt der
                persistenten Sequenz-Markdown-Dateien.
            sequence_export_sync: Use Case, der die Export-Tabelle einer
                Sequenzdatei mit derselben Zeilenlogik aktuell hält wie der
                manuelle Sequenzplan-Export.
        """
        self._sequence_plan_repo = sequence_plan_repo
        self._sequence_export_sync = sequence_export_sync

    def execute(
        self, *, table: PlanTableData, day_columns: list[dict[str, object]]
    ) -> list[TopicSequencePlanView]:
        """Berechnet Sequenz-Läufe und synchronisiert deren Dateien.

        Args:
            table: Aktuell geladene Planungstabelle (liefert Lerngruppe/Halbjahr
                für die Dateibenennung).
            day_columns: Vollständige, unprojizierte Tagesliste in chronologischer
                Reihenfolge (`app.raw_day_columns`).

        Returns:
            Eine `TopicSequencePlanView` pro erkannter Sequenz (Läufe mit
            weniger als `MIN_SEQUENCE_MEMBER_COUNT` Mitgliedern werden nicht
            als eigenständige Sequenz behandelt und tauchen nicht in der
            Rückgabe auf).
        """
        runs = compute_topic_sequence_runs(day_columns)
        views: list[TopicSequencePlanView] = []
        for run in runs:
            if run.member_count < MIN_SEQUENCE_MEMBER_COUNT:
                continue

            export_rows = build_export_rows_for_run(day_columns, run)
            if export_rows:
                rows = [
                    [row.datum, row.stunden, row.thema, row.stundenziel, row.prozesskompetenzen]
                    for row in export_rows
                ]
                sync_result = self._sequence_export_sync.execute(
                    table=table,
                    oberthema=run.oberthema,
                    headers=list(EXPORT_TABLE_HEADERS),
                    rows=rows,
                )
                sequence_path = sync_result.sequence_path
                sequenzziel = sync_result.sequenzziel
                leitkompetenz = sync_result.leitkompetenz
            else:
                sequence_path = self._sequence_plan_repo.ensure_sequence_document(
                    table=table, sequence_name=run.oberthema
                )
                sequenzziel, leitkompetenz = self._sequence_plan_repo.read_goal_and_focus_competency(sequence_path)

            views.append(
                TopicSequencePlanView(
                    run=run,
                    sequence_path=sequence_path,
                    sequenzziel=sequenzziel,
                    leitkompetenz=leitkompetenz,
                )
            )
        return views
