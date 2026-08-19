from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from kursplaner.core.domain.wiki_links import strip_group_prefixed_link

COLUMN_DATUM = "Datum"
COLUMN_INHALT = "Inhalt"
COLUMN_THEMA_AUSFALL = "Thema/Ausfall"
"""Kanonische Spaltennamen der Planungstabelle.

Einzige Quelle für "welche drei Spalten gibt es" — sowohl
`plan_table_markdown_io.py::_locate_plan_table_block` (Header-Validierung
beim Laden einer Datei) als auch `PlanTableData.column_index()`/
`.column_index_optional()` (Laufzeit-Zugriff durch Use Cases) referenzieren
dieselben Strings, statt zwei unabhängig gepflegte Schreibweisen zu haben.
"""


@dataclass
class PlanTableData:
    """Fachlicher Snapshot einer geladenen Planungstabelle.

    Enthält den ursprünglichen Quellkontext (Dateipfad, Zeilenbereich, Originalzeilen)
    und die editierbaren Tabellenwerte (`headers`, `rows`).

    `source_mtime_ns`/`source_size` sind ausschließlich für
    `plan_table_file_repository.load_last_plan_table()`/`save_plan_table()`
    gedacht: sie halten die Datei-Signatur zum Ladezeitpunkt fest, damit
    `save_plan_table()` externe Änderungen an der Datei erkennen und Text
    vor/nach der Tabelle vor dem Überschreiben frisch nachladen kann. Andere
    Aufrufer sollten diese Felder nicht lesen oder setzen.
    """

    markdown_path: Path
    headers: list[str]
    rows: list[list[str]]
    start_line: int
    end_line: int
    source_lines: list[str]
    had_trailing_newline: bool
    metadata: dict[str, object]
    source_mtime_ns: int | None = None
    source_size: int | None = None

    def column_index(self, column_name: str) -> int:
        """Liefert den Spaltenindex eines Headernamens (case-insensitiv).

        Zentrale Ablösung der zuvor 4x unabhängig duplizierten
        ``{name.lower(): idx for idx, name in enumerate(headers)}``-Helfer
        (`PlanCommandsUseCase._idx`, `ConvertToHospitationUseCase._header_index`,
        `MarkUnitAsUbUseCase._header_index`, `LessonEditUseCase._header_map`).
        Baut die Lookup bei jedem Aufruf frisch (kein Cache): `headers` ist
        eine mutable Liste ohne Mutationsgarantie, und bei nur ~3 Spalten ist
        der Perf-Gewinn eines Caches vernachlässigbar gegenüber dem Risiko
        eines still veralteten Caches.

        Args:
            column_name: Fachlicher Spaltenname, z. B. `COLUMN_INHALT`.

        Returns:
            Nullbasierter Spaltenindex.

        Raises:
            RuntimeError: Wenn `column_name` nicht in `headers` vorkommt.

        Example::

            table.column_index(COLUMN_INHALT)
            # -> 1
        """
        idx = self.column_index_optional(column_name)
        if idx is None:
            raise RuntimeError(f"Plan-Tabelle muss Spalte '{column_name}' enthalten.")
        return idx

    def column_index_optional(self, column_name: str) -> int | None:
        """Wie `column_index`, liefert aber `None` statt zu werfen.

        Für legitime Legacy-Fallback-Zweige, die auch Tabellen ohne eigene
        `Thema/Ausfall`-Spalte verarbeiten müssen (siehe
        `PlanCommandsUseCase.restore_from_cancel`/`.convert_to_ausfall`).

        Args:
            column_name: Fachlicher Spaltenname, z. B. `COLUMN_THEMA_AUSFALL`.

        Returns:
            Nullbasierter Spaltenindex, oder `None` wenn die Spalte fehlt.
        """
        lowered = column_name.lower()
        for idx, name in enumerate(self.headers):
            if name.lower() == lowered:
                return idx
        return None

    def inhalt(self, row_index: int) -> str:
        """Liest den `Inhalt`-Zellwert einer Planzeile robust (leer bei kurzer Zeile)."""
        idx = self.column_index(COLUMN_INHALT)
        row = self.rows[row_index]
        return row[idx] if idx < len(row) else ""

    def set_inhalt(self, row_index: int, value: str) -> None:
        """Setzt den `Inhalt`-Zellwert; polstert zu kurze Zeilen defensiv auf."""
        idx = self.column_index(COLUMN_INHALT)
        row = self.rows[row_index]
        while len(row) <= idx:
            row.append("")
        row[idx] = value

    def thema_ausfall(self, row_index: int) -> str:
        """Liest den `Thema/Ausfall`-Zellwert einer Planzeile robust (leer bei kurzer Zeile)."""
        idx = self.column_index(COLUMN_THEMA_AUSFALL)
        row = self.rows[row_index]
        return row[idx] if idx < len(row) else ""

    def set_thema_ausfall(self, row_index: int, value: str) -> None:
        """Setzt den `Thema/Ausfall`-Zellwert; polstert zu kurze Zeilen defensiv auf."""
        idx = self.column_index(COLUMN_THEMA_AUSFALL)
        row = self.rows[row_index]
        while len(row) <= idx:
            row.append("")
        row[idx] = value


@dataclass
class LessonYamlData:
    """Fachlicher YAML-Zustand einer einzelnen Stunden-Datei.

    `data` enthält ausschließlich die fachlichen YAML-Felder, nicht den Markdown-Body.
    """

    lesson_path: Path
    data: dict[str, object]


def parse_plan_row_date(value: str) -> date | None:
    """Parst den ``Datum``-Zellwert einer Planzeile (``DD-MM-YY``) robust.

    Konsolidiert die zuvor mehrfach unabhaengig implementierte
    DD-MM-YY-Parsing-Logik (Timetable-Change-, Extend-to-Vacation- und
    Archivierungs-Use-Cases). Liefert ``None`` statt zu werfen, damit
    Aufrufer leere/kaputte Zeilen ueberspringen koennen.

    Example::

        parse_plan_row_date("27-02-26")
        # -> date(2026, 2, 27)
        parse_plan_row_date("")
        # -> None
    """
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%d-%m-%y").date()
    except ValueError:
        return None


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
    return strip_group_prefixed_link(text, group_name)


def read_yaml_oberthema(yaml_data: dict[str, object], group_name: str) -> str:
    """Liest und entschlüsselt das Oberthema aus der YAML einer Stunden-Datei.

    Das YAML-Feld ``Oberthema`` darf bewusst als Wiki-Link gespeichert sein
    (z. B. ``"[[11.1 EFl1 Potenzfunktionen]]"``), damit es in Obsidian
    verlinkt — die Speicherung bleibt davon unberührt. Für Anzeige/Vergleich
    (Grid, Themenfolgen-Erkennung, Exporte, Prefill) liefert diese Funktion
    einheitlich den entschlüsselten Klartext (siehe
    :func:`~kursplaner.core.domain.wiki_links.strip_group_prefixed_link`) —
    die eine Stelle, die jeder Lesepfad dafür aufrufen soll.

    Args:
        yaml_data: Normalisiertes YAML-Dictionary einer Stunden-Datei.
        group_name: Lerngruppen-Bezeichnung des Kurses.

    Returns:
        Der entschlüsselte Oberthema-Text, oder ein leerer String.

    Example::

        read_yaml_oberthema({"Oberthema": "[[11.1 EFl1 Potenzfunktionen]]"}, "11.1")
        # -> "EFl1 Potenzfunktionen"
        read_yaml_oberthema({"Oberthema": "EFl1 Potenzfunktionen"}, "11.1")
        # -> "EFl1 Potenzfunktionen"
    """
    raw = str(yaml_data.get("Oberthema", "")).strip()
    return strip_group_prefixed_link(raw, group_name)
