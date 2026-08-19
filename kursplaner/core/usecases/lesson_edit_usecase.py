from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.plan_table import COLUMN_INHALT, PlanTableData
from kursplaner.core.ports.repositories import LessonRepository


class LessonEditUseCase:
    """Orchestriert den fachlichen Ablauf für Lesson Edit Use-Case.

    Die Klasse bündelt Anwendungslogik zwischen Domain-Regeln und Port-basiertem I/O.
    """

    def __init__(self, lesson_repo: LessonRepository):
        """Initialisiert den Use Case für tabellarische und YAML-Feldänderungen an Stunden."""
        self.lesson_repo = lesson_repo

    def validate_table(self, table: PlanTableData) -> int:
        """Prüft die Mindeststruktur der Planungstabelle für Edit-Operationen.

        Invariante: Spalte ``Inhalt`` muss vorhanden sein.

        Returns:
            Spaltenindex von ``Inhalt``.
        """
        return table.column_index(COLUMN_INHALT)

    def set_content_value(self, table: PlanTableData, row_index: int, value: str) -> None:
        """Setzt den Inhaltswert einer Tabellenzeile ohne YAML-Nebenwirkungen."""
        table.set_inhalt(row_index, value)

    def set_lesson_duration(self, lesson_path: Path, value: str) -> None:
        """Schreibt die Unterrichtsdauer in die verlinkte Stunden-YAML."""
        lesson = self.lesson_repo.load_lesson_yaml(lesson_path)
        lesson.data["Dauer"] = value
        self.lesson_repo.save_lesson_yaml(lesson)

    def set_lesson_field(
        self, lesson_path: Path, field_key: str, value: str, list_entries: list[str] | None = None
    ) -> None:
        """Aktualisiert ein einzelnes YAML-Feld einer Stunde (skalare oder Listenfelder)."""
        lesson = self.lesson_repo.load_lesson_yaml(lesson_path)
        if field_key in {"Kompetenzen", "Teilziele", "Material", "Vertretungsmaterial", "Ressourcen", "Baustellen"}:
            lesson.data[field_key] = list_entries or []
        else:
            lesson.data[field_key] = value
        self.lesson_repo.save_lesson_yaml(lesson)
