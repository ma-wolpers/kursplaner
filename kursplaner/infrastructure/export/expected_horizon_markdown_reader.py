"""Liest bestehende Kompetenzhorizont-Markdown-Dateien als Merge-Quelle.

Implementiert `core.ports.expected_horizon.ExistingExpectedHorizonReaderPort`.
Erkennt beide Formate des Markdown-Renderers:

* Legacy/ein Thema: eine einzige Tabelle ohne Überschrift → ``section=None``,
* mehrere Themen: je Thema ``### <Thema>`` gefolgt von einer Tabelle.
"""

from __future__ import annotations

from pathlib import Path

from bw_libs.safe_read import read_text_or_default
from kursplaner.core.domain.expected_horizon_reconciliation import ExistingHorizonRow

SECTION_HEADING_PREFIX = "### "
"""Präfix der Section-Überschriften (vom Markdown-Renderer geschrieben)."""


def split_table_row(line: str) -> list[str]:
    """Zerlegt eine Markdown-Tabellenzeile in getrimmte Zellen (``[]`` für Nicht-Tabellenzeilen)."""
    text = str(line or "").strip()
    if not text.startswith("|"):
        return []
    return [cell.strip() for cell in text.strip("|").split("|")]


def _is_header_row(cells: list[str]) -> bool:
    return len(cells) >= 5 and cells[0] == "Datum" and cells[1].startswith("Die SuS können")


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(set(cell) <= {"-", ":"} and cell for cell in cells)


class ExpectedHorizonMarkdownReader:
    """Dateibasierter Leser für bestehende KH-Markdown-Dateien."""

    def read_existing_rows(self, path: Path) -> list[ExistingHorizonRow]:
        """Liefert alle KH-Tabellenzeilen samt Section (siehe Port-Vertrag).

        Args:
            path: Pfad der bestehenden KH-Markdown-Datei.

        Returns:
            Zeilen in Dateireihenfolge; ``[]`` bei fehlender/unlesbarer Datei.
        """
        if not path.exists() or not path.is_file():
            return []
        text = read_text_or_default(path, default=None)
        if text is None:
            return []

        rows: list[ExistingHorizonRow] = []
        section: str | None = None
        in_table = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(SECTION_HEADING_PREFIX):
                section = stripped[len(SECTION_HEADING_PREFIX) :].strip() or None
                in_table = False
                continue
            cells = split_table_row(stripped)
            if not cells:
                # Leer-/Textzeilen beenden eine Tabelle bewusst nicht (wie bisher):
                # eine versehentliche Leerzeile in der Tabelle soll keine Bewertungen verlieren.
                continue
            if _is_header_row(cells):
                in_table = True
                continue
            if not in_table or _is_separator_row(cells) or len(cells) < 5:
                continue
            rows.append(
                ExistingHorizonRow(
                    section=section,
                    datum=cells[0],
                    ich_kann=cells[1],
                    afb=cells[2],
                    aufg=cells[3],
                    pkte=cells[4],
                )
            )
        return rows
