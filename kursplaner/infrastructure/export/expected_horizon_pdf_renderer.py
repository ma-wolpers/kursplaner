from __future__ import annotations

from pathlib import Path

from reportlab.graphics.shapes import Circle, Drawing, Line  # type: ignore[import-not-found]
from reportlab.lib import colors  # type: ignore[import-not-found]
from reportlab.lib.pagesizes import A4  # type: ignore[import-not-found]
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[import-not-found]
from reportlab.platypus import (  # type: ignore[import-not-found]
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from kursplaner.core.usecases.export_expected_horizon_usecase import ExpectedHorizonDocument


class ExpectedHorizonPdfRenderer:
    """Rendert den Kompetenzhorizont als PDF-Tabelle im Hochformat."""

    _PAGE_WIDTH, _PAGE_HEIGHT = A4
    _TOP_MARGIN = 28
    _BOTTOM_MARGIN = 24
    _INNER_BINDING_MARGIN = 60
    _OUTER_MARGIN = 28

    def __init__(self):
        styles = getSampleStyleSheet()
        self._title_style = ParagraphStyle(
            "ExpectedHorizonTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            alignment=1,
            spaceAfter=6,
        )
        self._subtitle_style = ParagraphStyle(
            "ExpectedHorizonSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            alignment=1,
            spaceAfter=4,
        )
        self._date_style = ParagraphStyle(
            "ExpectedHorizonDate",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=12,
            alignment=1,
            spaceAfter=10,
        )
        self._cell_style = ParagraphStyle(
            "ExpectedHorizonCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12,
            wordWrap="CJK",
        )
        self._cell_bold_style = ParagraphStyle(
            "ExpectedHorizonCellBold",
            parent=self._cell_style,
            fontName="Helvetica-Bold",
        )
        self._header_style = ParagraphStyle(
            "ExpectedHorizonHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            alignment=0,
        )

    @staticmethod
    def _face_symbol(kind: str) -> Drawing:
        drawing = Drawing(16, 16)
        drawing.add(Circle(8, 8, 7, strokeColor=colors.black, fillColor=None, strokeWidth=1))
        drawing.add(Circle(5.5, 10.5, 0.8, strokeColor=colors.black, fillColor=colors.black, strokeWidth=0.6))
        drawing.add(Circle(10.5, 10.5, 0.8, strokeColor=colors.black, fillColor=colors.black, strokeWidth=0.6))

        if kind == "happy":
            drawing.add(Line(4.4, 5.2, 6.5, 3.8, strokeColor=colors.black, strokeWidth=1.1))
            drawing.add(Line(6.5, 3.8, 9.5, 3.6, strokeColor=colors.black, strokeWidth=1.1))
            drawing.add(Line(9.5, 3.6, 11.6, 5.0, strokeColor=colors.black, strokeWidth=1.1))
        elif kind == "neutral":
            drawing.add(Line(4.8, 4.4, 11.2, 4.4, strokeColor=colors.black, strokeWidth=1))
        else:
            drawing.add(Line(4.8, 3.8, 8.0, 5.4, strokeColor=colors.black, strokeWidth=1))
            drawing.add(Line(8.0, 5.4, 11.2, 3.8, strokeColor=colors.black, strokeWidth=1))

        return drawing

    def _table_rows(self, document: ExpectedHorizonDocument) -> list[list[Paragraph]]:
        rows: list[list[Paragraph]] = [
            [
                Paragraph("Datum", self._header_style),
                Paragraph("Ich kann ...", self._header_style),
                self._face_symbol("happy"),
                self._face_symbol("neutral"),
                self._face_symbol("sad"),
            ]
        ]

        for line in document.rows:
            text_style = self._cell_bold_style if line.is_main_goal else self._cell_style
            rows.append(
                [
                    Paragraph(str(line.datum or ""), text_style),
                    Paragraph(str(line.ich_kann or ""), text_style),
                    Paragraph("", self._cell_style),
                    Paragraph("", self._cell_style),
                    Paragraph("", self._cell_style),
                ]
            )

        return rows

    @staticmethod
    def _column_widths(frame_width: float) -> list[float]:
        # Breite Schwerpunktspalte + engere Bewertungs-Spalten.
        factors = [0.10, 0.64, 0.08, 0.08, 0.08]
        return [frame_width * factor for factor in factors]

    @classmethod
    def _odd_frame(cls) -> Frame:
        width = cls._PAGE_WIDTH - cls._INNER_BINDING_MARGIN - cls._OUTER_MARGIN
        height = cls._PAGE_HEIGHT - cls._TOP_MARGIN - cls._BOTTOM_MARGIN
        return Frame(
            cls._INNER_BINDING_MARGIN,
            cls._BOTTOM_MARGIN,
            width,
            height,
            id="odd_frame",
        )

    @classmethod
    def _even_frame(cls) -> Frame:
        width = cls._PAGE_WIDTH - cls._OUTER_MARGIN - cls._INNER_BINDING_MARGIN
        height = cls._PAGE_HEIGHT - cls._TOP_MARGIN - cls._BOTTOM_MARGIN
        return Frame(
            cls._OUTER_MARGIN,
            cls._BOTTOM_MARGIN,
            width,
            height,
            id="even_frame",
        )

    @staticmethod
    def _set_next_template(template_name: str):
        def _callback(canvas, doc):
            del canvas
            doc.handle_nextPageTemplate(template_name)

        return _callback

    def render(self, document: ExpectedHorizonDocument, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        pdf = BaseDocTemplate(
            str(output_path),
            pagesize=A4,
            leftMargin=self._INNER_BINDING_MARGIN,
            rightMargin=self._OUTER_MARGIN,
            topMargin=self._TOP_MARGIN,
            bottomMargin=self._BOTTOM_MARGIN,
            title=document.title,
            author="kursplaner",
        )
        odd_template = PageTemplate(
            id="Odd",
            frames=[self._odd_frame()],
            onPage=self._set_next_template("Even"),
        )
        even_template = PageTemplate(
            id="Even",
            frames=[self._even_frame()],
            onPage=self._set_next_template("Odd"),
        )
        pdf.addPageTemplates([odd_template, even_template])

        story = [
            Paragraph(document.title, self._title_style),
            Paragraph(document.subtitle, self._subtitle_style),
            Spacer(1, 6),
        ]

        table = Table(
            self._table_rows(document),
            colWidths=self._column_widths(self._odd_frame().width),
            repeatRows=1,
            splitByRow=1,
        )
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9EEF5")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (2, 0), (4, -1), "CENTER"),
                    ("ALIGN", (1, 0), (1, -1), "LEFT"),
                    ("VALIGN", (2, 0), (4, 0), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        story.append(table)
        pdf.build(story)
