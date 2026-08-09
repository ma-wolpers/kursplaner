from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.ports.repositories import LessonRepository


class LessonEditUseCase:
    """Orchestriert den fachlichen Ablauf für Lesson Edit Use-Case.

    Die Klasse bündelt Anwendungslogik zwischen Domain-Regeln und Port-basiertem I/O.
    """

    def __init__(self, lesson_repo: LessonRepository):
        """Initialisiert den Use Case für tabellarische und YAML-Feldänderungen an Stunden."""
        self.lesson_repo = lesson_repo

    @staticmethod
    def _header_map(table: PlanTableData) -> dict[str, int]:
        """Erzeugt ein robustes Header-Index-Mapping für Tabellenoperationen."""
        return {name.lower(): idx for idx, name in enumerate(table.headers)}

    def validate_table(self, table: PlanTableData) -> int:
        """Prüft die Mindeststruktur der Planungstabelle für Edit-Operationen.

        Invariante: Spalte ``inhalt`` muss vorhanden sein.

        Returns:
            Spaltenindex von ``inhalt``.
        """
        header_map = self._header_map(table)
        idx_inhalt = header_map.get("inhalt")
        if idx_inhalt is None:
            raise RuntimeError("Plan-Tabelle muss Datum und Inhalt enthalten.")
        return idx_inhalt

    def set_content_value(self, table: PlanTableData, row_index: int, value: str) -> None:
        """Setzt den Inhaltswert einer Tabellenzeile ohne YAML-Nebenwirkungen."""
        idx_inhalt = self.validate_table(table)
        table.rows[row_index][idx_inhalt] = value

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
