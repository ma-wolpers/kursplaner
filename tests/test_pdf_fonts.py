"""Tests für die gebündelte PDF-Schrift (Auslieferung, Herkunft, Registrierung)."""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

import pytest

from kursplaner.infrastructure.export.pdf_fonts import FONT_FILES, FONTS_DIR, PdfFonts, register_pdf_fonts

pytest.importorskip("reportlab")


def test_font_files_ship_in_the_package_resources():
    for file_name in FONT_FILES.values():
        assert (FONTS_DIR / file_name).is_file(), file_name
    assert (FONTS_DIR / "LICENSE").is_file()
    assert (FONTS_DIR / "SOURCE.md").is_file()


def test_checksums_match_documented_source():
    """Die gebündelten Dateien sind exakt die in SOURCE.md dokumentierten (reproduzierbare Herkunft)."""
    documented = dict(re.findall(r"\| `([^`]+)` \| `([0-9a-f]{64})` \|", (FONTS_DIR / "SOURCE.md").read_text("utf-8")))
    assert set(documented) == {*FONT_FILES.values(), "LICENSE"}
    for file_name, expected in documented.items():
        actual = hashlib.sha256((FONTS_DIR / file_name).read_bytes()).hexdigest()
        assert actual == expected, file_name


def test_registration_is_idempotent_and_registers_family():
    from reportlab.lib.fonts import tt2ps
    from reportlab.pdfbase import pdfmetrics

    first = register_pdf_fonts()
    second = register_pdf_fonts()

    assert first == second == PdfFonts()
    assert set(FONT_FILES) <= set(pdfmetrics.getRegisteredFontNames())
    assert tt2ps("DejaVuSans", 1, 0) == "DejaVuSans-Bold"
    assert tt2ps("DejaVuSans", 0, 1) == "DejaVuSans-Oblique"


def test_missing_font_file_fails_loudly(tmp_path: Path):
    for file_name in list(FONT_FILES.values())[:-1]:
        shutil.copy(FONTS_DIR / file_name, tmp_path / file_name)

    with pytest.raises(RuntimeError) as info:
        register_pdf_fonts(tmp_path)

    assert list(FONT_FILES.values())[-1] in str(info.value)
