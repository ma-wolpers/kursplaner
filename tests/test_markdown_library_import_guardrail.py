"""Guardrail zur Mini-ADR §38: python-markdown wird nur an genau einer Stelle importiert.

Wie PyYAML (§29) ist die Bibliothek optional; nur
`infrastructure/rendering/markdown_html_renderer.py` darf sie importieren,
alle anderen Module gehen über `MarkdownHtmlRendererPort`.
"""

from __future__ import annotations

import re
from pathlib import Path

_PACKAGE = Path(__file__).resolve().parents[1] / "kursplaner"
_IMPORT = re.compile(r"^\s*(import markdown\b|from markdown\b)", re.MULTILINE)
_ALLOWED = "infrastructure/rendering/markdown_html_renderer.py"


def test_markdown_library_is_imported_only_by_its_adapter():
    importers = sorted(
        path.relative_to(_PACKAGE).as_posix()
        for path in _PACKAGE.rglob("*.py")
        if _IMPORT.search(path.read_text(encoding="utf-8"))
    )
    assert importers == [_ALLOWED]
