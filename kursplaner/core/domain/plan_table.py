from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.wiki_links import strip_wiki_link


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


def extract_plan_oberthema(thema_ausfall: str, group_name: str) -> str:
    """Liest den Oberthema-Namen direkt aus dem `Thema/Ausfall`-Zellwert der Plantabelle.

    Kehrt die Kodierung um, die `sync_thema_ausfall_to_plan_row` beim Schreiben
    erzeugt (`[[gruppe oberthema]]` bzw. `LZK [[gruppe oberthema]]`). Dient als
    Fallback-Quelle für das Oberthema, solange eine Einheit noch keine eigene,
    verlinkte Stunden-Datei mit YAML-Feld `Oberthema` hat — die Plantabelle
    kann ein Oberthema bereits tragen, bevor die Einheit angelegt wurde.

    Args:
        thema_ausfall: Roher Zellwert der `Thema/Ausfall`-Spalte einer Planzeile.
        group_name: Lerngruppen-Bezeichnung; darf als Wiki-Link vorliegen (z. B.
            ``"[[li2]]"``) und wird automatisch bereinigt.

    Returns:
        Der Oberthema-Text ohne führenden Lerngruppen-Token, oder ein leerer
        String, wenn die Zelle keinen Oberthema-Link enthält (z. B. bei Ausfall
        oder leerer Zelle).

    Example::

        extract_plan_oberthema("[[li2 Kodierung]]", "[[li2]]")
        # -> "Kodierung"
        extract_plan_oberthema("LZK [[li2 Kodierung]]", "li2")
        # -> "Kodierung"
    """
    text = str(thema_ausfall or "").strip()
    if not text:
        return ""
    if text[:4].upper() == "LZK ":
        text = text[4:].strip()
    if not (text.startswith("[[") and text.endswith("]]")):
        return ""

    inner = strip_wiki_link(text)
    group_plain = strip_wiki_link(str(group_name or "").strip())
    if group_plain and inner.lower().startswith(group_plain.lower()):
        remainder = inner[len(group_plain) :].strip()
        if remainder:
            return remainder
    return inner
