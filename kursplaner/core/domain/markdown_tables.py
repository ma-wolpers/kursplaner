"""Markdown-Tabellensyntax: einzige Stelle für Zeilen, Zellen, Trennzeile, Maskierung und Blöcke.

Genutzt von Kurstabelle (`plan_table_markdown_io`), Sequenzdatei
(`sequence_plan_repository`), Sequenz-Export (`markdown_text`) und
Kompetenzhorizont (`expected_horizon_markdown_reader`/`_renderer`), damit Lesen
und Schreiben überall zueinander passen.

**Maskierung (Obsidian/GFM):** In einer Zelle steht ein wörtliches ``|`` als
``\\|`` (so verlangt Obsidian z. B. Alias-Links ``[[a\\|b]]`` in Tabellen).
`escape_table_cell` und `split_table_row` sind zueinander invers. Andere
Backslashes bleiben unverändert – von Hand getippte Markdown-Escapes (``\\_``)
werden nie umgeschrieben; beim Zerlegen bindet ein ``\\`` das Folgezeichen,
damit ``\\\\|`` (Backslash, dann Zellgrenze) richtig getrennt wird.
"""

from __future__ import annotations

import re

_SEPARATOR_CELL_RE = re.compile(r":?-+:?")


def escape_table_cell(text: str) -> str:
    """Maskiert ``|`` für eine Tabellenzelle (Gegenstück zu `split_table_row`)."""
    return str(text).replace("|", "\\|")


def is_table_row(line: str) -> bool:
    """``True`` für eine Zeile, die mit ``|`` beginnt und mindestens eine weitere ``|`` enthält."""
    stripped = str(line).strip()
    return stripped.startswith("|") and "|" in stripped[1:]


def split_table_row(line: str) -> list[str]:
    """Zellen einer Tabellenzeile, getrimmt und entmaskiert; ``[]`` für Nicht-Tabellenzeilen.

    Getrennt wird nur an unmaskierten ``|``; die äußeren Begrenzer fallen weg.

    Example::

        split_table_row("| [[a\\\\|b]] | x |")  # -> ["[[a|b]]", "x"]
    """
    text = str(line).strip()
    if not text.startswith("|"):
        return []
    cells: list[str] = []
    current: list[str] = []
    index, closed = 1, False
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            following = text[index + 1]
            current.append("|" if following == "|" else char + following)
            index += 2
            closed = False
            continue
        if char == "|":
            cells.append("".join(current).strip())
            current, closed = [], True
        else:
            current.append(char)
            closed = False
        index += 1
    if not closed:
        cells.append("".join(current).strip())
    return cells


def is_separator_cells(cells: list[str]) -> bool:
    """``True``, wenn alle Zellen Trennzellen sind (``---``, ``:--``, ``--:``, ``:-:``)."""
    return bool(cells) and all(_SEPARATOR_CELL_RE.fullmatch(cell) for cell in cells)


def is_separator_row(line: str) -> bool:
    """``True`` für die Trennzeile unter der Kopfzeile einer Tabelle."""
    return is_separator_cells(split_table_row(line))


def table_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """``(erste, letzte)`` Zeilenindizes jeder Folge von mindestens zwei Tabellenzeilen.

    Ob die zweite Zeile eine Trennzeile ist, prüft der Aufrufer (`is_separator_row`),
    weil eine Kurstabelle ohne Trennzeile als Fehler gemeldet, nicht übersprungen wird.
    """
    blocks: list[tuple[int, int]] = []
    start: int | None = None
    for index, line in enumerate([*lines, ""]):
        if is_table_row(line):
            if start is None:
                start = index
            continue
        if start is not None and index - start >= 2:
            blocks.append((start, index - 1))
        start = None
    return blocks
