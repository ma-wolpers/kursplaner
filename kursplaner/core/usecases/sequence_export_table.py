"""Darstellung der Sequenzplan-Exporttabelle (Anwendungsschicht).

Bildet die typisierten Fachdaten eines Export-DTOs (`TopicUnitExportRow`) auf
medienneutrale Tabellenzellen (`ExportCell` = Zeilen einer Zelle) ab. Die Regeln
hier sind **Darstellungsregeln dieses einen Exports** — Wochentagskürzel,
``Std.``-Suffix, Zeilenaufteilung, Link-Anzeigenamen —, keine Fachregeln;
deshalb liegt das Modul bei den Use Cases, die die Tabelle zusammenstellen
(`ExportTopicUnitsPdfUseCase`, `SyncTopicSequencePlansUseCase`), und nicht im
Domain-Kern. Jedes Ausgabemedium (Markdown-Tabelle, PDF) verbindet die Zeilen
einer Zelle selbst und escaped medienspezifisch.

`EXPORT_TABLE_HEADERS` ist die **einzige** Quelle der Spaltenüberschriften; sie
sind unveränderlicher Teil des Exportformats und werden deshalb nicht im
Dokument-DTO mitgeführt.

Satzanfänge („Die SuS können …“ vor Stundenzielen, „Die SuS …“ vor
Kompetenzbezug und Leitkompetenzen) gehören nur ins Export-Dokument
(`document_row_cells`, `competency_sentences`), nicht in die Sequenzdatei.
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

GOAL_COLUMN_INDEX = EXPORT_TABLE_HEADERS.index("Stundenziel")
"""Position der Stundenziel-Zelle in einer `ExportTableRow`."""

COMPETENCE_COLUMN_INDEX = EXPORT_TABLE_HEADERS.index("Kompetenzbezug")
"""Position der Kompetenzbezug-Zelle in einer `ExportTableRow`."""

GOAL_SENTENCE_PREFIX = "Die SuS können "
"""Satzanfang vor jedem Stundenziel im Export-Dokument (nicht in der Sequenzdatei)."""

COMPETENCY_SENTENCE_PREFIX = "Die SuS "
"""Satzanfang vor jeder Kompetenz (Kompetenzbezug und Leitkompetenzen) im Export-Dokument."""


def with_sentence_prefix(text: str, prefix: str) -> str:
    """Stellt *prefix* vor einen Satz, sofern er nicht leer ist und noch nicht so beginnt.

    Der Vergleich ignoriert Groß-/Kleinschreibung, damit ein bereits
    ausformuliertes ``"Die SuS können …"`` nicht doppelt beginnt. Ein
    eingebetteter Wiki-Link bleibt unangetastet (Darstellung ist Sache des
    jeweiligen Mediums).

    Args:
        text: Satz (darf leer sein).
        prefix: Satzanfang inkl. abschließendem Leerzeichen.

    Returns:
        Der getrimmte Satz mit Satzanfang bzw. ``""`` bei leerem Text.

    Example::

        with_sentence_prefix("[[Mat-GF-29|führen … durch]]", "Die SuS ")
        # -> "Die SuS [[Mat-GF-29|führen … durch]]"
    """
    stripped = str(text).strip()
    if not stripped or stripped.casefold().startswith(prefix.casefold()):
        return stripped
    return prefix + stripped


def document_row_cells(row: ExportTableRow) -> ExportTableRow:
    """Ergänzt eine Tabellenzeile um die Satzanfänge des Export-Dokuments.

    Jeder Eintrag im Kompetenzbezug wird über `competency_sentences` zum
    Satz („Die SuS …“), die erste Zeile eines nicht leeren Stundenziels erhält
    `GOAL_SENTENCE_PREFIX`; alle übrigen Zellen bleiben unverändert. Die
    Sequenzdatei nutzt weiterhin die unveränderten `export_row_cells`.

    Args:
        row: Zeile aus `export_row_cells`.

    Returns:
        Die Zeile für das Export-Dokument.
    """
    cells = list(row)
    cells[COMPETENCE_COLUMN_INDEX] = competency_sentences(row[COMPETENCE_COLUMN_INDEX])
    goal = row[GOAL_COLUMN_INDEX]
    if goal:
        cells[GOAL_COLUMN_INDEX] = (with_sentence_prefix(goal[0], GOAL_SENTENCE_PREFIX), *goal[1:])
    return tuple(cells)


def competency_sentences(entries: tuple[str, ...]) -> tuple[str, ...]:
    """Formuliert Kompetenzen als Sätze mit `COMPETENCY_SENTENCE_PREFIX`; leere entfallen.

    Einzige Regel für Kompetenzbezug-Zellen und Leitkompetenzen.

    Args:
        entries: Kompetenzen (Zellzeilen oder Leitkompetenzen der Sequenzdatei).

    Returns:
        Je nicht leerem Eintrag ``"Die SuS <Eintrag>"``.
    """
    return tuple(with_sentence_prefix(entry, COMPETENCY_SENTENCE_PREFIX) for entry in entries if str(entry).strip())


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


def entries_cell(entries: tuple[str, ...]) -> ExportCell:
    """Zelle aus Listeneinträgen (Kompetenzen, Material): ein Anzeigename pro Zeile.

    Keine Einträge → leere Zelle.

    Args:
        entries: Einträge eines Listenfelds.

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
        entries_cell(row.kompetenzen),
        text_cell(row.stundenthema),
        text_cell(wiki_link_display_text(row.stundenziel)),
        entries_cell(row.material),
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
