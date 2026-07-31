from __future__ import annotations

from pathlib import Path

from kursplaner.core.usecases.export_topic_units_pdf_usecase import TopicUnitsPdfDocument


class TopicUnitsMarkdownRenderer:
    """Rendert den Oberthema-Export als Markdown-Tabelle."""

    @staticmethod
    def _escape_cell(value: str) -> str:
        return str(value or "").replace("|", "\\|").replace("\n", " ").strip()

    def render(self, document: TopicUnitsPdfDocument, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        sequenzziel_text = document.sequenzziel.strip() or "_(nicht gesetzt)_"
        leitkompetenz_text = document.leitkompetenz.strip() or "_(nicht gesetzt)_"

        lines = [
            f"# {document.title}",
            "",
            document.subtitle,
            "",
            f"Exportdatum: {document.export_date_text}",
            "",
            f"**Sequenzziel:** {sequenzziel_text}",
            f"**Leitkompetenz:** {leitkompetenz_text}",
            "",
            "| Datum | Stunden | Thema | Stundenziel | geförderte Prozesskompetenzen |",
            "| --- | --- | --- | --- | --- |",
        ]

        for row in document.rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        self._escape_cell(row.datum),
                        self._escape_cell(row.stunden),
                        self._escape_cell(row.thema),
                        self._escape_cell(row.stundenziel),
                        self._escape_cell(row.prozesskompetenzen),
                    ]
                )
                + " |"
            )

        output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
