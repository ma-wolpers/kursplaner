from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.content_markers import build_ausfall_marker
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.wiki_links import build_wiki_link
from kursplaner.core.ports.repositories import LessonRepository

LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


@dataclass(frozen=True)
class MergeResult:
    """Beschreibt die Datenstruktur für Merge Result.

    Die Instanz transportiert strukturierte Fachdaten zwischen Schichten und Verarbeitungsschritten.
    """

    merged_count: int
    total_hours: int


class PlanCommandsUseCase:
    """Orchestriert den fachlichen Ablauf für Plan Commands Use-Case.

    Die Klasse bündelt Anwendungslogik zwischen Domain-Regeln und Port-basiertem I/O.
    """

    def __init__(self, lesson_repo: LessonRepository):
        """Initialisiert fachliche Plan-Kommandos mit Port für Link-Auflösung."""
        self.lesson_repo = lesson_repo

    @staticmethod
    def _header_map(table: PlanTableData) -> dict[str, int]:
        """Erzeugt ein Lookup von Spaltenname auf Spaltenindex.

        Args:
            table: Planungstabelle mit Headern.

        Returns:
            Mapping aus kleingeschriebenem Headernamen auf Index.
        """
        return {name.lower(): idx for idx, name in enumerate(table.headers)}

    @staticmethod
    def _idx(table: PlanTableData, key: str) -> int:
        """Liefert den Index einer benötigten Spalte.

        Args:
            table: Planungstabelle mit Headern.
            key: Fachlicher Spaltenname.

        Returns:
            Spaltenindex für ``key``.
        """
        idx = PlanCommandsUseCase._header_map(table).get(key.lower())
        if idx is None:
            raise RuntimeError(f"Plan-Tabelle muss Spalte '{key}' enthalten.")
        return idx

    @staticmethod
    def _contains_link(content: str) -> bool:
        """Prüft, ob ein Zelleninhalt einen Wiki-Link enthält.

        Args:
            content: Zu prüfender Zelleninhalt.

        Returns:
            ``True``, wenn ein Linkmuster gefunden wurde.
        """
        return bool(LINK_RE.search(content or ""))

    @staticmethod
    def _row_content(table: PlanTableData, row_index: int) -> str:
        """Liest den bereinigten Inhalt der Spalte ``inhalt`` aus einer Zeile.

        Args:
            table: Planungstabelle.
            row_index: Zielzeile.

        Returns:
            Getrimmter Inhaltswert oder leerer String.
        """
        idx_inhalt = PlanCommandsUseCase._idx(table, "inhalt")
        if not (0 <= row_index < len(table.rows)):
            return ""
        row = table.rows[row_index]
        return row[idx_inhalt].strip() if idx_inhalt < len(row) else ""

    def restore_from_cancel(self, table: PlanTableData, row_index: int) -> None:
        """Entfernt den Abbruchtext aus der gewählten Zeile.

        Args:
            table: Planungstabelle.
            row_index: Zielzeile.
        """
        idx_inhalt = self._idx(table, "inhalt")
        current = table.rows[row_index][idx_inhalt]
        if isinstance(current, str):
            match = LINK_RE.search(current)
            if match:
                target = match.group(1).strip()
                if "|" in target:
                    target = target.split("|", 1)[0].strip()
                if target:
                    table.rows[row_index][idx_inhalt] = build_wiki_link(target)
                    return
        table.rows[row_index][idx_inhalt] = ""

    def clear_selected_lesson(self, table: PlanTableData, row_index: int) -> Path | None:
        """Löscht den Tabelleninhalt der Zielzeile und gibt den bisherigen Link zurück.

        Args:
            table: Planungstabelle.
            row_index: Zielzeile.

        Returns:
            Bisher verlinkte Stunden-Datei oder ``None``.
        """
        idx_inhalt = self._idx(table, "inhalt")
        link = self.lesson_repo.resolve_row_link_path(table, row_index)
        table.rows[row_index][idx_inhalt] = ""
        return link

    def convert_to_ausfall(self, table: PlanTableData, row_index: int, reason_text: str) -> Path | None:
        """Setzt eine Zeile auf Ausfalltext und liefert einen ggf. vorhandenen Link.

        Args:
            table: Planungstabelle.
            row_index: Zielzeile.
            reason_text: Anzuzeigender Ausfallgrund.

        Returns:
            Vorher verlinkte Stunden-Datei oder ``None``.
        """
        idx_inhalt = self._idx(table, "inhalt")
        link = self.lesson_repo.resolve_row_link_path(table, row_index)
        marker = build_ausfall_marker(reason_text)
        if isinstance(link, Path):
            table.rows[row_index][idx_inhalt] = f"{marker} {build_wiki_link(link.stem)}"
        else:
            table.rows[row_index][idx_inhalt] = marker
        return link

    def split_hour_count(self, table: PlanTableData, row_index: int) -> int:
        """Liest und validiert die Stundenanzahl für einen Split.

        Args:
            table: Planungstabelle.
            row_index: Zielzeile.

        Returns:
            Positive Stundenanzahl größer 1.
        """
        idx_stunden = self._idx(table, "stunden")
        hours_text = table.rows[row_index][idx_stunden].strip()
        if not hours_text.isdigit() or int(hours_text) <= 1:
            raise RuntimeError("Diese Einheit hat weniger als 2 Stunden.")
        return int(hours_text)

    def split_unit(self, table: PlanTableData, row_index: int) -> int:
        """Teilt eine Mehrstunden-Zeile in einzelne Ein-Stunden-Zeilen.

        Args:
            table: Planungstabelle.
            row_index: Ausgangszeile.

        Returns:
            Ursprüngliche Stundenanzahl der gesplitteten Einheit.
        """
        idx_stunden = self._idx(table, "stunden")
        hours_text = table.rows[row_index][idx_stunden].strip()
        if not hours_text.isdigit() or int(hours_text) <= 1:
            raise RuntimeError("Diese Einheit hat weniger als 2 Stunden.")

        hour_count = int(hours_text)
        source_row = list(table.rows[row_index])
        table.rows[row_index][idx_stunden] = "1"

        for _ in range(hour_count - 1):
            new_row = list(source_row)
            new_row[idx_stunden] = "1"
            idx_inhalt = self._idx(table, "inhalt")
            if idx_inhalt < len(new_row):
                new_row[idx_inhalt] = ""
            table.rows.insert(row_index + 1, new_row)

        return hour_count

    def _date_group_row_indices(self, table: PlanTableData, row_index: int) -> list[int]:
        """Sammelt alle Zeilenindizes mit gleichem Datumswert.

        Args:
            table: Planungstabelle.
            row_index: Referenzzeile für das Ziel-Datum.

        Returns:
            Alle Zeilenindizes derselben Datumsgruppe.
        """
        idx_datum = self._idx(table, "datum")
        target_date = table.rows[row_index][idx_datum] if idx_datum < len(table.rows[row_index]) else ""
        return [
            idx for idx, row in enumerate(table.rows) if (row[idx_datum] if idx_datum < len(row) else "") == target_date
        ]

    def can_merge_date_units(self, table: PlanTableData, row_index: int) -> bool:
        """Prüft, ob Einheiten eines Datums ohne Konflikt zusammengeführt werden dürfen.

        Args:
            table: Planungstabelle.
            row_index: Referenzzeile.

        Returns:
            ``True`` bei zusammenführbaren Zeilen.
        """
        group = self._date_group_row_indices(table, row_index)
        if len(group) <= 1:
            return False
        non_empty = [idx for idx in group if self._row_content(table, idx)]
        return len(non_empty) <= 1

    def merge_units(self, table: PlanTableData, row_index: int) -> MergeResult:
        """Führt die tatsächliche Zusammenführung einer Datumsgruppe aus.

        Args:
            table: Planungstabelle.
            row_index: Referenzzeile.

        Returns:
            Kennzahlen zur Anzahl und Summe der zusammengeführten Zeilen.
        """
        group = self._date_group_row_indices(table, row_index)
        if len(group) <= 1:
            raise RuntimeError("Für dieses Datum gibt es nichts zu verbinden.")
        if not self.can_merge_date_units(table, row_index):
            raise RuntimeError("Verbinden ist nur möglich, wenn maximal eine Einheit Inhalt hat.")

        idx_stunden = self._idx(table, "stunden")
        non_empty = [idx for idx in group if self._row_content(table, idx)]
        keeper = non_empty[0] if non_empty else group[0]

        total_hours = 0
        for idx in group:
            raw = table.rows[idx][idx_stunden].strip() if idx_stunden < len(table.rows[idx]) else ""
            total_hours += int(raw) if raw.isdigit() else 0
        total_hours = max(1, total_hours)

        table.rows[keeper][idx_stunden] = str(total_hours)
        for idx in sorted([item for item in group if item != keeper], reverse=True):
            del table.rows[idx]

        return MergeResult(merged_count=len(group), total_hours=total_hours)

    def merge_preview(self, table: PlanTableData, row_index: int) -> MergeResult:
        """Berechnet eine Merge-Vorschau ohne Tabellenänderung.

        Args:
            table: Planungstabelle.
            row_index: Referenzzeile.

        Returns:
            Kennzahlen, die bei einem Merge zu erwarten sind.
        """
        group = self._date_group_row_indices(table, row_index)
        if len(group) <= 1:
            raise RuntimeError("Für dieses Datum gibt es nichts zu verbinden.")
        if not self.can_merge_date_units(table, row_index):
            raise RuntimeError("Verbinden ist nur möglich, wenn maximal eine Einheit Inhalt hat.")

        idx_stunden = self._idx(table, "stunden")
        total_hours = 0
        for idx in group:
            raw = table.rows[idx][idx_stunden].strip() if idx_stunden < len(table.rows[idx]) else ""
            total_hours += int(raw) if raw.isdigit() else 0
        total_hours = max(1, total_hours)

        return MergeResult(merged_count=len(group), total_hours=total_hours)

    def shift_existing_lessons_forward(self, table: PlanTableData, start_row_index: int) -> bool:
        """Verschiebt bestehende Inhalte ab einer Zeile um einen freien Slot nach hinten.

        Args:
            table: Planungstabelle.
            start_row_index: Startzeile der Verschiebung.

        Returns:
            ``True`` bei erfolgreicher Verschiebung, sonst ``False``.
        """
        idx_inhalt = self._idx(table, "inhalt")

        valid_rows: list[int] = []
        for row_index, row in enumerate(table.rows):
            content = row[idx_inhalt] if idx_inhalt < len(row) else ""
            has_link = self._contains_link(content)
            is_cancel = bool(content.strip() and not has_link)
            if not is_cancel:
                valid_rows.append(row_index)

        if start_row_index not in valid_rows:
            return False

        start_pos = valid_rows.index(start_row_index)
        free_pos = None
        for probe in range(start_pos, len(valid_rows)):
            row_index = valid_rows[probe]
            content = table.rows[row_index][idx_inhalt].strip()
            if not content:
                free_pos = probe
                break

        if free_pos is None:
            return False

        for probe in range(free_pos, start_pos, -1):
            dst = valid_rows[probe]
            src = valid_rows[probe - 1]
            table.rows[dst][idx_inhalt] = table.rows[src][idx_inhalt]

        table.rows[start_row_index][idx_inhalt] = ""
        return True

    def swap_contents(self, table: PlanTableData, row_a: int, row_b: int) -> None:
        """Tauscht Inhalte der Spalte ``inhalt`` zwischen zwei Zeilen.

        Args:
            table: Planungstabelle.
            row_a: Erste Zielzeile.
            row_b: Zweite Zielzeile.
        """
        idx_inhalt = self._idx(table, "inhalt")
        if not (0 <= row_a < len(table.rows) and 0 <= row_b < len(table.rows)):
            raise RuntimeError("Ungültige Zeilen für Verschiebung.")

        content_a = table.rows[row_a][idx_inhalt] if idx_inhalt < len(table.rows[row_a]) else ""
        content_b = table.rows[row_b][idx_inhalt] if idx_inhalt < len(table.rows[row_b]) else ""

        if idx_inhalt < len(table.rows[row_a]):
            table.rows[row_a][idx_inhalt] = content_b
        if idx_inhalt < len(table.rows[row_b]):
            table.rows[row_b][idx_inhalt] = content_a
