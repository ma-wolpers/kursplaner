"""Markdown → HTML mit python-markdown (einzige Importstelle, Mini-ADR §38).

Die Bibliothek ist optional (wie PyYAML/reportlab): fehlt sie, ist
`MARKDOWN_AVAILABLE` falsch und `to_html` liefert ``None`` – die
Einheitsvorschau zeigt dann den Rohtext statt abzustürzen.
"""

from __future__ import annotations

try:
    import markdown  # type: ignore[import-untyped]

    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

MARKDOWN_EXTENSIONS = ("fenced_code", "tables", "sane_lists")
"""Dieselben Standard-Erweiterungen wie Blattwerks Hilfe-Doku: Codeblöcke, Tabellen, robuste Listen."""


class PythonMarkdownHtmlRenderer:
    """`MarkdownHtmlRendererPort` auf Basis von python-markdown."""

    def to_html(self, markdown_text: str) -> str | None:
        """Liefert das HTML zu ``markdown_text`` oder ``None`` ohne installierte Bibliothek."""
        if not MARKDOWN_AVAILABLE:
            return None
        return markdown.markdown(markdown_text, extensions=list(MARKDOWN_EXTENSIONS))
