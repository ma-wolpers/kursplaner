"""PDF-Renderer des Sequenzplan-Exports (Aufbau nach der Ref-Vorlage „Sequenzplan“).

Aufbau (Querformat): Exportdatum klein oben links → Titel „Sequenzplan“
zentriert → Kurszeile → Meta-Block (Thema der Sequenz, vorrangig geförderte
Kompetenz(en)) mit grau hinterlegten Labels → Tabelle „Datum und Stunde |
Kompetenzbezug | Stundenthema | Stundenziel | Material“.

Zeilenhöhe und Seitenumbruch (verbindliche Semantik, per Spike mit reportlab
4.4.2 geprüft): jede Datenzeile mindestens `MIN_ROW_HEIGHT` (≈ 2,4 cm, Platz
für Notizen), längere Zeilen wachsen mit dem Inhalt (``minRowHeights``); eine
einzelne Zeile, die nicht mehr auf die Seite passt, wird über Seiten geteilt
(``splitInRow``), der Tabellenkopf wiederholt sich (``repeatRows``).
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from kursplaner.core.ports.sequence_export import ExportCell
from kursplaner.core.usecases.export_topic_units_pdf_usecase import TopicUnitsPdfDocument
from kursplaner.core.usecases.sequence_export_table import EXPORT_TABLE_HEADERS
from kursplaner.infrastructure.export.pdf_fonts import register_pdf_fonts

try:
    from reportlab.lib import colors  # type: ignore[import-not-found]
    from reportlab.lib.pagesizes import A4, landscape  # type: ignore[import-not-found]
    from reportlab.lib.styles import ParagraphStyle  # type: ignore[import-not-found]
    from reportlab.pdfbase.pdfmetrics import stringWidth  # type: ignore[import-not-found]
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

COLUMN_FACTORS: tuple[float, ...] = (0.10, 0.27, 0.21, 0.25, 0.17)
"""Spaltenbreiten als Anteil der Satzbreite (Datum schmal, Rest im Verhältnis der Vorlage).

Die Datumsspalte ist ein Mindestanteil; siehe `TopicUnitsPdfRenderer._column_widths`."""

MIN_ROW_HEIGHT = 68.0
"""Mindesthöhe einer Datenzeile in pt (≈ 2,4 cm wie in der Vorlage)."""

HEADER_BACKGROUND = "#E6E6E6"
"""Grauton für Tabellenkopf und Meta-Labels."""

DATE_COLUMN_BACKGROUND = "#F3F3F3"
"""Hellerer Grauton für die Datumsspalte der Datenzeilen."""

_NOT_SET = "(nicht gesetzt)"
_PADDING = 5


def cell_markup(cell: ExportCell) -> str:
    """Wandelt eine `ExportCell` in reportlab-Paragraph-Markup um.

    Jede Zeile wird **einzeln** XML-escaped (``&``, ``<``, ``>``), erst danach
    werden die Zeilen mit ``<br/>`` verbunden — so wird das absichtlich
    eingefügte ``<br/>`` nie selbst escaped, und ``&``/``<`` in Benutzertext
    brechen den Paragraph-Parser nicht.

    Args:
        cell: Zeilen der Zelle.

    Returns:
        Das Markup (leer bei leerer Zelle).
    """
    return "<br/>".join(escape(line) for line in cell)


class TopicUnitsPdfRenderer:
    """Rendert den Sequenzplan als Querformat-PDF nach der Ref-Vorlage."""

    def __init__(self):
        """Registriert die gebündelte Schrift und baut die Absatzformate."""
        # Unicode-fähige, gebündelte Schrift für alle Texte (siehe pdf_fonts.py).
        self._fonts = register_pdf_fonts()
        regular, bold = self._fonts.regular, self._fonts.bold
        self._date_style = ParagraphStyle("SeqDate", fontName=regular, fontSize=8, leading=10)
        self._title_style = ParagraphStyle(
            "SeqTitle", fontName=regular, fontSize=20, leading=24, alignment=1, spaceAfter=2
        )
        self._course_style = ParagraphStyle(
            "SeqCourse",
            fontName=regular,
            fontSize=10,
            leading=13,
            alignment=1,
            textColor=colors.HexColor("#555555"),
            spaceAfter=8,
        )
        self._meta_label_style = ParagraphStyle("SeqMetaLabel", fontName=bold, fontSize=10, leading=13)
        self._meta_value_style = ParagraphStyle("SeqMetaValue", fontName=regular, fontSize=10, leading=13)
        self._header_style = ParagraphStyle("SeqHeader", fontName=bold, fontSize=10, leading=12, alignment=1)
        self._cell_style = ParagraphStyle("SeqCell", fontName=regular, fontSize=9.5, leading=12)

    def _meta_table(self, document: TopicUnitsPdfDocument, width: float) -> Table:
        """Baut den randlosen Meta-Block mit grau hinterlegten Labels.

        Args:
            document: Renderdaten.
            width: Verfügbare Satzbreite.

        Returns:
            Die zweispaltige Tabelle (Label | Wert).
        """
        topic = escape(document.sequence_topic) or _NOT_SET
        focus = "<br/>".join(escape(entry) for entry in document.leitkompetenzen) or _NOT_SET
        rows = [
            [Paragraph("Thema der Sequenz:", self._meta_label_style), Paragraph(topic, self._meta_value_style)],
            [
                Paragraph("Vorrangig geförderte Kompetenz(en):", self._meta_label_style),
                Paragraph(focus, self._meta_value_style),
            ],
        ]
        label_width = 7.2 * 28.35  # ≈ 7,2 cm
        table = Table(rows, colWidths=[label_width, width - label_width])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), self._fonts.regular),  # Tabellen-Standardschrift, sonst Helvetica
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor(HEADER_BACKGROUND)),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), _PADDING),
                    ("RIGHTPADDING", (0, 0), (-1, -1), _PADDING),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        return table

    def _column_widths(self, width: float) -> list[float]:
        """Spaltenbreiten nach `COLUMN_FACTORS`, Datumsspalte nie schmaler als das Datum.

        Die Datumsspalte ist mindestens ``COLUMN_FACTORS[0]`` breit, wächst aber
        auf die mit der echten Schrift gemessene Breite von ``"Mo 00.00.0000"``
        (plus Innenabstand und Reserve), damit das Datum nie umbricht; die
        übrigen Spalten teilen sich den Rest im festgelegten Verhältnis.

        Args:
            width: Verfügbare Satzbreite.

        Returns:
            Fünf Spaltenbreiten, Summe = `width`.
        """
        measured = stringWidth("Mo 00.00.0000", self._fonts.regular, self._cell_style.fontSize) + 2 * _PADDING + 2
        date_width = max(width * COLUMN_FACTORS[0], measured)
        rest_factors = COLUMN_FACTORS[1:]
        rest_width = width - date_width
        return [date_width, *(rest_width * factor / sum(rest_factors) for factor in rest_factors)]

    def _data_table(self, document: TopicUnitsPdfDocument, width: float) -> Table:
        """Baut die Sequenztabelle mit Mindesthöhe, Zeilensplit und wiederholtem Kopf.

        Args:
            document: Renderdaten.
            width: Verfügbare Satzbreite.

        Returns:
            Die Tabelle.
        """
        data = [[Paragraph(escape(header), self._header_style) for header in EXPORT_TABLE_HEADERS]]
        for row in document.rows:
            data.append([Paragraph(cell_markup(cell), self._cell_style) for cell in row])
        table = Table(
            data,
            colWidths=self._column_widths(width),
            repeatRows=1,
            splitByRow=1,
            splitInRow=1,
            minRowHeights=[0.0] + [MIN_ROW_HEIGHT] * (len(data) - 1),
        )
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), self._fonts.regular),  # Tabellen-Standardschrift, sonst Helvetica
                    ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(HEADER_BACKGROUND)),
                    ("BACKGROUND", (0, 1), (0, -1), colors.HexColor(DATE_COLUMN_BACKGROUND)),
                    ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
                    ("VALIGN", (0, 1), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), _PADDING),
                    ("RIGHTPADDING", (0, 0), (-1, -1), _PADDING),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return table

    def render(self, document: TopicUnitsPdfDocument, output_path: Path) -> None:
        """Schreibt das PDF.

        Args:
            document: Medienneutrale Renderdaten.
            output_path: Zieldatei (Elternordner werden angelegt).
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pdf = SimpleDocTemplate(
            str(output_path),
            initialFontName=self._fonts.regular,  # sonst setzt der Canvas Helvetica als Startschrift
            pagesize=landscape(A4),
            leftMargin=32,
            rightMargin=32,
            topMargin=28,
            bottomMargin=24,
            title=f"{document.document_title} – {document.sequence_topic}",
            author="kursplaner",
        )
        story = [
            Paragraph(escape(document.export_date_text), self._date_style),
            Paragraph(escape(document.document_title), self._title_style),
            Paragraph(escape(document.course_line), self._course_style),
            self._meta_table(document, pdf.width),
            Spacer(1, 8),
            self._data_table(document, pdf.width),
        ]
        pdf.build(story)
