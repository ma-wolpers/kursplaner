"""Darstellung der Sequenzplan-Exporttabelle (Anwendungsschicht).

Bildet die typisierten Fachdaten eines Export-DTOs (`TopicUnitExportRow`) auf
medienneutrale Tabellenzellen (`ExportCell` = Zeilen einer Zelle) ab. Die Regeln
hier sind **Darstellungsregeln dieses einen Exports** — Wochentagskürzel,
``Std.``-Suffix, Zeilenaufteilung, Material-Anzeigenamen —, keine Fachregeln;
deshalb liegt das Modul bei den Use Cases, die die Tabelle zusammenstellen
(`ExportTopicUnitsPdfUseCase`, `SyncTopicSequencePlansUseCase`), und nicht im
Domain-Kern. Jedes Ausgabemedium (Markdown-Tabelle, PDF) verbindet die Zeilen
einer Zelle selbst und escaped medienspezifisch.

`EXPORT_TABLE_HEADERS` ist die **einzige** Quelle der Spaltenüberschriften; sie
sind unveränderlicher Teil des Exportformats und werden deshalb nicht im
Dokument-DTO mitgeführt.
"""

from __future__ import annotations

from kursplaner.core.domain.course_rhythm import weekday_token
from kursplaner.core.domain.topic_sequence_runs import TopicUnitExportRow
from kursplaner.core.domain.wiki_links import wiki_link_display_text
from kursplaner.core.ports.sequence_export import ExportCell, ExportTableRow

EXPORT_TABLE_HEADERS: tuple[str, ...] = (
    "Datum und Stunde",
    "Kompetenzbezug",
    "Stundenthema",
    "Stundenziel",
    "Material",
)
"""Spaltenüberschriften des Sequenzplans (Export und Sequenzdatei-Tabelle)."""


def date_hour_cell(row: TopicUnitExportRow) -> ExportCell:
    """Zelle „Datum und Stunde“: Wochentag + Datum, darunter Startzeit und Stundenzahl.

    Fehlende Bestandteile werden ausgelassen, es gibt keine Platzhalter: Ohne
    parsebares Datum erscheint der rohe Datumswert, ohne Startzeit nur
    ``2 Std.``, ohne Stundenzahl nur die Startzeit; fehlt beides, hat die Zelle
    nur eine Zeile.

    Args:
        row: Export-DTO der Einheit.

    Returns:
        Die Zeilen der Zelle, z. B. ``("Do 07.09.2023", "08:00 · 2 Std.")``.
    """
    if row.datum is not None:
        first = f"{weekday_token(row.datum.weekday())} {row.datum.strftime('%d.%m.%Y')}"
    else:
        first = row.datum_raw
    second_parts = [part for part in (row.startzeit.strip(), f"{row.stunden} Std." if row.stunden > 0 else "") if part]
    lines = [line for line in (first, " · ".join(second_parts)) if line]
    return tuple(lines)


def material_cell(entries: tuple[str, ...]) -> ExportCell:
    """Zelle „Material“: ein Anzeigename pro Zeile (leeres Material → leere Zelle).

    Args:
        entries: Einträge des Listenfelds ``Material``.

    Returns:
        Je Eintrag `wiki_link_display_text` (Alias bzw. Dateiname bei einem
        einzelnen Wiki-Link, sonst unverändert).
    """
    return tuple(wiki_link_display_text(entry) for entry in entries)


def export_row_cells(row: TopicUnitExportRow) -> ExportTableRow:
    """Bildet eine Einheit auf die fünf Zellen des Sequenzplans ab.

    Reihenfolge wie `EXPORT_TABLE_HEADERS`. Gemeinsam genutzt vom manuellen
    Export und vom Sequenzdatei-Sync, damit beide Tabellen identisch sind.
    Kompetenzen und Material stehen je ein Eintrag pro Zeile.

    Args:
        row: Export-DTO der Einheit.

    Returns:
        Die Tabellenzeile.

    Example::

        export_row_cells(row)
        # -> (("Do 07.09.2023", "08:00 · 2 Std."), ("Modellieren",), ("Thema",), ("Ziel",), ("AB 1",))
    """
    return (
        date_hour_cell(row),
        tuple(row.kompetenzen),
        text_cell(row.stundenthema),
        text_cell(row.stundenziel),
        material_cell(row.material),
    )


def text_cell(text: str) -> ExportCell:
    """Zelle aus Freitext: eine Zeile je Textzeile, Leerzeilen entfallen.

    Freitext (Stundenthema/-ziel) darf Zeilenumbrüche enthalten; als eigene
    Zellzeilen kann jedes Medium sie korrekt umbrechen, statt ein rohes ``\\n``
    in eine Markdown-Tabellenzeile zu schreiben.

    Args:
        text: Freitext (darf leer sein).

    Returns:
        Die nicht leeren, getrimmten Zeilen.
    """
    return tuple(line.strip() for line in str(text).splitlines() if line.strip())
