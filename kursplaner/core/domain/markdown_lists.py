"""Reine Markdown-Bullet-Listen-Komposition (``- item``-Zeilen).

Einzige Stelle der ``- item``-Darstellung. Nutzer: ``## Inhalte``/``## Methodik``
einer Einheit (`LessonCommandsUseCase`, Wiki-Link-umschlossene Items).
Link-Wrapping und Leer-Verhalten bleiben Aufrufer-Entscheidung.
"""

from __future__ import annotations


def markdown_bullet_lines(items: list[str]) -> list[str]:
    """Die ``- <item>``-Zeilen einer Aufzählung (einzige Stelle dieser Darstellung).

    Für Aufrufer, die einen Abschnitt über `markdown_sections.replace_section`
    ersetzen und dafür nur die Inhaltszeilen brauchen.
    """
    return [f"- {item}" for item in items]
