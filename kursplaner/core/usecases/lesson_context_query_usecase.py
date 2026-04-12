from __future__ import annotations

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.ports.repositories import LessonRepository


class LessonContextQueryUseCase:
    """Bündelt fachliche Kontextabfragen rund um Planzeilen und Stundenbezüge."""

    def __init__(self, lesson_repo: LessonRepository):
        """Initialisiert den Query-Use-Case mit dem benötigten Lesson-Read-Port."""
        self.lesson_repo = lesson_repo

    @staticmethod
    def _keyword_match(text: str, keywords: list[str]) -> bool:
        """Prüft case-insensitiv auf das Vorkommen fachlicher Schlüsselwörter."""
        lowered = text.lower()
        return any(keyword.lower() in lowered for keyword in keywords)

    @staticmethod
    def selected_row_hours(table: PlanTableData | None, row_index: int) -> int:
        """Liest die Stundenzahl einer Zeile robust aus der Planstruktur.

        Liefert `0`, wenn Tabelle/Index ungültig sind oder der Stundenwert
        nicht numerisch vorliegt.
        """
        if table is None or row_index < 0 or row_index >= len(table.rows):
            return 0
        header_map = {name.lower(): idx for idx, name in enumerate(table.headers)}
        idx_stunden = header_map.get("stunden")
        if idx_stunden is None:
            return 0
        row = table.rows[row_index]
        raw = row[idx_stunden].strip() if idx_stunden < len(row) else ""
        return int(raw) if raw.isdigit() else 0

    def next_lzk_number(self, table: PlanTableData) -> int:
        """Bestimmt die nächste freie laufende LZK-Nummer in der Planung.

        Erkennt vorhandene LZKs sowohl über Tabellenmarker als auch über
        `Stundenthema` in verlinkten Stunden.
        """
        count = 0
        lessons_by_row = self.lesson_repo.load_lessons_for_all_rows(table)

        for row_index, row in enumerate(table.rows):
            content = row[2] if len(row) > 2 else ""
            if self._keyword_match(content, ["lzk"]):
                count += 1
                continue
            lesson = lessons_by_row.get(row_index)
            if lesson is None:
                continue
            topic = str(lesson.data.get("Stundenthema", ""))
            if self._keyword_match(topic, ["lzk"]):
                count += 1
        return count + 1

    def last_oberthema_before_row(self, table: PlanTableData, row_index: int) -> str:
        """Liefert das letzte gesetzte Oberthema vor einer Zielzeile.

        Durchsucht vorherige Zeilen rückwärts auf Basis batchgeladener Stunden-YAMLs.
        """
        if row_index <= 0:
            return ""
        probes = list(range(row_index - 1, -1, -1))
        lessons_by_row = self.lesson_repo.load_lessons_for_all_rows(table)
        for probe in probes:
            lesson = lessons_by_row.get(probe)
            if lesson is None:
                continue
            oberthema = str(lesson.data.get("Oberthema", "")).strip()
            if oberthema:
                return oberthema
        return ""
