from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PlanTableData:
    """Fachlicher Snapshot einer geladenen Planungstabelle.

    Enthält den ursprünglichen Quellkontext (Dateipfad, Zeilenbereich, Originalzeilen)
    und die editierbaren Tabellenwerte (`headers`, `rows`).
    """

    markdown_path: Path
    headers: list[str]
    rows: list[list[str]]
    start_line: int
    end_line: int
    source_lines: list[str]
    had_trailing_newline: bool
    metadata: dict[str, str]


@dataclass
class LessonYamlData:
    """Fachlicher YAML-Zustand einer einzelnen Stunden-Datei.

    `data` enthält ausschließlich die fachlichen YAML-Felder, nicht den Markdown-Body.
    """

    lesson_path: Path
    data: dict[str, object]


def sanitize_hour_title(text: str) -> str:
    """Bereinigt Freitext zu einem robusten Dateinamen-Stem.

    Entfernt unzulässige Dateisystemzeichen, normalisiert Whitespaces und liefert
    bei leerem Ergebnis den Fallback ``"Neue Stunde"``.
    """

    cleaned = re.sub(r"[\\/:*?\"<>|]", "", text).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or "Neue Stunde"
