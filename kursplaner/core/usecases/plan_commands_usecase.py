from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.content_markers import build_ausfall_marker
from kursplaner.core.domain.lesson_yaml_policy import infer_stundentyp
from kursplaner.core.domain.plan_row_payload import Move, apply_moves, shift_moves, swap_payloads
from kursplaner.core.domain.plan_table import COLUMN_INHALT, COLUMN_THEMA_AUSFALL, PlanTableData
from kursplaner.core.domain.wiki_links import build_dataview_lesson_link, first_wiki_link
from kursplaner.core.ports.repositories import LessonRepository


class PlanCommandsUseCase:
    """Orchestriert den fachlichen Ablauf für Plan Commands Use-Case.

    Die Klasse bündelt Anwendungslogik zwischen Domain-Regeln und Port-basiertem I/O.
    """

    def __init__(self, lesson_repo: LessonRepository):
        """Initialisiert fachliche Plan-Kommandos mit Port für Link-Auflösung."""
        self.lesson_repo = lesson_repo

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
        idx_thema_ausfall = table.column_index_optional(COLUMN_THEMA_AUSFALL)
        if idx_thema_ausfall is not None:
            row = table.rows[row_index]
            if idx_thema_ausfall < len(row):
                row[idx_thema_ausfall] = ""
            return

        idx_inhalt = table.column_index(COLUMN_INHALT)
        current = table.rows[row_index][idx_inhalt]
        if isinstance(current, str):
            link = first_wiki_link(current)
            if link is not None and link[0]:
                table.rows[row_index][idx_inhalt] = build_dataview_lesson_link(link[0])
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
        idx_inhalt = table.column_index(COLUMN_INHALT)
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
        idx_thema_ausfall = table.column_index_optional(COLUMN_THEMA_AUSFALL)
        if idx_thema_ausfall is not None:
            row = table.rows[row_index]
            if idx_thema_ausfall < len(row):
                row[idx_thema_ausfall] = marker
            return link

        idx_inhalt = table.column_index(COLUMN_INHALT)
        if isinstance(link, Path):
            table.rows[row_index][idx_inhalt] = f"{marker} {build_dataview_lesson_link(link.stem)}"
        else:
            table.rows[row_index][idx_inhalt] = marker
        return link

    def is_lzk_row(self, table: PlanTableData, row_index: int) -> bool:
        """``True``, wenn die verlinkte Einheit eine LZK ist (fester Termin beim Verschieben).

        Gleiche Typregel wie `DayColumn.stundentyp` (`infer_stundentyp` auf der
        verlinkten YAML); eine nicht lesbare Datei gilt als nicht fest.
        """
        link = self.lesson_repo.resolve_row_link_path(table, row_index)
        if not isinstance(link, Path) or not link.is_file():
            return False
        try:
            return infer_stundentyp(self.lesson_repo.load_lesson_yaml(link).data) == "LZK"
        except (OSError, RuntimeError, TypeError, ValueError):
            return False

    def plan_shift(self, table: PlanTableData, start_row_index: int) -> tuple[Move, ...] | None:
        """Vorschau des Verschiebens ab *start_row_index* (LZKs bleiben stehen), ohne zu schreiben.

        Returns:
            Die Bewegungen (`plan_row_payload.shift_moves`) oder ``None``, wenn
            bis zum Tabellenende kein freier Termin kommt.
        """
        return shift_moves(table, start_row_index, lambda row: self.is_lzk_row(table, row))

    def shift_existing_lessons_forward(self, table: PlanTableData, start_row_index: int) -> bool:
        """Verschiebt Einheiten ab einer Zeile um einen Termin nach hinten bis zum ersten freien Termin.

        Link und Thema-Zelle wandern gemeinsam (`plan_row_payload`); Ausfall-/Ferientermine
        und LZKs bleiben stehen und werden übersprungen. Die Startzeile selbst wird auch
        dann verschoben, wenn sie eine LZK ist (ausdrücklich gewählt).

        Args:
            table: Planungstabelle.
            start_row_index: Zeile, die frei werden soll.

        Returns:
            ``True`` bei erfolgreicher Verschiebung, sonst ``False`` (Tabelle unverändert).
        """
        moves = self.plan_shift(table, start_row_index)
        if moves is None:
            return False
        apply_moves(table, moves, start_row_index)
        return True

    def swap_contents(self, table: PlanTableData, row_a: int, row_b: int) -> None:
        """Tauscht die Einheiten zweier Zeilen (Link + Thema-Zelle, Termine bleiben).

        Args:
            table: Planungstabelle.
            row_a: Erste Zielzeile.
            row_b: Zweite Zielzeile.
        """
        if not (0 <= row_a < len(table.rows) and 0 <= row_b < len(table.rows)):
            raise RuntimeError("Ungültige Zeilen für Verschiebung.")
        swap_payloads(table, row_a, row_b)
