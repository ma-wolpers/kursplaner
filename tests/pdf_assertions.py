"""Gemeinsame, verbindliche PDF-Prüfungen für alle Renderer-Tests (pypdf).

Jeder PDF-Renderer-Test prüft damit dieselben objektiven Mindestkriterien:
gültiges, lesbares PDF, erwartete Seitenzahl, extrahierbarer Text inklusive
Unicode-Zeichen und Sentinel-Tokens (= nichts abgeschnitten), eingebettete
DejaVu-Schrift und keine Helvetica. ``Times-Roman`` darf als bloße
Ressource vorkommen: reportlab-``Drawing``s (z. B. Smiley-Symbole) setzen sie
intern, ohne Text damit zu zeichnen.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from pypdf import PdfReader

UNICODE_PROBE = "ä ö ü ß → ≤ α"
"""Zeichen, die mit Helvetica (WinAnsi) nicht darstellbar wären bzw. Umlaute."""


def pdf_font_names(reader: PdfReader) -> set[str]:
    """Sammelt alle ``/BaseFont``-Namen aus den Seitenressourcen.

    Args:
        reader: Geöffnetes PDF.

    Returns:
        Die Schriftnamen (inkl. Subset-Präfix wie ``AAAAAA+DejaVuSans``).
    """
    names: set[str] = set()
    for page in reader.pages:
        resources = page.get("/Resources") or {}
        fonts = resources.get("/Font") or {}
        for font in fonts.values():
            names.add(str(font.get_object().get("/BaseFont")))
    return names


def assert_valid_pdf(
    path: Path,
    *,
    pages: int | None = None,
    min_pages: int | None = None,
    contains: Iterable[str] = (),
    on_every_page: Iterable[str] = (),
) -> PdfReader:
    """Prüft die verbindlichen Mindestkriterien eines gerenderten PDFs.

    Args:
        path: Gerenderte Datei.
        pages: Exakt erwartete Seitenzahl (optional).
        min_pages: Mindestseitenzahl (optional).
        contains: Texte, die irgendwo im extrahierten Text vorkommen müssen
            (Sentinels, Unicode-Probe, …).
        on_every_page: Texte, die auf **jeder** Seite vorkommen müssen (z. B.
            ein wiederholter Tabellenkopf).

    Returns:
        Der geöffnete `PdfReader` für weitere Prüfungen.
    """
    assert path.read_bytes().startswith(b"%PDF"), "keine PDF-Datei"
    reader = PdfReader(str(path))
    count = len(reader.pages)
    if pages is not None:
        assert count == pages, f"Seitenzahl {count} != {pages}"
    if min_pages is not None:
        assert count >= min_pages, f"Seitenzahl {count} < {min_pages}"

    page_texts = [page.extract_text() or "" for page in reader.pages]
    full_text = "\n".join(page_texts)
    assert full_text.strip(), "kein extrahierbarer Text"
    for token in contains:
        assert token in full_text, f"{token!r} fehlt im PDF-Text"
    for token in on_every_page:
        for number, text in enumerate(page_texts, start=1):
            assert token in text, f"{token!r} fehlt auf Seite {number}"

    fonts = pdf_font_names(reader)
    assert any("DejaVuSans" in name for name in fonts), f"DejaVu nicht eingebettet: {fonts}"
    assert not any("Helvetica" in name for name in fonts), f"Helvetica verwendet: {fonts}"
    return reader
