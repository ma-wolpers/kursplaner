"""Reine Markdown-Bullet-Listen-Komposition (Titel + `- item`-Zeilen).

Extrahiert aus der strukturell (nicht wörtlich) duplizierten Sections-Logik
in `plan_table_file_repository.py::set_lesson_markdown_sections` (Wiki-Link-
umschlossene Items, Section nur bei nicht-leerer Liste) und
`ub_repository.py::FileSystemUbRepository._render_list_section` (Klartext-
Items, Platzhalter-Bullet bei leerer Liste, Section immer gerendert). Beide
unterschiedlichen Policies (Link-Wrapping, Leer-Verhalten) bleiben bewusst
Aufrufer-Entscheidung vor dem Aufruf dieser Funktion — nur die gemeinsame
"Titel + Bullets"-Komposition wird hier zentralisiert.
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
    lines = [f"## {title}", ""]
    lines.extend(f"- {item}" for item in items)
    return "\n".join(lines)
