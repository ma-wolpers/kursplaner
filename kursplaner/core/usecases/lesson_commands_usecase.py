from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData, sanitize_hour_title
from kursplaner.core.ports.repositories import LessonRepository


class LessonCommandsUseCase:
    """Orchestriert den fachlichen Ablauf für Lesson Commands Use-Case.

    Die Klasse bündelt Anwendungslogik zwischen Domain-Regeln und Port-basiertem I/O.
    """

    def __init__(self, lesson_repo: LessonRepository):
        """Initialisiert Kommandos zum Erzeugen und Ändern von Stunden-Dateien.

        Args:
            lesson_repo: Repository mit CRUD-Operationen für Stunden.
        """
        self.lesson_repo = lesson_repo

    def create_lzk_lesson(
        self,
        table: PlanTableData,
        row_index: int,
        title: str,
        default_hours: int,
    ) -> Path:
        """Erzeugt eine LZK-Stunde, verlinkt sie und synchronisiert das Thema.

        Args:
            table: Planungstabelle.
            row_index: Zielzeile.
            title: Titel für die anzulegende Stunde.
            default_hours: Initiale Stundenanzahl.

        Returns:
            Pfad der angelegten Stunden-Datei.
        """
        link = self.lesson_repo.create_linked_lesson_file(table, row_index, title, default_hours)
        lesson = self.lesson_repo.load_lesson_yaml(link)
        lesson.data["Stundentyp"] = "LZK"
        lesson.data["Stundenthema"] = sanitize_hour_title(title) or "LZK"
        lesson.data.setdefault("Oberthema", "")
        self.lesson_repo.save_lesson_yaml(lesson)
        return link

    def create_regular_lesson_link(
        self,
        table: PlanTableData,
        row_index: int,
        topic: str,
        default_hours: int,
    ) -> Path:
        """Erzeugt und verlinkt eine reguläre Stunden-Datei.

        Args:
            table: Planungstabelle.
            row_index: Zielzeile.
            topic: Thema der neuen Stunde.
            default_hours: Initiale Stundenanzahl.

        Returns:
            Pfad der angelegten Stunden-Datei.
        """
        return self.lesson_repo.create_linked_lesson_file(table, row_index, topic, default_hours)

    def update_regular_lesson_content(
        self,
        lesson_path: Path,
        topic: str,
        oberthema_input: str,
        *,
        was_lzk: bool,
        content_before: str,
    ) -> None:
        """Aktualisiert Kernfelder einer regulären Stunde in der YAML-Struktur.

        Args:
            lesson_path: Pfad zur Stunden-Datei.
            topic: Neues Stundenthema.
            oberthema_input: Optionaler Oberthemawert.
            was_lzk: Kennzeichen, ob die Stunde vorher als LZK geführt wurde.
            content_before: Vorheriger Tabelleninhalt für Fallbacks.
        """
        lesson = self.lesson_repo.load_lesson_yaml(lesson_path)
        lesson.data["Stundentyp"] = "Unterricht"
        lesson.data["Stundenthema"] = sanitize_hour_title(topic)
        if oberthema_input:
            lesson.data["Oberthema"] = oberthema_input
        self.lesson_repo.save_lesson_yaml(lesson)

    def update_lesson_sections(self, lesson_path: Path, inhalte_refs: list[str], methodik_refs: list[str]) -> None:
        """Schreibt Inhalte-/Methodik-Referenzen in die Stunden-Markdown-Datei.

        Args:
            lesson_path: Pfad zur Stunden-Datei.
            inhalte_refs: Einträge für den Abschnitt ``Inhalte``.
            methodik_refs: Einträge für den Abschnitt ``Methodik``.
        """
        if inhalte_refs or methodik_refs:
            self.lesson_repo.set_lesson_markdown_sections(lesson_path, inhalte_refs, methodik_refs)

    def update_lesson_competencies(self, lesson_path: Path, kompetenzen_refs: list[str], stundenziel: str = "") -> None:
        """Schreibt Kompetenzlisten in die Stunden-YAML-Datei."""
        lesson = self.lesson_repo.load_lesson_yaml(lesson_path)
        lesson.data["Kompetenzen"] = list(kompetenzen_refs)
        if stundenziel.strip():
            lesson.data["Stundenziel"] = stundenziel.strip()
        self.lesson_repo.save_lesson_yaml(lesson)
