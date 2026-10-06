"""Markdown-Ausgabe von Benutzerinhalten für Sequenzplan-Export und Sequenzdatei.

Darstellungspolitik (für Tabellenzellen und Metawerte gleich):

* Benutzerinhalte werden **HTML-neutral** ausgegeben (``&``, ``<``, ``>`` als
  Entities), damit nichts unbeabsichtigt als HTML interpretiert wird.
* Markdown-**Inline**-Syntax bleibt bewusst wirksam: Ziel ist
  Obsidian-Kompatibilität, Wiki-Links ``[[…]]`` (z. B. in Kompetenzen oder
  Leitkompetenzen) sollen klickbar bleiben. Block-Syntax (``#``, ``>``, ``-``)
  kann nicht greifen, weil kein Benutzerwert am Zeilenanfang steht.
* Backslashes werden verdoppelt, damit ein wörtlicher ``\\`` nie mit dem
  Tabellen-Escape ``\\|`` verschmilzt.

Reihenfolge in Tabellenzellen (verbindlich): pro Zeile ``\\`` → ``\\\\``, dann
``&``/``<``/``>`` → Entities, dann ``|`` → ``\\|`` (tabellenspezifisch); **erst
danach** werden die Zeilen mit ``<br>`` verbunden, damit das absichtlich
erzeugte ``<br>`` nie escaped wird. Ein Wiki-Alias ``[[a|b]]`` wird dabei zu
``[[a\\|b]]`` — der in Obsidian dokumentierten Tabellenform.
"""

from __future__ import annotations

from collections.abc import Sequence

from kursplaner.core.ports.sequence_export import ExportCell, ExportTableRow

LINE_BREAK = "<br>"
"""Zeilenumbruch innerhalb einer Markdown-Tabellenzelle bzw. Metazeile."""


def markdown_inline_text(line: str) -> str:
    """Macht eine einzelne Textzeile HTML-neutral (Inline-Markdown bleibt wirksam).

    Args:
        line: Eine Zeile Benutzertext.

    Returns:
        Der Text mit verdoppelten Backslashes und ``&``/``<``/``>`` als Entities.
        ``|`` bleibt unverändert (außerhalb von Tabellen kein Sonderzeichen).

    Example::

        markdown_inline_text("a < b & [[x|y]]")  # -> "a &lt; b &amp; [[x|y]]"
    """
    text = str(line).replace("\\", "\\\\")
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def markdown_table_cell(cell: ExportCell) -> str:
    """Rendert eine `ExportCell` als Inhalt einer Markdown-Tabellenzelle.

    Args:
        cell: Zeilen der Zelle (Tupel; ein bloßer String wird abgelehnt, weil er
            sonst zeichenweise als Zeilen gelesen würde).

    Returns:
        Der Zellinhalt, Zeilen mit ``<br>`` verbunden.

    Raises:
        TypeError: Wenn `cell` kein Tupel aus Texten ist.

    Example::

        markdown_table_cell(("a|b", "c\\\\d"))  # -> "a\\\\|b<br>c\\\\\\\\d"
    """
    if not isinstance(cell, tuple) or not all(isinstance(line, str) for line in cell):
        raise TypeError(f"Tabellenzelle muss ein Tupel aus Texten sein, nicht {cell!r}")
    escaped = [markdown_inline_text(line).replace("|", "\\|") for line in cell]
    return LINE_BREAK.join(escaped)


def markdown_table_lines(headers: Sequence[str], rows: Sequence[ExportTableRow]) -> list[str]:
    """Rendert Kopf, Trennzeile und Zeilen einer Markdown-Tabelle.

    Args:
        headers: Spaltenüberschriften (Klartext).
        rows: Tabellenzeilen, je eine `ExportCell` pro Spalte.

    Returns:
        Die Tabellenzeilen ohne Zeilenende.
    """
    header_cells = [markdown_table_cell((str(header),)) for header in headers]
    lines = [
        "| " + " | ".join(header_cells) + " |",
        "| " + " | ".join(["---"] * len(header_cells)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(markdown_table_cell(cell) for cell in row) + " |")
    return lines
