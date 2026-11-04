"""``##``-Abschnitte im Body einer Datei mit Frontmatter: lesen und ersetzen, Frontmatter byte-genau.

Verbindet die zwei bestehenden Regeln, ohne eine davon zu duplizieren:
`yaml_registry.split_frontmatter_block` trennt Frontmatter und Body,
`markdown_sections.extract_section`/`replace_section` bestimmen die
Abschnittsgrenzen. So kann eine Überschrift im Frontmatter nie getroffen werden,
und ein Abschnitts-Schreibvorgang rendert das Frontmatter nie neu (wichtig z. B.
für den Marker von Blattwerk-Kurzentwürfen ``.ebw``).

Rein und I/O-frei; den Dateizugriff macht
`infrastructure/repositories/markdown_section_files.py`. Nutzer: Leiter-Ablage
der Sequenzdatei und ``## Ideen`` einer Einheit (§37). Ältere Abschnitts-Schreiber
(Brainstorming der Sequenzdatei, UB-Body, ``## Inhalte``/``## Methodik``) nutzen
diesen Weg noch nicht, siehe DEVELOPMENT_LOG 2026-11-04.
"""

from __future__ import annotations

from collections.abc import Sequence

from kursplaner.core.domain.markdown_sections import extract_section, replace_section
from kursplaner.core.domain.yaml_registry import split_frontmatter_block


def extract_body_section(raw_text: str, heading: str, *, level: int = 2) -> str | None:
    """Inhalt des Abschnitts *heading* (Ebene *level*) im Body, getrimmt; ``None`` ohne Abschnitt.

    Der Abschnitt endet an der nächsten Überschrift derselben Ebene
    (`extract_section(..., stop_at_level=level)`), genau wie beim Ersetzen.
    """
    _head, body = split_frontmatter_block(raw_text)
    return extract_section(body, heading, target_level=level, stop_at_level=level)


def replace_body_section(
    raw_text: str,
    heading: str,
    lines: Sequence[str],
    *,
    level: int = 2,
    insert_before: str | None = None,
) -> str:
    """Ersetzt, legt an oder entfernt (leere *lines*) einen Abschnitt im Body.

    Semantik wie `markdown_sections.replace_section` (neuer Abschnitt vor
    *insert_before*, sonst am Ende); das Frontmatter bleibt wörtlich, ein
    Schluss-Zeilenumbruch des Bodys bleibt erhalten.
    """
    head, body = split_frontmatter_block(raw_text)
    new_body = replace_section(body, heading, list(lines), level=level, insert_before=insert_before)
    if body.endswith("\n") and not new_body.endswith("\n"):
        new_body += "\n"
    return head + new_body
