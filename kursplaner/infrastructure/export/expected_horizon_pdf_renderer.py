from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from kursplaner.core.domain.expected_horizon_pdf_layout import ExpectedHorizonPdfLayout
from kursplaner.core.domain.expected_horizon_reconciliation import ReconciledHorizon
from kursplaner.core.usecases.export_expected_horizon_usecase import ExpectedHorizonDocument, GoalKind
from kursplaner.infrastructure.export.pdf_face_symbols import face_symbol
from kursplaner.infrastructure.export.pdf_fonts import register_pdf_fonts

try:
    from reportlab.lib import colors  # type: ignore[import-not-found]
    from reportlab.lib.pagesizes import A4  # type: ignore[import-not-found]
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[import-not-found]
    from reportlab.pdfbase.pdfmetrics import stringWidth  # type: ignore[import-not-found]
    from reportlab.platypus import (  # type: ignore[import-not-found]
        BaseDocTemplate,
        Frame,
        PageTemplate,
        Paragraph,
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


class ExpectedHorizonPdfRenderer:
    """Rendert den Kompetenzhorizont als PDF-Tabelle im Hochformat."""

    _TOP_MARGIN = 28
    _BOTTOM_MARGIN = 24
    _INNER_BINDING_MARGIN = 60
    _OUTER_MARGIN = 28

    def __init__(self):
        # `A4` erst hier (statt als Klassenattribut) aufloesen, damit die Klasse
        # auch importierbar bleibt, wenn `reportlab` fehlt -- nur die Instanziierung
        # soll dann fehlschlagen, nicht schon der Modul-Import.
        self._PAGE_WIDTH, self._PAGE_HEIGHT = A4
        # Unicode-fähige, gebündelte Schrift für alle Texte (siehe pdf_fonts.py).
        self._fonts = register_pdf_fonts()
        styles = getSampleStyleSheet()
        self._title_style = ParagraphStyle(
            "ExpectedHorizonTitle",
            parent=styles["Heading1"],
            fontName=self._fonts.bold,
            fontSize=20,
            leading=24,
            alignment=1,
            spaceAfter=6,
        )
        self._subtitle_style = ParagraphStyle(
            "ExpectedHorizonSubtitle",
            parent=styles["Normal"],
            fontName=self._fonts.bold,
            fontSize=13,
            leading=16,
            alignment=1,
            spaceAfter=4,
        )
        self._date_style = ParagraphStyle(
            "ExpectedHorizonDate",
            parent=styles["Normal"],
            fontName=self._fonts.regular,
            fontSize=10,
            leading=12,
            alignment=1,
            spaceAfter=10,
        )
        self._base_styles = styles
        self._apply_layout(ExpectedHorizonPdfLayout())

    def _apply_layout(self, layout: ExpectedHorizonPdfLayout) -> None:
        """Setzt Layout und Tabellen-Stile passend zur gewählten Schriftgröße.

        Zellen nutzen ``layout.font_size``; Zeilenabstand, Kopf- und
        Abschnittszeilen skalieren proportional (Faktor 1.0 = bisheriges Layout).

        Args:
            layout: Darstellungsoptionen dieses Renderlaufs.
        """
        self._layout = layout
        scale = layout.scale
        normal = self._base_styles["Normal"]
        self._cell_style = ParagraphStyle(
            "ExpectedHorizonCell",
            parent=normal,
            fontName=self._fonts.regular,
            fontSize=layout.font_size,
            leading=12 * scale,
            wordWrap="CJK",
        )
        self._cell_bold_style = ParagraphStyle(
            "ExpectedHorizonCellBold", parent=self._cell_style, fontName=self._fonts.bold
        )
        self._cell_italic_style = ParagraphStyle(
            "ExpectedHorizonCellItalic", parent=self._cell_style, fontName=self._fonts.italic
        )
        self._section_style = ParagraphStyle(
            "ExpectedHorizonSection",
            parent=normal,
            fontName=self._fonts.bold,
            fontSize=10.5 * scale,
            leading=13 * scale,
        )
        self._header_style = ParagraphStyle(
            "ExpectedHorizonHeader", parent=normal, fontName=self._fonts.bold, fontSize=10 * scale, leading=12 * scale
        )

    def _table_rows(self, document: ExpectedHorizonDocument) -> list[list[Paragraph]]:
        """Baut Kopfzeile, ggf. Abschnittsüberschriften und Zielzeilen der Tabelle.

        Mit ``with_task_column`` erhält jede Zeile ganz rechts eine leere
        „Aufgaben“-Zelle zum handschriftlichen Ausfüllen.
        """
        task_column = self._layout.with_task_column
        header = [
            Paragraph("Datum", self._header_style),
            Paragraph("Ich kann ...", self._header_style),
            face_symbol("happy"),
            face_symbol("neutral"),
            face_symbol("sad"),
        ]
        if task_column:
            header.append(Paragraph("Aufgaben", self._header_style))
        rows: list[list[Paragraph]] = [header]
        empty_tail = [Paragraph("", self._cell_style) for _ in range(4 if task_column else 3)]

        with_headings = len(document.sections) > 1
        for section in document.sections:
            if with_headings:
                rows.append([Paragraph(escape(section.oberthema), self._section_style)] + [""] * (len(header) - 1))
            for line in section.rows:
                if line.kind == GoalKind.STUNDENZIEL:
                    text_style = self._cell_bold_style
                elif line.kind == GoalKind.SONDERZIEL:
                    text_style = self._cell_italic_style
                else:
                    text_style = self._cell_style
                rows.append(
                    [
                        Paragraph(str(line.datum or ""), text_style),
                        Paragraph(str(line.ich_kann or ""), text_style),
                        *empty_tail,
                    ]
                )

        return rows

    @staticmethod
    def _section_heading_rows(document: ExpectedHorizonDocument) -> list[int]:
        """Tabellenzeilen-Indizes der Section-Überschriften (nur bei mehreren Sections)."""
        if len(document.sections) <= 1:
            return []
        indices: list[int] = []
        row_index = 1  # Zeile 0 ist der Tabellenkopf
        for section in document.sections:
            indices.append(row_index)
            row_index += 1 + len(section.rows)
        return indices

    def _column_widths(self, frame_width: float) -> list[float]:
        """Spaltenbreiten: Datum, breite „Ich kann“-Spalte, drei Smiley-Spalten, ggf. „Aufgaben“.

        Die Datumsspalte wächst mit der Schriftgröße, damit ``TT.MM.JJ`` nicht
        umbricht: Die Breite wird mit der tatsächlich verwendeten Schrift
        gemessen (fetter Schnitt, breiteste Ziffern ``00.00.00``) plus
        Innenabstand und kleiner Reserve — ein fester em-Faktor war auf
        Helvetica geeicht und brach mit der breiteren DejaVu Sans das Datum um.
        Die „Ich kann“-Spalte nimmt den Rest.
        """
        measured = stringWidth("00.00.00", self._fonts.bold, self._layout.font_size)
        date_width = max(frame_width * 0.10, measured + 12 + 2)
        if self._layout.with_task_column:
            tail = [frame_width * 0.07] * 3 + [frame_width * 0.20]
        else:
            tail = [frame_width * 0.08] * 3
        return [date_width, frame_width - date_width - sum(tail), *tail]

    def _odd_frame(self) -> Frame:
        width = self._PAGE_WIDTH - self._INNER_BINDING_MARGIN - self._OUTER_MARGIN
        height = self._PAGE_HEIGHT - self._TOP_MARGIN - self._BOTTOM_MARGIN
        return Frame(
            self._INNER_BINDING_MARGIN,
            self._BOTTOM_MARGIN,
            width,
            height,
            id="odd_frame",
        )

    def _even_frame(self) -> Frame:
        width = self._PAGE_WIDTH - self._OUTER_MARGIN - self._INNER_BINDING_MARGIN
        height = self._PAGE_HEIGHT - self._TOP_MARGIN - self._BOTTOM_MARGIN
        return Frame(
            self._OUTER_MARGIN,
            self._BOTTOM_MARGIN,
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

    def render(
        self,
        document: ExpectedHorizonDocument,
        output_path: Path,
        *,
        reconciled: ReconciledHorizon | None = None,
        layout: ExpectedHorizonPdfLayout | None = None,
    ) -> None:
        """Schreibt den Kompetenzhorizont als PDF.

        ``reconciled`` wird bewusst ignoriert: Das PDF hat keine
        Bewertungsspalten und zeigt immer den frischen Stand ohne entfallene Ziele.

        Args:
            document: Render-DTO mit Sections.
            output_path: Zielpfad.
            reconciled: Ignoriert (siehe oben).
            layout: Aufgaben-Spalte und Schriftgröße; ``None`` = Standardlayout.
        """
        del reconciled
        self._apply_layout(layout or ExpectedHorizonPdfLayout())
        output_path.parent.mkdir(parents=True, exist_ok=True)

        pdf = BaseDocTemplate(
            str(output_path),
            initialFontName=self._fonts.regular,  # sonst setzt der Canvas Helvetica als Startschrift
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
        heading_styles = []
        for row_index in self._section_heading_rows(document):
            heading_styles.extend(
                [
                    ("SPAN", (0, row_index), (-1, row_index)),
                    ("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#F3F5F8")),
                ]
            )
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), self._fonts.regular),  # Tabellen-Standardschrift, sonst Helvetica
                    *heading_styles,
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
