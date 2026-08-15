from __future__ import annotations

import re
from pathlib import Path

from kursplaner.core.domain.content_markers import build_ausfall_marker, resolve_row_cancel_state
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.wiki_links import build_wiki_link
from kursplaner.core.ports.repositories import LessonRepository

LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


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
