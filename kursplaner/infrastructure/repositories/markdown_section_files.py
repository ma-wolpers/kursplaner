"""Dateizugriff für ``##``-Body-Abschnitte (Regeln in `domain/markdown_body_sections`).

Liest frisch von der Platte und schreibt nur, wenn sich der Dateitext ändert
(atomar). Jedes Repository, das einen Body-Abschnitt liest oder ersetzt, nutzt
diese zwei Funktionen statt eigener Lese-/Ersetzungslogik.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from bw_libs.app_paths import atomic_write_text
from kursplaner.core.domain.markdown_body_sections import extract_body_section, replace_body_section


def read_body_section(path: Path, heading: str, *, level: int = 2) -> str | None:
    """Getrimmter Abschnittsinhalt im Body von *path*; ``None`` ohne Abschnitt."""
    return extract_body_section(path.read_text(encoding="utf-8"), heading, level=level)


def write_body_section(
    path: Path,
    heading: str,
    lines: Sequence[str],
    *,
    level: int = 2,
    insert_before: str | None = None,
) -> bool:
    """Ersetzt/legt an/entfernt einen Body-Abschnitt in *path*; ``True``, wenn geschrieben wurde."""
    original = path.read_text(encoding="utf-8")
    updated = replace_body_section(original, heading, lines, level=level, insert_before=insert_before)
    if updated == original:
        return False
    atomic_write_text(path, updated, encoding="utf-8")
    return True
