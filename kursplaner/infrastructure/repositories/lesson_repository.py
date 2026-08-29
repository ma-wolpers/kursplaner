from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData
from kursplaner.infrastructure.repositories.file_signature import file_signature
from kursplaner.infrastructure.repositories.plan_table_file_repository import (
    create_linked_lesson_file,
    get_row_link_path,
    load_linked_lesson_yaml,
    save_linked_lesson_yaml,
    set_lesson_markdown_sections,
)


class FileSystemLessonRepository:
    """Dateibasierte Operationen für verlinkte Stunden-Dateien.

    Hält einen instanzgebundenen `(mtime_ns, size)`-gekeyten Cache geparster
    YAML-Daten (`_lesson_yaml_cache`) — ergänzt das Einzelzeilen-Patching in
    `LoadPlanDetailUseCase.build_day_columns_incremental()` für Fälle, in
    denen trotzdem ein vollständiger Neu-Einlesevorgang nötig ist (initiales
    Laden eines Plans, expliziter Reload nach externer Änderung, UB-
    Entwicklungslisten-Links). Der Cache ist ausschließlich eine Performance-
    Optimierung, nie Quelle der Wahrheit: jeder Lesevorgang vergleicht die
    aktuelle Datei-Signatur gegen die beim letzten Cache-Eintrag gemerkte und
    liest bei Abweichung (externe Änderung erkannt) frisch von der Platte.
    Wird als Singleton in `adapters/bootstrap/wiring.py` erzeugt und lebt für
    die gesamte App-Laufzeit — der Cache ist deshalb kein Modul-Global,
    sondern Instanzzustand (sauber testbar, keine Cross-Test-Verschmutzung).
    """

    def __init__(self) -> None:
        """Initialisiert das Repository mit einem leeren Lesson-YAML-Cache."""
        self._lesson_yaml_cache: dict[Path, tuple[tuple[int, int], LessonYamlData]] = {}

    def resolve_row_link_path(self, table: PlanTableData, row_index: int) -> Path | None:
        """Liest den verlinkten Stunden-Dateipfad für eine Planzeile."""
        return get_row_link_path(table, row_index)

    def load_lesson_yaml(self, path: Path) -> LessonYamlData:
        """Lädt YAML-Daten einer verlinkten Stunden-Datei, gecacht nach Datei-Signatur.

        Liest nur dann tatsächlich von der Platte, wenn kein Cache-Eintrag für
        diesen (aufgelösten) Pfad existiert oder sich `(mtime_ns, size)` seit
        dem letzten Eintrag geändert hat — deckt sowohl eigene Schreibvorgänge
        (siehe `save_lesson_yaml()`/`set_lesson_markdown_sections()`, die den
        Eintrag explizit verwerfen) als auch externe Änderungen ab (Datei von
        außerhalb der App verändert, z. B. direkt in Obsidian oder durch ein
        Sync-Tool — die Signatur weicht dann beim nächsten Aufruf ab, ganz
        ohne dass die App das selbst mitbekommen haben muss).
        """
        resolved = path.resolve()
        try:
            signature = file_signature(resolved)
        except OSError:
            self._lesson_yaml_cache.pop(resolved, None)
            return load_linked_lesson_yaml(path)

        cached = self._lesson_yaml_cache.get(resolved)
        if cached is not None and cached[0] == signature:
            return cached[1]

        lesson = load_linked_lesson_yaml(path)
        self._lesson_yaml_cache[resolved] = (signature, lesson)
        return lesson

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
                lesson = self.load_lesson_yaml(resolved)
                loaded_by_path[resolved] = lesson
            loaded_by_row[row_index] = lesson

        return loaded_by_row

    def load_lessons_for_all_rows(self, table: PlanTableData) -> dict[int, LessonYamlData]:
        """Lädt YAML-Daten für alle Zeilen einer Planungstabelle."""
        return self.load_lessons_for_rows(table, list(range(len(table.rows))))

    def save_lesson_yaml(self, lesson: LessonYamlData) -> None:
        """Persistiert YAML-Daten in die verlinkte Stunden-Datei.

        Verwirft den Cache-Eintrag explizit statt sich auf eine unterschiedliche
        Signatur nach dem Schreiben zu verlassen — sofort korrekt statt von der
        `mtime`-Aufloesung des Dateisystems abhaengig.
        """
        save_linked_lesson_yaml(lesson)
        self._lesson_yaml_cache.pop(lesson.lesson_path.resolve(), None)

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
        """Schreibt Inhalts-/Methodik-Abschnitte in eine Stunden-Markdown-Datei.

        Verwirft den Cache-Eintrag wie `save_lesson_yaml()` (siehe dort).
        """
        set_lesson_markdown_sections(
            lesson_path=lesson_path,
            inhalte_refs=inhalte_refs,
            methodik_refs=methodik_refs,
        )
        self._lesson_yaml_cache.pop(lesson_path.resolve(), None)
