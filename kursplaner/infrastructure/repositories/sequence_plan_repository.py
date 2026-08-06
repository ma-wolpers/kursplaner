from __future__ import annotations

import re
from pathlib import Path

from bw_libs.app_paths import atomic_write_text
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.sequence_planning import (
    SEQUENCE_YAML_COURSE_PLAN_KEY,
    build_sequence_stem,
    course_plan_wiki_link,
    extract_halfyear_token_from_table,
    list_sequence_document_paths,
    sequence_directory_for_plan,
)
from kursplaner.core.domain.yaml_registry import SEQUENCE_PLAN_SCHEMA, parse_yaml_frontmatter

_GOAL_KEY = "Sequenzziel"
_FOCUS_COMPETENCY_KEY = "Leitkompetenz"


class FileSystemSequencePlanRepository:
    """Create and update per-course sequence markdown files."""

    _BRAINSTORMING_HEADING = "## Brainstorming"
    _EXPORT_HEADING = "## Export"

    @staticmethod
    def _yaml_quote(value: str) -> str:
        escaped = str(value or "").replace('"', '\\"')
        return f'"{escaped}"'

    @staticmethod
    def _is_separator_row(row_line: str) -> bool:
        text = str(row_line or "").strip()
        if not text.startswith("|"):
            return False
        cells = [cell.strip() for cell in text.strip("|").split("|")]
        if not cells:
            return False
        return all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)

    @classmethod
    def _extract_table_blocks(cls, lines: list[str]) -> list[tuple[int, int]]:
        blocks: list[tuple[int, int]] = []
        start: int | None = None

        for index, line in enumerate(lines):
            stripped = line.strip()
            is_row = stripped.startswith("|") and "|" in stripped[1:]
            if is_row:
                if start is None:
                    start = index
            else:
                if start is not None:
                    if index - start >= 2 and cls._is_separator_row(lines[start + 1]):
                        blocks.append((start, index - 1))
                    start = None

        if start is not None and len(lines) - start >= 2 and cls._is_separator_row(lines[start + 1]):
            blocks.append((start, len(lines) - 1))
        return blocks

    @staticmethod
    def _find_heading_line(lines: list[str], heading: str) -> int:
        normalized = heading.strip().lower()
        for index, line in enumerate(lines):
            if line.strip().lower() == normalized:
                return index
        return -1

    def resolve_sequence_path(self, *, table: PlanTableData, sequence_name: str) -> Path:
        """Resolve canonical sequence markdown path for one plan and sequence name."""
        group_name = str(table.metadata.get("Lerngruppe", "")).strip()
        halfyear_token = extract_halfyear_token_from_table(table)
        stem = build_sequence_stem(
            sequence_name=sequence_name,
            group_name=group_name,
            halfyear_token=halfyear_token,
        )
        return sequence_directory_for_plan(table) / f"{stem}.md"

    def ensure_sequence_document(self, *, table: PlanTableData, sequence_name: str) -> Path:
        """Create a sequence file if missing and return its path."""
        target_path = self.resolve_sequence_path(table=table, sequence_name=sequence_name).expanduser().resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists() and target_path.is_file():
            return target_path

        group_name = str(table.metadata.get("Lerngruppe", "")).strip()
        halfyear_token = extract_halfyear_token_from_table(table)
        title = target_path.stem

        lines = [
            "---",
            f"{SEQUENCE_YAML_COURSE_PLAN_KEY}: {self._yaml_quote(course_plan_wiki_link(table))}",
            f"Sequenzname: {self._yaml_quote(sequence_name)}",
            f"Lerngruppe: {self._yaml_quote(group_name)}",
            f"Halbjahr: {self._yaml_quote(halfyear_token)}",
            f"{_GOAL_KEY}: {self._yaml_quote('')}",
            f"{_FOCUS_COMPETENCY_KEY}: {self._yaml_quote('')}",
            "---",
            "",
            f"# {title}",
            "",
            self._BRAINSTORMING_HEADING,
            "",
            self._EXPORT_HEADING,
            "",
        ]
        atomic_write_text(target_path, "\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return target_path

    def list_sequence_documents(self, table: PlanTableData) -> list[Path]:
        """Listet alle vorhandenen Sequenz-Markdown-Dateien dieses Kursplans."""
        return list_sequence_document_paths(sequence_directory_for_plan(table))

    def read_sequence_name(self, sequence_path: Path) -> str:
        """Liest den `Sequenzname`-Frontmatter-Wert einer Sequenzdatei.

        Wirft wie die übrigen Lesemethoden dieser Klasse (`read_goal_and_focus_competency`,
        `write_goal_and_focus_competency`) bei fehlendem/kaputtem Frontmatter durch —
        kein abweichendes Fehlerverhalten nur für diese eine Methode einführen. Der
        `Sequenzen/`-Ordner enthält per Konstruktion ausschließlich über
        `ensure_sequence_document()` erzeugte, schema-konforme Dateien.
        """
        path = sequence_path.expanduser().resolve()
        text = path.read_text(encoding="utf-8")
        data, _ = parse_yaml_frontmatter(text, SEQUENCE_PLAN_SCHEMA, source_label=str(path))
        return self._coerce_frontmatter_text(data.get("Sequenzname", ""))

    def read_brainstorming(self, sequence_path: Path) -> str:
        """Read the editable brainstorming section from a sequence markdown file."""
        path = sequence_path.expanduser().resolve()
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()

        start = self._find_heading_line(lines, self._BRAINSTORMING_HEADING)
        if start < 0:
            return ""

        end = len(lines)
        for index in range(start + 1, len(lines)):
            if lines[index].strip().startswith("## "):
                end = index
                break

        section_lines = lines[start + 1 : end]
        while section_lines and not section_lines[0].strip():
            section_lines.pop(0)
        while section_lines and not section_lines[-1].strip():
            section_lines.pop()
        return "\n".join(section_lines)

    def write_brainstorming(self, *, sequence_path: Path, brainstorming_text: str) -> None:
        """Update only the brainstorming section while preserving the rest of the document."""
        path = sequence_path.expanduser().resolve()
        lines = path.read_text(encoding="utf-8").splitlines()

        normalized = str(brainstorming_text or "").replace("\r\n", "\n").replace("\r", "\n")
        content_lines = normalized.split("\n") if normalized else []

        start = self._find_heading_line(lines, self._BRAINSTORMING_HEADING)
        export_line = self._find_heading_line(lines, self._EXPORT_HEADING)

        if start < 0:
            insert_at = export_line if export_line >= 0 else len(lines)
            block = [self._BRAINSTORMING_HEADING, ""] + content_lines + [""]
            lines = lines[:insert_at] + block + lines[insert_at:]
        else:
            end = len(lines)
            for index in range(start + 1, len(lines)):
                if lines[index].strip().startswith("## "):
                    end = index
                    break
            replacement = [""] + content_lines + [""]
            lines = lines[: start + 1] + replacement + lines[end:]

        atomic_write_text(path, "\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def replace_trailing_table(self, *, sequence_path: Path, table_lines: list[str]) -> None:
        """Replace only the trailing markdown table while preserving all other content."""
        if not table_lines:
            return

        path = sequence_path.expanduser().resolve()
        lines = path.read_text(encoding="utf-8").splitlines()
        blocks = self._extract_table_blocks(lines)

        if blocks:
            start, end = blocks[-1]
            lines = lines[:start] + list(table_lines) + lines[end + 1 :]
        else:
            export_line = self._find_heading_line(lines, self._EXPORT_HEADING)
            if export_line < 0:
                lines.extend(["", self._EXPORT_HEADING, ""])
            elif export_line + 1 >= len(lines) or lines[export_line + 1].strip():
                lines.insert(export_line + 1, "")
            if lines and lines[-1].strip():
                lines.append("")
            lines.extend(table_lines)

        atomic_write_text(path, "\n".join(lines).rstrip() + "\n", encoding="utf-8")

    @staticmethod
    def render_markdown_table(*, headers: list[str], rows: list[list[str]]) -> list[str]:
        """Render one markdown table as line list."""
        escaped_headers = [str(cell or "").replace("|", "\\|").strip() for cell in headers]
        lines = [
            "| " + " | ".join(escaped_headers) + " |",
            "| " + " | ".join(["---"] * len(escaped_headers)) + " |",
        ]
        for row in rows:
            escaped = [str(cell or "").replace("|", "\\|").replace("\n", " ").strip() for cell in row]
            lines.append("| " + " | ".join(escaped) + " |")
        return lines

    @staticmethod
    def _coerce_frontmatter_text(raw_value: object) -> str:
        """Normalisiert einen geparsten Frontmatter-Wert auf reinen Text.

        `parse_yaml_frontmatter` interpretiert eine leere Zeile (``Schluessel: ""``)
        als Beginn einer YAML-Liste, weil dasselbe Parsing auch echte Listenfelder
        (z. B. ``Kompetenzen``) bedienen muss. Für die reinen Textfelder dieses
        Repositories wird ein solches Leer-Listen-Ergebnis auf einen leeren String
        zurückgeführt.
        """
        if isinstance(raw_value, list):
            return ""
        return str(raw_value or "").strip()

    def read_goal_and_focus_competency(self, sequence_path: Path) -> tuple[str, str]:
        """Liest Sequenzziel und Leitkompetenz aus dem YAML-Frontmatter einer Sequenzdatei.

        Args:
            sequence_path: Pfad der Sequenz-Markdown-Datei.

        Returns:
            Tupel ``(sequenzziel, leitkompetenz)``; beide leer, wenn (noch) nicht gesetzt.
        """
        path = sequence_path.expanduser().resolve()
        text = path.read_text(encoding="utf-8")
        data, _ = parse_yaml_frontmatter(text, SEQUENCE_PLAN_SCHEMA, source_label=str(path))
        sequenzziel = self._coerce_frontmatter_text(data.get(_GOAL_KEY, ""))
        leitkompetenz = self._coerce_frontmatter_text(data.get(_FOCUS_COMPETENCY_KEY, ""))
        return sequenzziel, leitkompetenz

    def write_goal_and_focus_competency(
        self, *, sequence_path: Path, sequenzziel: str, leitkompetenz: str
    ) -> None:
        """Schreibt Sequenzziel/Leitkompetenz chirurgisch in das Frontmatter zurück.

        Ersetzt ausschließlich die beiden betroffenen Frontmatter-Zeilen zwischen
        den beiden ``---``-Markern; alle anderen Frontmatter-Felder sowie der
        gesamte Dateikörper (Titel, Brainstorming, Export-Tabelle) bleiben
        unverändert.

        Args:
            sequence_path: Pfad der Sequenz-Markdown-Datei.
            sequenzziel: Neuer Text für das Sequenzziel-Feld.
            leitkompetenz: Neuer Text für das Leitkompetenz-Feld.

        Raises:
            RuntimeError: Wenn die Datei kein (geschlossenes) YAML-Frontmatter besitzt.
        """
        path = sequence_path.expanduser().resolve()
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0].strip() != "---":
            raise RuntimeError(f"Fehlendes YAML-Frontmatter in Sequenzdatei: {path}")

        closing_index = next((idx for idx in range(1, len(lines)) if lines[idx].strip() == "---"), None)
        if closing_index is None:
            raise RuntimeError(f"YAML-Frontmatter nicht geschlossen in Sequenzdatei: {path}")

        frontmatter_body = [
            line
            for line in lines[1:closing_index]
            if not line.startswith(f"{_GOAL_KEY}:") and not line.startswith(f"{_FOCUS_COMPETENCY_KEY}:")
        ]
        frontmatter_body.append(f"{_GOAL_KEY}: {self._yaml_quote(sequenzziel)}")
        frontmatter_body.append(f"{_FOCUS_COMPETENCY_KEY}: {self._yaml_quote(leitkompetenz)}")

        new_lines = ["---"] + frontmatter_body + lines[closing_index:]
        atomic_write_text(path, "\n".join(new_lines).rstrip() + "\n", encoding="utf-8")

    def is_trivial(self, sequence_path: Path) -> bool:
        """Prüft, ob eine Sequenzdatei außer Struktur keinen echten Inhalt trägt.

        "Inhalt" umfasst Brainstorming-Text, Sequenzziel, Leitkompetenz und
        Export-Tabellenzeilen. Frontmatter-Metadaten (Sequenzname, Lerngruppe,
        Halbjahr, Kursplan-Link) und die Titelzeile zählen nicht, da sie beim
        Anlegen immer gesetzt werden und für sich keinen fachlichen Inhalt tragen.

        Args:
            sequence_path: Pfad der zu prüfenden Sequenz-Markdown-Datei.

        Returns:
            True, wenn die Datei existiert und keinen der obigen Inhalte trägt;
            False bei nicht-existenter Datei oder vorhandenem Inhalt.
        """
        path = sequence_path.expanduser().resolve()
        if not path.exists():
            return False
        if self.read_brainstorming(path).strip():
            return False
        sequenzziel, leitkompetenz = self.read_goal_and_focus_competency(path)
        if sequenzziel.strip() or leitkompetenz.strip():
            return False
        lines = path.read_text(encoding="utf-8").splitlines()
        blocks = self._extract_table_blocks(lines)
        if blocks:
            start, end = blocks[-1]
            if end - start + 1 > 2:  # mehr als Header- + Trennzeile
                return False
        return True

    def delete_if_trivial(self, sequence_path: Path) -> bool:
        """Löscht eine Sequenzdatei, wenn `is_trivial()` keinen Inhalt mehr findet.

        Args:
            sequence_path: Pfad der zu prüfenden/ggf. zu löschenden Sequenzdatei.

        Returns:
            True, wenn die Datei gelöscht wurde.
        """
        if not self.is_trivial(sequence_path):
            return False
        sequence_path.expanduser().resolve().unlink(missing_ok=True)
        return True
