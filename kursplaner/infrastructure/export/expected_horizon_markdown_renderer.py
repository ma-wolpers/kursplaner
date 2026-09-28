"""Rendert den Kompetenzhorizont als Markdown-Tabelle(n).

Formatiert nur noch: Der Abgleich mit einer bestehenden Datei (übernommene
AFB/Aufg/Pkte, durchgestrichene entfallene Ziele) ist fachliche Logik in
`core.domain.expected_horizon_reconciliation` und kommt als ``reconciled``
herein. Das Einlesen bestehender Dateien übernimmt
`expected_horizon_markdown_reader`.

Layout:

* **eine Section** → genau das bisherige Format (eine Tabelle ohne Überschrift),
* **mehrere Sections** → je Section ``### <Thema>`` gefolgt von einer Tabelle.
"""

from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.expected_horizon_reconciliation import (
    ReconciledHorizon,
    ReconciledRow,
    ReconciledSection,
    reconcile,
)
from kursplaner.core.usecases.export_expected_horizon_usecase import ExpectedHorizonDocument, GoalKind
from kursplaner.infrastructure.export.expected_horizon_markdown_reader import SECTION_HEADING_PREFIX


class ExpectedHorizonMarkdownRenderer:
    """Rendert den Kompetenzhorizont als Markdown-Tabelle(n)."""

    _COLUMN_HEADER = "| Datum | Die SuS können ... | AFB | Aufg | Pkte |"
    _SEPARATOR = "| --- | --- | --- | --- | --- |"

    @staticmethod
    def _escape_cell(value: str) -> str:
        return str(value or "").replace("|", "\\|").replace("\n", " ").strip()

    @staticmethod
    def _wrap(value: str, marker: str) -> str:
        text = str(value or "").strip()
        return f"{marker}{text}{marker}" if text else ""

    def _render_row(self, row: ReconciledRow) -> str:
        """Formatiert eine abgeglichene Zeile (Stundenziel fett, Sonderziel kursiv, entfallen durchgestrichen)."""
        if row.removed:
            datum = self._escape_cell(row.datum)
            ich_kann = self._escape_cell(self._wrap(row.ich_kann, "~~"))
        else:
            datum = self._escape_cell(row.datum)
            ich_kann = self._escape_cell(row.ich_kann)
            if row.kind == GoalKind.STUNDENZIEL:
                datum = self._wrap(datum, "**")
                ich_kann = self._wrap(ich_kann, "**")
            elif row.kind == GoalKind.SONDERZIEL:
                ich_kann = self._wrap(ich_kann, "*")
        cells = [datum, ich_kann, self._escape_cell(row.afb), self._escape_cell(row.aufg), self._escape_cell(row.pkte)]
        return "| " + " | ".join(cells) + " |"

    def _render_table(self, section: ReconciledSection) -> list[str]:
        return [self._COLUMN_HEADER, self._SEPARATOR, *(self._render_row(row) for row in section.rows)]

    def render(
        self,
        document: ExpectedHorizonDocument,
        output_path: Path,
        *,
        reconciled: ReconciledHorizon | None = None,
    ) -> None:
        """Schreibt den Kompetenzhorizont als Markdown.

        Args:
            document: Render-DTO (Titel, Untertitel, Sections).
            output_path: Zielpfad.
            reconciled: Abgeglichene Sections; ohne Angabe werden die Sections
                des Dokuments ohne Merge-Quelle abgeglichen (leere Bewertungen).
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        horizon = reconciled if reconciled is not None else reconcile(document.sections, [])

        lines = [f"# {document.title}", "", document.subtitle, ""]
        if len(horizon.sections) == 1:
            lines.extend(self._render_table(horizon.sections[0]))
        else:
            for section in horizon.sections:
                lines.extend([f"{SECTION_HEADING_PREFIX}{section.oberthema}", ""])
                lines.extend(self._render_table(section))
                lines.append("")

        output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
