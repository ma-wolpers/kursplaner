from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.lesson_yaml_policy import infer_stundentyp
from kursplaner.core.domain.oberthema_values import OBERTHEMA_KEY, encode_oberthemen, normalize_oberthemen
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

    def set_lesson_oberthemen(self, lesson_path: Path, topics: list[str], group_name: str) -> None:
        """Schreibt das Oberthema einer Stunde als ausdrückliche Korrektur (kanonische Liste).

        Setzt die Invarianten durch (Entschlüsselung, keine Duplikate/Leereinträge,
        Wiki-Link-Form) und erlaubt als bewusstes Speichern der Oberthema-Zelle
        auch das Ersetzen eines ungültigen Plattenwerts (``repair_oberthema``).

        Args:
            lesson_path: Pfad der Stunden-Datei.
            topics: Eingegebene Themen (roh, dürfen Wiki-Links/Duplikate enthalten).
            group_name: Lerngruppen-Bezeichnung des Kurses.

        Raises:
            RuntimeError: Wenn eine Nicht-LZK-Einheit mehr als ein Oberthema bekäme.
        """
        lesson = self.lesson_repo.load_lesson_yaml(lesson_path)
        normalized = normalize_oberthemen(topics, group_name)
        if len(normalized) > 1 and infer_stundentyp(lesson.data) != "LZK":
            raise RuntimeError("Nur eine LZK darf mehrere Oberthemen haben.")
        lesson.data[OBERTHEMA_KEY] = encode_oberthemen(normalized, group_name)
        self.lesson_repo.save_lesson_yaml(lesson, repair_oberthema=True)

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
        if field_key in {
            "Kompetenzen",
            "Teilziele",
            "Sonderziele",
            "Material",
            "Vertretungsmaterial",
            "Ressourcen",
            "Baustellen",
        }:
            lesson.data[field_key] = list_entries or []
        else:
            lesson.data[field_key] = value
        self.lesson_repo.save_lesson_yaml(lesson)
