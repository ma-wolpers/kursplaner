from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData
from kursplaner.infrastructure.repositories.plan_table_file_repository import (
    create_linked_lesson_file,
    get_row_link_path,
    load_linked_lesson_yaml,
    save_linked_lesson_yaml,
    set_lesson_markdown_sections,
)


class FileSystemLessonRepository:
    """Dateibasierte Operationen für verlinkte Stunden-Dateien."""

    def resolve_row_link_path(self, table: PlanTableData, row_index: int) -> Path | None:
        """Liest den verlinkten Stunden-Dateipfad für eine Planzeile."""
        return get_row_link_path(table, row_index)

    def load_lesson_yaml(self, path: Path) -> LessonYamlData:
        """Lädt YAML-Daten einer verlinkten Stunden-Datei."""
        return load_linked_lesson_yaml(path)

    def load_lessons_for_rows(self, table: PlanTableData, row_indices: list[int]) -> dict[int, LessonYamlData]:
        """Lädt YAML-Daten für mehrere Zeilen, dedupliziert nach Dateipfad."""
        loaded_by_row: dict[int, LessonYamlData] = {}
        loaded_by_path: dict[Path, LessonYamlData] = {}

        for row_index in row_indices:
            link_path = get_row_link_path(table, row_index)
            if not (isinstance(link_path, Path) and link_path.exists() and link_path.is_file()):
                continue

            resolved = link_path.resolve()
            lesson = loaded_by_path.get(resolved)
            if lesson is None:
                lesson = load_linked_lesson_yaml(resolved)
                loaded_by_path[resolved] = lesson
            loaded_by_row[row_index] = lesson

        return loaded_by_row

    def load_lessons_for_all_rows(self, table: PlanTableData) -> dict[int, LessonYamlData]:
        """Lädt YAML-Daten für alle Zeilen einer Planungstabelle."""
        return self.load_lessons_for_rows(table, list(range(len(table.rows))))

    def save_lesson_yaml(self, lesson: LessonYamlData) -> None:
        """Persistiert YAML-Daten in die verlinkte Stunden-Datei."""
        save_linked_lesson_yaml(lesson)

    def create_linked_lesson_file(
        self, plan_table: PlanTableData, row_index: int, lesson_topic: str, default_hours: int
    ) -> Path:
        """Erzeugt und verlinkt eine neue Stunden-Datei für eine Planzeile."""
        return create_linked_lesson_file(
            plan_table=plan_table,
            row_index=row_index,
            lesson_topic=lesson_topic,
            default_hours=default_hours,
        )

    def set_lesson_markdown_sections(
        self, lesson_path: Path, inhalte_refs: list[str], methodik_refs: list[str]
    ) -> None:
        """Schreibt Inhalts-/Methodik-Abschnitte in eine Stunden-Markdown-Datei."""
        set_lesson_markdown_sections(
            lesson_path=lesson_path,
            inhalte_refs=inhalte_refs,
            methodik_refs=methodik_refs,
        )
