"""Use Case: Export einer Themen-Sequenz (Kette benachbarter Einheiten) als PDF/Markdown.

Exportiert ausschließlich die zusammenhängende Kette benachbarter Einheiten, die
zur ausgewählten Einheit gehört (siehe `topic_sequence_runs.compute_topic_sequence_runs`),
nicht mehr jedes Vorkommen desselben Oberthema-Textes im gesamten Kursplan.
Zusätzlich zur Tabelle werden Sequenzziel und Leitkompetenz aus der persistenten
Sequenzdatei geladen (und deren Export-Tabelle beim Export aktualisiert), damit
Renderer sie zwischen Titel/Untertitel und Tabelle anzeigen können.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

from kursplaner.core.domain.export_date_formatting import extract_term_token, schoolyear_from_term
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.topic_sequence_runs import (
    EXPORT_TABLE_HEADERS,
    EXPORTABLE_LESSON_TYPES,
    TopicUnitExportRow,
    build_export_rows_for_run,
    compute_topic_sequence_runs,
    find_run_for_row_index,
    row_lesson_type,
)
from kursplaner.core.domain.wiki_links import strip_wiki_link
from kursplaner.core.usecases.sync_sequence_export_table_usecase import SyncSequenceExportTableUseCase


@dataclass(frozen=True)
class TopicUnitsPdfDocument:
    """Vollstaendige Renderdaten fuer den Sequenz-PDF-Export.

    Attributes:
        title: Kopfzeile (Fach/Lerngruppe/Schuljahr/Halbjahr).
        subtitle: Anzeigename der Sequenz (Oberthema in Anführungszeichen).
        export_date_text: Formatiertes Exportdatum.
        rows: Exportierte Tabellenzeilen der Sequenz.
        sequenzziel: Übergeordnetes Sequenzziel, wird zwischen Titel und Tabelle angezeigt.
        leitkompetenz: Vorderrangig geförderte Kompetenz, ebenfalls zwischen Titel und Tabelle.
    """

    title: str
    subtitle: str
    export_date_text: str
    rows: tuple[TopicUnitExportRow, ...]
    sequenzziel: str
    leitkompetenz: str


@dataclass(frozen=True)
class ExportTopicUnitsPdfResult:
    """Rueckgabe des Use Cases mit Zielpfad, Titel und Sequenz-Metadaten."""

    output_path: Path
    title: str
    row_count: int
    sequence_path: Path
    sequenzziel: str
    leitkompetenz: str


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
                (Export-Tabelle, Sequenzziel/Leitkompetenz) aktuell hält.
        """
        self._renderer = renderer
        self._sequence_export_sync = sequence_export_sync

    @staticmethod
    def _find_day_by_row_index(day_columns: list[dict[str, object]], row_index: int) -> dict[str, object] | None:
        """Sucht die Tages-Spalte mit passendem, stabilem Zeilenindex."""
        for day in day_columns:
            if not isinstance(day, dict):
                continue
            try:
                if int(day.get("row_index", -1)) == row_index:  # type: ignore[arg-type]
                    return day
            except (TypeError, ValueError):
                continue
        return None

    def execute(
        self,
        *,
        table: PlanTableData,
        day_columns: list[dict[str, object]],
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
            aktuellem Sequenzziel/Leitkompetenz der persistenten Sequenzdatei.

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
        subtitle = f'"{run.oberthema}"'

        export_rows = [[row.datum, row.stunden, row.thema, row.stundenziel, row.prozesskompetenzen] for row in rows]
        sync_result = self._sequence_export_sync.execute(
            table=table,
            oberthema=run.oberthema,
            headers=list(EXPORT_TABLE_HEADERS),
            rows=export_rows,
        )

        document = TopicUnitsPdfDocument(
            title=title,
            subtitle=subtitle,
            export_date_text=export_date.strftime("%d.%m.%Y"),
            rows=tuple(rows),
            sequenzziel=sync_result.sequenzziel,
            leitkompetenz=sync_result.leitkompetenz,
        )

        self._renderer.render(document, output_path)
        return ExportTopicUnitsPdfResult(
            output_path=output_path,
            title=title,
            row_count=len(rows),
            sequence_path=sync_result.sequence_path,
            sequenzziel=sync_result.sequenzziel,
            leitkompetenz=sync_result.leitkompetenz,
        )
