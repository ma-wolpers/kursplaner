"""Port für die Umwandlung von Markdown in HTML (von der Infrastruktur implementiert)."""

from __future__ import annotations

from typing import Protocol


class MarkdownHtmlRendererPort(Protocol):
    """Wandelt Markdown-Text in HTML für eine formatierte Leseansicht um.

    Die Implementierung darf fehlen (optionale Bibliothek, Mini-ADR
    `docs/ARCHITEKTUR_KERN.md` §38): dann liefert sie ``None`` und der
    Aufrufer zeigt den Rohtext.
    """

    def to_html(self, markdown_text: str) -> str | None:
        """Liefert das HTML zu ``markdown_text`` oder ``None``, wenn kein Renderer verfügbar ist."""
        ...
