"""Use Case: Export einer Themen-Sequenz (Kette benachbarter Einheiten) als PDF/Markdown.

Exportiert ausschließlich die zusammenhängende Kette benachbarter Einheiten, die
zur ausgewählten Einheit gehört (siehe `topic_sequence_runs.compute_topic_sequence_runs`),
nicht mehr jedes Vorkommen desselben Oberthema-Textes im gesamten Kursplan.
Zusätzlich werden die Leitkompetenzen aus der persistenten Sequenzdatei geladen
(deren Export-Tabelle beim Export aktualisiert wird) und im Kopf des Dokuments
angezeigt. Das Sequenzziel bleibt programmintern erhalten (Rückgabe, Sequenzdatei),
erscheint aber nicht im Export. Aufbau des Dokuments nach der Ref-Vorlage
„Sequenzplan“: Exportdatum, Titel, Kurszeile, Thema der Sequenz, vorrangig
geförderte Kompetenz(en), Tabelle (`sequence_export_table`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.export_date_formatting import extract_term_token, schoolyear_from_term
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.topic_sequence_runs import (
    EXPORTABLE_LESSON_TYPES,
    build_export_rows_for_run,
    compute_topic_sequence_runs,
    find_run_for_row_index,
    row_lesson_type,
)
from kursplaner.core.domain.wiki_links import strip_wiki_link
from kursplaner.core.ports.sequence_export import ExportTableRow
from kursplaner.core.usecases.sequence_export_table import EXPORT_TABLE_HEADERS, export_row_cells
from kursplaner.core.usecases.sync_sequence_export_table_usecase import SyncSequenceExportTableUseCase

SEQUENCE_PLAN_TITLE = "Sequenzplan"
"""Dokumenttitel des Sequenzplan-Exports (Ref-Vorlage)."""


@dataclass(frozen=True)
class TopicUnitsPdfDocument:
    """Vollständige, medienneutrale Renderdaten des Sequenzplan-Exports (PDF/Markdown).

    Die Spaltenüberschriften sind fester Teil des Exportformats und stehen
    deshalb nicht hier, sondern einzig in `sequence_export_table.EXPORT_TABLE_HEADERS`.
    Das Sequenzziel gehört bewusst nicht zum Dokument (nicht im Export).

    Attributes:
        document_title: Dokumenttitel (``"Sequenzplan"``), auch PDF-Metadatentitel.
        export_date_text: Formatiertes Exportdatum (``TT.MM.JJJJ``).
        course_line: Kurszeile ``"Fach Lerngruppe Schuljahr Hj. X"``.
        sequence_topic: Thema der Sequenz (Oberthema, Klartext).
        leitkompetenzen: Vorrangig geförderte Kompetenzen.
        rows: Tabellenzeilen (`ExportCell` je Spalte).
    """

    document_title: str
    export_date_text: str
    course_line: str
    sequence_topic: str
    leitkompetenzen: tuple[str, ...]
    rows: tuple[ExportTableRow, ...]


@dataclass(frozen=True)
class ExportTopicUnitsPdfResult:
    """Rückgabe des Use Cases mit Zielpfad, Kurszeile und Sequenz-Metadaten.

    Attributes:
        output_path: Geschriebene Datei.
        title: Kurszeile (für Statusmeldungen der GUI).
        row_count: Anzahl exportierter Einheiten.
        sequence_path: Aktualisierte Sequenzdatei.
        sequenzziel: Sequenzziel (programmintern, nicht im Export).
        leitkompetenzen: Vorrangig geförderte Kompetenzen.
    """

    output_path: Path
    title: str
    row_count: int
    sequence_path: Path
    sequenzziel: str
    leitkompetenzen: tuple[str, ...]


class TopicUnitsPdfRendererPort(Protocol):
    """Port zum Rendern eines fachlich vorbereiteten Sequenz-Exports als PDF."""

    def render(self, document: TopicUnitsPdfDocument, output_path: Path) -> None:
        """Schreibt das PDF-Dokument an den angegebenen Zielpfad."""


class ExportTopicUnitsPdfUseCase:
    """Exportiert die zusammenhängende Sequenz einer ausgewählten Unterrichts- oder LZK-Einheit."""

    def __init__(self, *, renderer: TopicUnitsPdfRendererPort, sequence_export_sync: SyncSequenceExportTableUseCase):
        """Initialisiert den Use Case mit Renderer und Sequenzdatei-Synchronisation.

        Args:
            renderer: Konkreter Renderer (PDF oder Markdown), der das
                vorbereitete Dokument tatsächlich schreibt.
            sequence_export_sync: Use Case, der die persistente Sequenzdatei
                (Export-Tabelle, Sequenzziel/Leitkompetenzen) aktuell hält.
        """
        self._renderer = renderer
        self._sequence_export_sync = sequence_export_sync

    @staticmethod
    def _find_day_by_row_index(day_columns: list[DayColumn], row_index: int) -> DayColumn | None:
        """Sucht die Tages-Spalte mit passendem, stabilem Zeilenindex."""
        for day in day_columns:
            if day.row_index == row_index:
                return day
        return None

    def execute(
        self,
        *,
        table: PlanTableData,
        day_columns: list[DayColumn],
        selected_row_index: int,
        output_path: Path,
        export_date: date,
    ) -> ExportTopicUnitsPdfResult:
        """Exportiert die Sequenz, die die ausgewählte Einheit enthält.

        Args:
            table: Aktuell geladene Planungstabelle.
            day_columns: Vollständige, unprojizierte Tagesliste in
                chronologischer Reihenfolge (`app.raw_day_columns`), damit die
                Sequenz-Erkennung unabhängig von Sichtbarkeits-Einstellungen ist.
            selected_row_index: Stabiler Zeilenindex der ausgewählten Einheit.
            output_path: Zielpfad der PDF-/Markdown-Ausgabedatei.
            export_date: Datum, das als Exportdatum im Dokument erscheint.

        Returns:
            Ergebnis mit Zielpfad, Titel, Zeilenanzahl sowie Pfad und
            aktuellem Sequenzziel/Leitkompetenzen der persistenten Sequenzdatei.

        Raises:
            RuntimeError: Wenn keine gültige Einheit ausgewählt ist, sie nicht
                exportierbar ist, kein Oberthema trägt oder die Sequenz keine
                exportierbaren Zeilen enthält.
        """
        selected_day = self._find_day_by_row_index(day_columns, selected_row_index)
        if selected_day is None:
            raise RuntimeError("Es ist keine gueltige Einheit ausgewaehlt.")

        selected_type = row_lesson_type(selected_day)
        if selected_type not in EXPORTABLE_LESSON_TYPES:
            raise RuntimeError("Der Export ist nur fuer Unterrichts- oder LZK-Einheiten verfuegbar.")

        runs = compute_topic_sequence_runs(day_columns)
        run = find_run_for_row_index(runs, selected_row_index)
        if run is None or not run.oberthema:
            raise RuntimeError("Die ausgewaehlte Einheit hat kein Oberthema.")

        rows = build_export_rows_for_run(day_columns, run)
        if not rows:
            raise RuntimeError("Keine Einheiten fuer das ausgewaehlte Oberthema gefunden.")

        term_token = extract_term_token(table)
        halfyear = term_token[-1]
        schoolyear = schoolyear_from_term(term_token)

        subject = str(table.metadata.get("Kursfach", "")).strip() or "Fach"
        group = strip_wiki_link(str(table.metadata.get("Lerngruppe", ""))).strip() or "Lerngruppe"
        title = f"{subject} {group} {schoolyear} Hj. {halfyear}"

        table_rows = tuple(export_row_cells(row) for row in rows)
        sync_result = self._sequence_export_sync.execute(
            table=table,
            oberthema=run.oberthema,
            headers=EXPORT_TABLE_HEADERS,
            rows=table_rows,
        )

        document = TopicUnitsPdfDocument(
            document_title=SEQUENCE_PLAN_TITLE,
            export_date_text=export_date.strftime("%d.%m.%Y"),
            course_line=title,
            sequence_topic=run.oberthema,
            leitkompetenzen=sync_result.leitkompetenzen,
            rows=table_rows,
        )

        self._renderer.render(document, output_path)
        return ExportTopicUnitsPdfResult(
            output_path=output_path,
            title=title,
            row_count=len(rows),
            sequence_path=sync_result.sequence_path,
            sequenzziel=sync_result.sequenzziel,
            leitkompetenzen=sync_result.leitkompetenzen,
        )
