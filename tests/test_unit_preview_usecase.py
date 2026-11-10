"""`LoadUnitPreviewUseCase`: Lesevorschau einer Einheitsdatei (synthetische Dateien).

Geprüft: Frontmatter-Felder in Dateireihenfolge ohne leere Felder, Listen als
mehrere Werte, Wiki-Links als sichtbarer Text (Feld und Body), Markdown → HTML
über den echten python-markdown-Adapter, Rohtext-Fallback ohne Renderer,
Lesefehler als `error` statt Exception, Body ohne Frontmatter, `.ebw`.
Echte Dateisystem-Repositories, keine realen Kursdaten.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kursplaner.core.usecases.unit_preview_usecase import UNREADABLE_UNIT_MESSAGE, LoadUnitPreviewUseCase
from kursplaner.infrastructure.rendering import markdown_html_renderer
from kursplaner.infrastructure.rendering.markdown_html_renderer import PythonMarkdownHtmlRenderer
from kursplaner.infrastructure.repositories.lesson_file_repository import FileSystemLessonFileRepository
from kursplaner.infrastructure.repositories.lesson_repository import FileSystemLessonRepository

_UNIT = """---
Stundentyp: Unterricht
Dauer: 2
Stundenthema: Bruchrechnung
Oberthema: "[[Zahlen|Zahlenbereiche]]"
Kompetenzen:
  - Modellieren
  - "[[K-Arg|Argumentieren]]"
Material:
---
# Bruchrechnung

## Inhalte
- **Kürzen** mit [[Kürzen-Regel|Regel]]

| a | b |
|---|---|
| 1 | 2 |
"""


class _NoRenderer:
    def to_html(self, markdown_text: str) -> str | None:
        return None


def _usecase(renderer=None) -> LoadUnitPreviewUseCase:
    return LoadUnitPreviewUseCase(
        lesson_repo=FileSystemLessonRepository(),
        lesson_file_repo=FileSystemLessonFileRepository(),
        markdown_renderer=renderer or PythonMarkdownHtmlRenderer(),
    )


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_fields_keep_file_order_skip_empty_and_unwrap_links(tmp_path):
    preview = _usecase().execute(_write(tmp_path, "Bruch 1.md", _UNIT))
    assert preview.title == "Bruch 1"
    assert preview.error is None
    assert preview.fields == (
        ("Stundentyp", ("Unterricht",)),
        ("Dauer", ("2",)),
        ("Stundenthema", ("Bruchrechnung",)),
        ("Oberthema", ("Zahlenbereiche",)),
        ("Kompetenzen", ("Modellieren", "Argumentieren")),
    )


@pytest.mark.skipif(not markdown_html_renderer.MARKDOWN_AVAILABLE, reason="python-markdown fehlt")
def test_body_becomes_html_with_lists_tables_and_link_labels(tmp_path):
    preview = _usecase().execute(_write(tmp_path, "Bruch.md", _UNIT))
    assert "<h1>Bruchrechnung</h1>" in preview.body_html
    assert "<strong>Kürzen</strong> mit Regel" in preview.body_html
    assert "<table>" in preview.body_html
    assert "[[" not in preview.body_text


def test_without_renderer_body_html_is_none_and_raw_text_remains(tmp_path):
    preview = _usecase(_NoRenderer()).execute(_write(tmp_path, "Bruch.md", _UNIT))
    assert preview.body_html is None
    assert preview.body_text.startswith("# Bruchrechnung")


def test_missing_markdown_library_falls_back_to_none(monkeypatch):
    monkeypatch.setattr(markdown_html_renderer, "MARKDOWN_AVAILABLE", False)
    assert PythonMarkdownHtmlRenderer().to_html("# x") is None


def test_unreadable_file_reports_error_instead_of_raising(tmp_path):
    preview = _usecase().execute(tmp_path / "fehlt.md")
    assert preview.error == UNREADABLE_UNIT_MESSAGE
    assert preview.title == "fehlt"


def test_file_without_frontmatter_still_shows_body(tmp_path):
    preview = _usecase(_NoRenderer()).execute(_write(tmp_path, "Notiz.md", "Nur Text"))
    assert preview.fields == ()
    assert preview.body_text == "Nur Text"


def test_blattwerk_short_draft_is_previewed_like_markdown(tmp_path):
    text = "---\ndocument_type: kursentwurf\nStundentyp: Unterricht\nDauer: 1\nStundenthema: Prozente\n---\n# Ablauf\n"
    preview = _usecase(_NoRenderer()).execute(_write(tmp_path, "Prozente.ebw", text))
    assert ("Stundenthema", ("Prozente",)) in preview.fields
    assert preview.body_text == "# Ablauf"
