from __future__ import annotations

from kursplaner.core.domain.course_rhythm import RHYTHM_YAML_KEY, hours_for_date, parse_rhythm
from kursplaner.core.domain.lesson_yaml_policy import infer_stundentyp
from kursplaner.core.domain.plan_table import PlanTableData, parse_plan_row_date
from kursplaner.core.ports.repositories import LessonRepository


class LessonContextQueryUseCase:
    """Bündelt fachliche Kontextabfragen rund um Planzeilen und Stundenbezüge."""

    def __init__(self, lesson_repo: LessonRepository):
        """Initialisiert den Query-Use-Case mit dem benötigten Lesson-Read-Port."""
        self.lesson_repo = lesson_repo

    @staticmethod
    def selected_row_hours(table: PlanTableData | None, row_index: int) -> int:
        """Liest die Stundenzahl einer Zeile aus dem Wochentags-Rhythmus.

        Liefert `0`, wenn Tabelle/Index ungültig sind oder der Wochentag der
        Zeile keinen Rhythmus-Eintrag hat.
        """
        if table is None or row_index < 0 or row_index >= len(table.rows):
            return 0
        header_map = {name.lower(): idx for idx, name in enumerate(table.headers)}
        idx_datum = header_map.get("datum")
        if idx_datum is None:
            return 0
        row = table.rows[row_index]
        row_date = parse_plan_row_date(row[idx_datum]) if idx_datum < len(row) else None
        if row_date is None:
            return 0
        rhythm = parse_rhythm(table.metadata.get(RHYTHM_YAML_KEY, []))
        return hours_for_date(rhythm, row_date)

    def next_lzk_number(self, table: PlanTableData) -> int:
        """Bestimmt die nächste freie laufende LZK-Nummer in der Planung.

        Erkennt vorhandene LZKs ausschließlich über den YAML-Stundentyp
        verlinkter Stunden-Dateien.
        """
        count = 0
        lessons_by_row = self.lesson_repo.load_lessons_for_all_rows(table)

        for row_index, _row in enumerate(table.rows):
            lesson = lessons_by_row.get(row_index)
            if lesson is None:
                continue
            lesson_data = lesson.data if isinstance(lesson.data, dict) else {}
            if infer_stundentyp(lesson_data) == "LZK":
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
