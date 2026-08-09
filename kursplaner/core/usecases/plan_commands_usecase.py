from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from kursplaner.core.domain.content_markers import build_ausfall_marker, resolve_row_cancel_state
from kursplaner.core.domain.course_rhythm import RHYTHM_YAML_KEY, hours_for_date, parse_rhythm
from kursplaner.core.domain.plan_table import PlanTableData, parse_plan_row_date
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
    def _row_date(table: PlanTableData, row_index: int) -> date | None:
        """Liest und parst das Datum einer Zeile.

        Args:
            table: Planungstabelle.
            row_index: Zielzeile.

        Returns:
            Geparstes Datum oder ``None`` bei fehlender/ungueltiger Zeile.
        """
        idx_datum = PlanCommandsUseCase._idx(table, "datum")
        if not (0 <= row_index < len(table.rows)):
            return None
        row = table.rows[row_index]
        return parse_plan_row_date(row[idx_datum]) if idx_datum < len(row) else None

    @staticmethod
    def _hours_for_row(table: PlanTableData, row_index: int) -> int:
        """Leitet die Rhythmus-Stundenzahl des Wochentags einer Zeile ab (0 falls kein Unterrichtstag)."""
        row_date = PlanCommandsUseCase._row_date(table, row_index)
        if row_date is None:
            return 0
        rhythm = parse_rhythm(table.metadata.get(RHYTHM_YAML_KEY, []))
        return hours_for_date(rhythm, row_date)

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
        """Entfernt die Ausfall-Markierung aus der gewählten Zeile.

        Args:
            table: Planungstabelle.
            row_index: Zielzeile.

        Note:
            Moderne 4-Spalten-Tabellen tragen den Ausfallgrund in der
            `Thema/Ausfall`-Spalte; die `Inhalt`-Spalte bleibt dabei unberührt
            und muss daher nur geleert werden, wenn dort (Legacy-Tabellen ohne
            eigene `Thema/Ausfall`-Spalte) noch der alte Kombi-Marker steht.
        """
        idx_thema_ausfall = self._header_map(table).get("thema/ausfall")
        if idx_thema_ausfall is not None:
            row = table.rows[row_index]
            if idx_thema_ausfall < len(row):
                row[idx_thema_ausfall] = ""
            return

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
        """Setzt eine Zeile auf Ausfall und liefert einen ggf. vorhandenen Link.

        Args:
            table: Planungstabelle.
            row_index: Zielzeile.
            reason_text: Anzuzeigender Ausfallgrund.

        Returns:
            Vorher verlinkte Stunden-Datei oder ``None``.

        Note:
            Moderne 4-Spalten-Tabellen tragen den Ausfallgrund ausschließlich in
            der `Thema/Ausfall`-Spalte; die `Inhalt`-Spalte bleibt unverändert
            (sie darf weiterhin auf eine Schatten-Einheiten-Datei verlinken, z. B.
            wenn deren YAML separat auf `Stundentyp: Ausfall` gesetzt wird). Nur
            für Legacy-Tabellen ohne eigene `Thema/Ausfall`-Spalte greift der
            alte Kombi-Marker-Pfad in der `Inhalt`-Spalte.
        """
        link = self.lesson_repo.resolve_row_link_path(table, row_index)
        marker = build_ausfall_marker(reason_text)
        idx_thema_ausfall = self._header_map(table).get("thema/ausfall")
        if idx_thema_ausfall is not None:
            row = table.rows[row_index]
            if idx_thema_ausfall < len(row):
                row[idx_thema_ausfall] = marker
            return link

        idx_inhalt = self._idx(table, "inhalt")
        if isinstance(link, Path):
            table.rows[row_index][idx_inhalt] = f"{marker} {build_wiki_link(link.stem)}"
        else:
            table.rows[row_index][idx_inhalt] = marker
        return link

    def split_hour_count(self, table: PlanTableData, row_index: int) -> int:
        """Liest und validiert die Stundenanzahl für einen Split.

        Die Stundenzahl ergibt sich aus dem Rhythmus des Wochentags, nicht mehr
        aus einer gespeicherten Tabellenspalte (siehe :meth:`_hours_for_row`).

        Args:
            table: Planungstabelle.
            row_index: Zielzeile.

        Returns:
            Positive Stundenanzahl größer 1.
        """
        hour_count = self._hours_for_row(table, row_index)
        if hour_count <= 1:
            raise RuntimeError("Diese Einheit hat weniger als 2 Stunden.")
        return hour_count

    def split_unit(self, table: PlanTableData, row_index: int) -> int:
        """Teilt eine Mehrstunden-Zeile in einzelne Ein-Stunden-Zeilen desselben Datums.

        Fügt ``hour_count - 1`` weitere Zeilen mit demselben Datum ein; die
        Stundenzahl je Zeile ergibt sich beim Laden automatisch aus der
        Gesamtstundenzahl des Wochentags geteilt durch die Zeilenanzahl
        desselben Datums (siehe ``load_plan_detail_usecase.build_day_columns``
        / :func:`~kursplaner.core.domain.course_rhythm.distribute_hours_over_rows`).

        Args:
            table: Planungstabelle.
            row_index: Ausgangszeile.

        Returns:
            Ursprüngliche Stundenanzahl der gesplitteten Einheit.
        """
        hour_count = self.split_hour_count(table, row_index)

        idx_inhalt = self._idx(table, "inhalt")
        source_row = list(table.rows[row_index])

        for _ in range(hour_count - 1):
            new_row = list(source_row)
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

        Die Stundenzahl der Gruppe ist unabhängig von der Zeilenanzahl fix
        (Rhythmus-Stunden des Wochentags); das Löschen der überzähligen Zeilen
        gibt dem verbleibenden Keeper automatisch die volle Stundenzahl
        (siehe ``load_plan_detail_usecase.build_day_columns``).

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

        non_empty = [idx for idx in group if self._row_content(table, idx)]
        keeper = non_empty[0] if non_empty else group[0]
        total_hours = max(1, self._hours_for_row(table, keeper))

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

        total_hours = max(1, self._hours_for_row(table, group[0]))
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
            if not resolve_row_cancel_state(table.headers, row):
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
