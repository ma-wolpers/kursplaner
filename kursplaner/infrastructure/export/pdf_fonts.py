"""Gemeinsame PDF-Schrift (DejaVu Sans) für alle reportlab-Renderer.

Die reportlab-Standardschrift Helvetica kennt nur WinAnsi: Zeichen wie
``→ ≤ α`` erscheinen dort als Kästchen. Alle PDF-Exporte (Sequenzplan,
Kompetenzhorizont, Achievement-Report) registrieren deshalb über dieses Modul
die im Repo gebündelte DejaVu Sans (Herkunft, Version, Prüfsummen und Lizenz:
``kursplaner/resources/fonts/SOURCE.md``) und verwenden ausschließlich die
hier gelieferten Schriftnamen.

Fehlt eine Schriftdatei, schlägt die Registrierung mit einer klaren
`RuntimeError` fehl — es gibt bewusst keinen stillen Rückfall auf Helvetica,
der Sonderzeichen unbemerkt zerstören würde.

``reportlab`` wird erst in `register_pdf_fonts` importiert, damit dieses Modul
wie die Renderer auch ohne installiertes ``reportlab`` importierbar bleibt
(Verfügbarkeitsprüfung in ``wiring.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

FONTS_DIR = Path(__file__).resolve().parents[2] / "resources" / "fonts"
"""Ablageort der gebündelten Schriftdateien (`kursplaner/resources/fonts`)."""

FONT_FAMILY = "DejaVuSans"

FONT_FILES: dict[str, str] = {
    "DejaVuSans": "DejaVuSans.ttf",
    "DejaVuSans-Bold": "DejaVuSans-Bold.ttf",
    "DejaVuSans-Oblique": "DejaVuSans-Oblique.ttf",
    "DejaVuSans-BoldOblique": "DejaVuSans-BoldOblique.ttf",
}
"""Registrierter reportlab-Schriftname → Dateiname."""


@dataclass(frozen=True)
class PdfFonts:
    """Die von allen Renderern zu verwendenden reportlab-Schriftnamen.

    Attributes:
        regular: Normalschnitt.
        bold: Fettschnitt (auch für ``<b>`` im Paragraph-Markup).
        italic: Kursivschnitt (auch für ``<i>``).
        bold_italic: Fett-kursiv.
    """

    regular: str = "DejaVuSans"
    bold: str = "DejaVuSans-Bold"
    italic: str = "DejaVuSans-Oblique"
    bold_italic: str = "DejaVuSans-BoldOblique"


def register_pdf_fonts(fonts_dir: Path = FONTS_DIR) -> PdfFonts:
    """Registriert DejaVu Sans (alle vier Schnitte) bei reportlab, idempotent.

    Registriert jede Schrift nur einmal pro Prozess und meldet die Familie per
    ``registerFontFamily`` an, damit ``<b>``/``<i>`` in Paragraph-Markup auf
    die DejaVu-Schnitte statt auf Helvetica abgebildet werden.

    Args:
        fonts_dir: Verzeichnis mit den Schriftdateien (für Tests überschreibbar).

    Returns:
        Die zu verwendenden Schriftnamen.

    Raises:
        RuntimeError: Wenn eine der Schriftdateien fehlt.

    Example::

        fonts = register_pdf_fonts()
        ParagraphStyle("X", fontName=fonts.regular)
    """
    missing = [name for name in FONT_FILES.values() if not (fonts_dir / name).is_file()]
    if missing:
        raise RuntimeError(
            f"PDF-Schriftdateien fehlen in {fonts_dir}: {', '.join(missing)}. "
            "Siehe kursplaner/resources/fonts/SOURCE.md zur Wiederherstellung."
        )

    from reportlab.pdfbase import pdfmetrics  # type: ignore[import-not-found]
    from reportlab.pdfbase.ttfonts import TTFont  # type: ignore[import-not-found]

    registered = set(pdfmetrics.getRegisteredFontNames())
    for font_name, file_name in FONT_FILES.items():
        if font_name not in registered:
            pdfmetrics.registerFont(TTFont(font_name, str(fonts_dir / file_name)))

    fonts = PdfFonts()
    pdfmetrics.registerFontFamily(
        FONT_FAMILY,
        normal=fonts.regular,
        bold=fonts.bold,
        italic=fonts.italic,
        boldItalic=fonts.bold_italic,
    )
    return fonts
