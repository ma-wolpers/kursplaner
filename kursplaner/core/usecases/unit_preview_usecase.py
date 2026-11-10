"""Lädt eine Einheitsdatei als Lesevorschau (Frontmatter-Felder + Markdown-Body).

Nur lesend, für die Einheitsvorschau im Kursgitter (Strg+D). Das Frontmatter
kommt ungekürzt und unkanonisiert über `LessonRepository.load_raw_lesson_frontmatter`
(Plattenwert, Dateireihenfolge), der Body über `body_after_frontmatter`.
Wiki-Links erscheinen als ihr sichtbarer Text (`unwrap_wiki_links`). Ein
Lesefehler wirft nicht, sondern landet in `UnitPreview.error`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.wiki_links import unwrap_wiki_links
from kursplaner.core.domain.yaml_registry import RawYamlBlock, body_after_frontmatter
from kursplaner.core.ports.markdown_html import MarkdownHtmlRendererPort
from kursplaner.core.ports.repositories import LessonFileRepository, LessonRepository

UNREADABLE_UNIT_MESSAGE = "Einheitsdokument konnte nicht gelesen werden (Datei fehlt, verschoben oder gesperrt)."


@dataclass(frozen=True)
class UnitPreview:
    """Anzeigefertige Vorschau einer Einheit.

    Attributes:
        title: Dateiname ohne Endung.
        fields: Nicht-leere Frontmatter-Felder in Dateireihenfolge, je Feld die
            Anzeigewerte (Skalar = ein Wert, Liste = mehrere).
        body_html: Der Body als HTML; ``None`` ohne Markdown-Renderer (dann
            `body_text` als Rohtext zeigen).
        body_text: Der Body mit entpackten Wiki-Links (Rohtext-Fallback).
        error: Fehlermeldung, wenn die Datei nicht lesbar war (sonst ``None``).
    """

    title: str
    fields: tuple[tuple[str, tuple[str, ...]], ...] = ()
    body_html: str | None = None
    body_text: str = ""
    error: str | None = None


def _display_values(value: object) -> tuple[str, ...]:
    """Anzeigewerte eines rohen Frontmatter-Werts; leere Einträge entfallen."""
    if isinstance(value, RawYamlBlock):
        raw_items: list[object] = ["\n".join(line.strip() for line in value.lines).strip()]
    elif isinstance(value, (list, tuple)):
        raw_items = list(value)
    elif value is None:
        raw_items = []
    else:
        raw_items = [value]
    shown = (unwrap_wiki_links(str(item)).strip() for item in raw_items)
    return tuple(text for text in shown if text)


class LoadUnitPreviewUseCase:
    """Baut die `UnitPreview` einer Einheitsdatei (`.md` oder Blattwerk-`.ebw`)."""

    def __init__(
        self,
        *,
        lesson_repo: LessonRepository,
        lesson_file_repo: LessonFileRepository,
        markdown_renderer: MarkdownHtmlRendererPort,
    ) -> None:
        """Initialisiert den Use Case mit Lese-Ports und Markdown-Renderer."""
        self.lesson_repo = lesson_repo
        self.lesson_file_repo = lesson_file_repo
        self.markdown_renderer = markdown_renderer

    def execute(self, path: Path) -> UnitPreview:
        """Liest die Datei frisch von der Platte und bereitet sie zur Anzeige auf.

        Args:
            path: Pfad der verknüpften Einheitsdatei (`DayColumn.link`).
        """
        try:
            raw_text = self.lesson_file_repo.read_file_content(path)
        except (OSError, UnicodeDecodeError):
            return UnitPreview(title=path.stem, error=UNREADABLE_UNIT_MESSAGE)
        body_text = unwrap_wiki_links(body_after_frontmatter(raw_text)).strip()
        return UnitPreview(
            title=path.stem,
            fields=self._fields(path),
            body_html=self.markdown_renderer.to_html(body_text) if body_text else "",
            body_text=body_text,
        )

    def _fields(self, path: Path) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Nicht-leere Frontmatter-Felder; fehlendes/ungültiges Frontmatter zeigt einfach keine Felder.

        `parse_yaml_frontmatter` meldet Formfehler als ``RuntimeError`` – für
        eine reine Leseansicht kein Grund, den Body nicht zu zeigen.
        """
        try:
            raw = self.lesson_repo.load_raw_lesson_frontmatter(path)
        except (OSError, RuntimeError, UnicodeDecodeError):
            return ()
        fields = ((str(key), _display_values(value)) for key, value in raw.items())
        return tuple((key, values) for key, values in fields if values)
