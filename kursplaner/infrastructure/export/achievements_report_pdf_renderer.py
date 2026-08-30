from __future__ import annotations

from pathlib import Path

from kursplaner.core.usecases.export_achievements_report_usecase import AchievementsReportDocument

try:
    from reportlab.lib import colors  # type: ignore[import-not-found]
    from reportlab.lib.pagesizes import A4  # type: ignore[import-not-found]
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[import-not-found]
    from reportlab.platypus import (  # type: ignore[import-not-found]
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
"""`reportlab` ist optional -- fehlt es, bleibt diese Klasse importierbar (fuer
`wiring.py`), darf aber nicht instanziiert werden. Die Verfuegbarkeitspruefung
liegt bei der Composition Root (`wiring.py`), nicht hier."""


class AchievementsReportPdfRenderer:
    """Rendert den Achievement-Fortschritt als PDF: pro Fach eine Ueberschrift + Tabelle."""

    def __init__(self):
        styles = getSampleStyleSheet()
        self._title_style = ParagraphStyle(
            "AchievementsReportTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            alignment=1,
            spaceAfter=6,
        )
        self._date_style = ParagraphStyle(
            "AchievementsReportDate",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=12,
            alignment=1,
            spaceAfter=14,
        )
        self._domain_heading_style = ParagraphStyle(
            "AchievementsReportDomainHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            spaceBefore=10,
            spaceAfter=6,
        )
        self._header_style = ParagraphStyle(
            "AchievementsReportHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
        )
        self._cell_style = ParagraphStyle(
            "AchievementsReportCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
        )

    def _domain_table(self, group) -> Table:
        rows: list[list[Paragraph]] = [
            [
                Paragraph("Achievement", self._header_style),
                Paragraph("Stand", self._header_style),
                Paragraph("Status", self._header_style),
            ]
        ]
        for item in group.items:
            rows.append(
                [
                    Paragraph(str(item.title), self._cell_style),
                    Paragraph(f"{item.current}/{item.target}", self._cell_style),
                    Paragraph("erreicht" if item.is_fulfilled else "offen", self._cell_style),
                ]
            )

        table = Table(rows, colWidths=[280, 80, 80], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9EEF5")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (1, 0), (2, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return table

    def render(self, document: AchievementsReportDocument, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        pdf = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=32,
            bottomMargin=28,
            title=document.title,
            author="kursplaner",
        )

        story = [
            Paragraph(document.title, self._title_style),
            Paragraph(document.export_date_text, self._date_style),
        ]

        for group in document.groups:
            story.append(Paragraph(group.domain, self._domain_heading_style))
            story.append(self._domain_table(group))
            story.append(Spacer(1, 4))

        pdf.build(story)
