"""Markdown-Renderer des Sequenzplan-Exports (Aufbau nach der Ref-Vorlage „Sequenzplan“)."""

from __future__ import annotations

from pathlib import Path

from kursplaner.core.usecases.export_topic_units_pdf_usecase import TopicUnitsPdfDocument
from kursplaner.core.usecases.sequence_export_table import EXPORT_TABLE_HEADERS
from kursplaner.infrastructure.export.markdown_text import LINE_BREAK, markdown_inline_text, markdown_table_lines

_NOT_SET = "_(nicht gesetzt)_"


class TopicUnitsMarkdownRenderer:
    """Rendert den Sequenzplan als Markdown: Kopf mit festen Labels, danach die Tabelle.

    Alle Benutzerwerte stehen hinter einem festen Label (nie am Zeilenanfang),
    damit Block-Markdown nicht greifen kann; sie werden über
    `markdown_text.markdown_inline_text` HTML-neutral ausgegeben (Inline-Markdown
    wie Wiki-Links bleibt wirksam). Das tabellenspezifische ``\\|``-Escape wird
    für Metazeilen bewusst **nicht** verwendet, weil es außerhalb einer Tabelle
    als sichtbarer Backslash stehen bliebe.
    """

    def render(self, document: TopicUnitsPdfDocument, output_path: Path) -> None:
        """Schreibt das Markdown-Dokument.

        Args:
            document: Medienneutrale Renderdaten.
            output_path: Zieldatei (Elternordner werden angelegt).
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        focus = LINE_BREAK.join(markdown_inline_text(entry) for entry in document.leitkompetenzen) or _NOT_SET
        topic = markdown_inline_text(document.sequence_topic) or _NOT_SET

        lines = [
            f"# {markdown_inline_text(document.document_title)}",
            "",
            f"Exportdatum: {markdown_inline_text(document.export_date_text)}",
            "",
            f"Kurs: {markdown_inline_text(document.course_line)}",
            "",
            f"**Thema der Sequenz:** {topic}",
            "",
            f"**Vorrangig geförderte Kompetenz(en):** {focus}",
            "",
            *markdown_table_lines(EXPORT_TABLE_HEADERS, document.rows),
        ]
        output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
