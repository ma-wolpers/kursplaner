from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors  # type: ignore[import-not-found]
from reportlab.lib.pagesizes import A4, landscape  # type: ignore[import-not-found]
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[import-not-found]
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # type: ignore[import-not-found]

from kursplaner.core.usecases.export_topic_units_pdf_usecase import TopicUnitsPdfDocument


class TopicUnitsPdfRenderer:
    """Rendert den Oberthema-Export als Querformat-PDF mit umbrechender Tabelle."""

    def __init__(self):
        styles = getSampleStyleSheet()
        self._title_style = ParagraphStyle(
            "TopicExportTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            alignment=1,
            spaceAfter=6,
        )
        self._subtitle_style = ParagraphStyle(
            "TopicExportSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            alignment=1,
            spaceAfter=4,
        )
        self._date_style = ParagraphStyle(
            "TopicExportDate",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=14,
            alignment=1,
            spaceAfter=12,
        )
        self._cell_style = ParagraphStyle(
            "TopicExportCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12,
            wordWrap="CJK",
        )
        self._header_style = ParagraphStyle(
            "TopicExportHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
        )

    def _table_rows(self, document: TopicUnitsPdfDocument) -> list[list[Paragraph]]:
        header = [
            Paragraph("Datum", self._header_style),
            Paragraph("Stunden", self._header_style),
            Paragraph("Thema", self._header_style),
            Paragraph("Stundenziel", self._header_style),
            Paragraph("geförderte Prozesskompetenzen", self._header_style),
        ]
        rows: list[list[Paragraph]] = [header]

        for row in document.rows:
            rows.append(
                [
                    Paragraph(str(row.datum or ""), self._cell_style),
                    Paragraph(str(row.stunden or ""), self._cell_style),
                    Paragraph(str(row.thema or ""), self._cell_style),
                    Paragraph(str(row.stundenziel or ""), self._cell_style),
                    Paragraph(str(row.prozesskompetenzen or ""), self._cell_style),
                ]
            )

        return rows

    @staticmethod
    def _column_widths(doc_width: float) -> list[float]:
        # Summe = 1.0
        factors = [0.11, 0.08, 0.18, 0.28, 0.35]
        return [doc_width * factor for factor in factors]

    def render(self, document: TopicUnitsPdfDocument, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        pdf = SimpleDocTemplate(
            str(output_path),
            pagesize=landscape(A4),
            leftMargin=32,
            rightMargin=32,
            topMargin=28,
            bottomMargin=24,
            title=document.title,
            author="kursplaner",
        )

        story = [
            Paragraph(document.title, self._title_style),
            Paragraph(document.subtitle, self._subtitle_style),
            Paragraph(document.export_date_text, self._date_style),
            Spacer(1, 6),
        ]

        table_data = self._table_rows(document)
        table = Table(
            table_data,
            colWidths=self._column_widths(pdf.width),
            repeatRows=1,
            splitByRow=1,
        )
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9EEF5")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (1, 1), (1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        story.append(table)
        pdf.build(story)
