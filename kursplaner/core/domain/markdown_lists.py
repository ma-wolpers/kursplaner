"""Reine Markdown-Bullet-Listen-Komposition (Titel + `- item`-Zeilen).

Einzige Stelle der ``- item``-Darstellung. Nutzer: ``## Inhalte``/``## Methodik``
einer Einheit (`LessonCommandsUseCase`, Wiki-Link-umschlossene Items) und der
UB-Body (`ub_markdown_sections`, Klartext-Items, Platzhalter-Bullet bei leerer
Liste). Link-Wrapping und Leer-Verhalten bleiben Aufrufer-Entscheidung.
"""

from __future__ import annotations


def render_markdown_bullet_section(title: str, items: list[str]) -> str:
    """Rendert `## <title>` gefolgt von `- <item>`-Zeilen je Element in `items`.

    Args:
        title: Section-Überschrift ohne `##`-Präfix.
        items: Bereits fertig formatierte Bullet-Inhalte (Link-Wrapping o. ä.
            liegt beim Aufrufer). Leere Liste rendert nur die Überschrift ohne
            Bullets — Platzhalter-/Weglass-Verhalten bei Leerheit ist
            Aufrufer-Entscheidung (siehe Modul-Docstring).

    Returns:
        Section-Text ohne abschließenden Zeilenumbruch.

    Example::

        render_markdown_bullet_section("Inhalte", ["[[a]]", "[[b]]"])
        # -> "## Inhalte\\n\\n- [[a]]\\n- [[b]]"
    """
    return "\n".join([f"## {title}", "", *markdown_bullet_lines(items)])


def markdown_bullet_lines(items: list[str]) -> list[str]:
    """Die ``- <item>``-Zeilen einer Aufzählung (einzige Stelle dieser Darstellung).

    Für Aufrufer, die einen Abschnitt über `markdown_sections.replace_section`
    ersetzen und dafür nur die Inhaltszeilen brauchen.
    """
    return [f"- {item}" for item in items]
