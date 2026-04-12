from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable, Protocol

from kursplaner.core.domain.kompetenzkatalog import Kompetenzkatalog, KompetenzkatalogManifestEntry
from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData

ConfirmChange = Callable[[str, str], bool]
PlanCalendarEvent = tuple[str, date, date]


class PlanRepository(Protocol):
    """Definiert den Vertrag für Plan Repository.

    Die konkrete Implementierung wird in der Infrastructure-Schicht bereitgestellt.
    """

    def load_plan_table(self, markdown_path: Path) -> PlanTableData:
        """Lädt eine Planungstabelle aus einer Markdown-Datei.

        Args:
            markdown_path: Pfad zur Planungs-Markdown-Datei.

        Returns:
            Das fachliche PlanTableData-Modell.
        """
        ...

    def load_plan_tables(self, base_dir: Path) -> list[PlanTableData]:
        """Lädt alle verwalteten Planungstabellen unterhalb eines Basisordners.

        Args:
            base_dir: Wurzelverzeichnis mit Unterrichtsordnern.

        Returns:
            Liste aller erfolgreich geladenen PlanTableData-Modelle.
        """
        ...

    def save_plan_table(self, table: PlanTableData) -> None:
        """Persistiert eine geänderte Planungstabelle.

        Args:
            table: Zu speichernder Tabellenzustand.
        """
        ...

    def list_plan_markdown_files(self, base_dir: Path) -> list[Path]:
        """Listet alle verwalteten Plan-Markdown-Dateien unterhalb eines Basisordners.

        Args:
            base_dir: Wurzelverzeichnis mit Unterrichtsordnern.

        Returns:
            Liste der gefundenen Plan-Dateipfade.
        """
        ...

    def load_plan_metadata(self, markdown_path: Path) -> dict[str, str]:
        """Lädt Metadaten einer Planungsdatei.

        Args:
            markdown_path: Pfad zur Planungsdatei.

        Returns:
            Key-Value-Mapping der Plan-Metadaten.
        """
        ...

    def invalidate_plan_list_cache(self, base_dir: Path | None = None) -> None:
        """Invalidiert den internen Planlisten-Index.

        Args:
            base_dir: Optionales Basisverzeichnis zur gezielten Invalidation.
        """
        ...

    def invalidate_cache(self, base_dir: Path | None = None) -> None:
        """Invalidiert interne Plan-bezogene Caches gezielt oder vollständig.

        Args:
            base_dir: Optionales Basisverzeichnis zur gezielten Invalidation.
        """
        ...

    def append_plan_rows(
        self,
        markdown_path: Path,
        rows: list[tuple[date, int, str]],
        confirm_change: ConfirmChange | None = None,
    ) -> None:
        """Hängt Planzeilen als Markdown-Tabelle an eine bestehende Plan-Datei an.

        Args:
            markdown_path: Zielpfad der Plan-Markdown-Datei.
            rows: Zu schreibende Terminzeilen.
            confirm_change: Optionale Bestätigung vor dem Schreibvorgang.
        """
        ...

    def write_plan_rows(
        self,
        markdown_path: Path,
        rows: list[tuple[date, int, str]],
        confirm_change: ConfirmChange | None = None,
    ) -> None:
        """Schreibt Planzeilen als initiale oder ersetzte Haupttabelle.

        Wird für Erstanlage oder vollständiges Ersetzen der letzten Planungstabelle verwendet.

        Args:
            markdown_path: Zielpfad der Plan-Markdown-Datei.
            rows: Zu schreibende Terminzeilen.
            confirm_change: Optionale Bestätigung vor dem Schreibvorgang.
        """
        ...

    def write_plan_metadata(
        self,
        markdown_path: Path,
        group_name: str,
        course_subject: str,
        grade_level: int,
        kc_profile_label: str | None = None,
        process_competencies: tuple[str, ...] = (),
        content_competency: str | None = None,
    ) -> None:
        """Schreibt/aktualisiert den YAML-Metadatenblock einer Plan-Datei.

        Args:
            markdown_path: Zielpfad der Plan-Markdown-Datei.
            group_name: Lerngruppenname.
            course_subject: Standardisiertes Kursfach (z. B. ``Informatik``).
            grade_level: Jahrgangsstufe.
            kc_profile_label: Optionales KC-Profil fuer die Unterrichtseinheit.
            process_competencies: Optional gewaehlte prozessbezogene Kompetenzen.
            content_competency: Optional gewaehltes inhaltsbezogenes Stundenziel.
        """
        ...


class LessonRepository(Protocol):
    """Definiert den Vertrag für Lesson Repository.

    Die konkrete Implementierung wird in der Infrastructure-Schicht bereitgestellt.
    """

    def resolve_row_link_path(self, table: PlanTableData, row_index: int) -> Path | None:
        """Löst den Link einer Tabellenzeile auf eine Stunden-Datei auf.

        Args:
            table: Planungstabelle mit der Zielzeile.
            row_index: Index der Zeile in der Tabelle.

        Returns:
            Pfad zur verlinkten Stunden-Datei oder ``None``.
        """
        ...

    def load_lesson_yaml(self, path: Path) -> LessonYamlData:
        """Lädt YAML-Daten einer Stunden-Datei.

        Args:
            path: Pfad zur Stunden-Datei.

        Returns:
            Strukturiertes LessonYamlData-Modell.
        """
        ...

    def load_lessons_for_rows(self, table: PlanTableData, row_indices: list[int]) -> dict[int, LessonYamlData]:
        """Lädt verlinkte Stunden-YAMLs für mehrere Tabellenzeilen gebündelt.

        Args:
            table: Planungstabelle mit Linkspalten.
            row_indices: Zielzeilen, deren Links aufgelöst und geladen werden.

        Returns:
            Mapping aus Zeilenindex auf geladene Stunden-YAML-Daten.
        """
        ...

    def load_lessons_for_all_rows(self, table: PlanTableData) -> dict[int, LessonYamlData]:
        """Lädt verlinkte Stunden-YAMLs für alle Tabellenzeilen gebündelt.

        Args:
            table: Planungstabelle, deren Zeilen vollständig ausgewertet werden.

        Returns:
            Mapping aus Zeilenindex auf geladene Stunden-YAML-Daten.
        """
        ...

    def save_lesson_yaml(self, lesson: LessonYamlData) -> None:
        """Speichert YAML-Daten einer Stunden-Datei.

        Args:
            lesson: Zu persistierende Stunden-YAML-Daten.
        """
        ...

    def create_linked_lesson_file(
        self,
        plan_table: PlanTableData,
        row_index: int,
        lesson_topic: str,
        default_hours: int,
    ) -> Path:
        """Erzeugt eine neue Stunden-Datei und verlinkt sie in der Planungstabelle.

        Args:
            plan_table: Zielplanung, in der der Link gesetzt wird.
            row_index: Tabellenzeile, die verlinkt wird.
            lesson_topic: Anfangsthema für die neue Stunde.
            default_hours: Initiale Dauer der Stunde.

        Returns:
            Pfad der erzeugten Stunden-Datei.
        """
        ...

    def set_lesson_markdown_sections(
        self,
        lesson_path: Path,
        inhalte_refs: list[str],
        methodik_refs: list[str],
    ) -> None:
        """Schreibt Inhalts-/Methodik-Sektionen in eine Stunden-Markdown-Datei.

        Args:
            lesson_path: Pfad zur Stunden-Datei.
            inhalte_refs: Referenzen für die Inhalte-Sektion.
            methodik_refs: Referenzen für die Methodik-Sektion.
        """
        ...


class CalendarRepository(Protocol):
    """Definiert den Vertrag für Calendar Repository.

    Die konkrete Implementierung wird in der Infrastructure-Schicht bereitgestellt.
    """

    def infer_term_from_date(self, start_date: date, calendar_dir: Path) -> str:
        """Leitet ein Halbjahr anhand eines Startdatums und Kalenderdaten ab.

        Args:
            start_date: Datum, für das ein Halbjahr bestimmt werden soll.
            calendar_dir: Verzeichnis mit Kalenderquellen.

        Returns:
            Halbjahres-Token (z. B. ``26-1`` oder ``26-2``).
        """
        ...

    def load_calendar_data(
        self,
        calendar_dir: Path,
        years: set[int],
    ) -> tuple[dict[date, str], list[PlanCalendarEvent], list[str]]:
        """Lädt Kalenderereignisse und Blöcke für angegebene Jahre.

        Args:
            calendar_dir: Verzeichnis mit Kalenderquellen.
            years: Zieljahre der Kalendereinträge.

        Returns:
            Tupel aus Tagesereignissen, Event-Blöcken und Warnungen.
        """
        ...


class CommandRepository(Protocol):
    """Definiert den Vertrag für Command Repository.

    Die konkrete Implementierung wird in der Infrastructure-Schicht bereitgestellt.
    """

    def read_file_content(self, path: Path) -> str | None:
        """Liest den Inhalt einer Datei für Command-basierte Änderungen.

        Args:
            path: Zielpfad der Datei.

        Returns:
            Dateiinhalt oder ``None``, wenn die Datei nicht vorhanden ist.
        """
        ...


class KompetenzkatalogRepository(Protocol):
    """Definiert den Vertrag fuer JSON-basierte Kompetenzkatalog-Quellen."""

    def default_manifest_path(self) -> Path:
        """Liefert den Standardpfad der Manifestdatei."""
        ...

    def load_manifest_entries_from(self, manifest_path: Path) -> tuple[KompetenzkatalogManifestEntry, ...]:
        """Liest alle Katalogeintraege aus einer Manifestdatei."""
        ...

    def list_manifest_entries(self) -> tuple[KompetenzkatalogManifestEntry, ...]:
        """Liest alle Katalogeintraege aus dem Standardmanifest."""
        ...

    def load_catalog_file(self, path: Path, profile_id: str) -> Kompetenzkatalog:
        """Laedt einen einzelnen Kompetenzkatalog fuer ein Profil aus einer JSON-Datei."""
        ...

    def write_file_content(self, path: Path, content: str | None) -> None:
        """Schreibt oder löscht Dateiinhalt für Undo/Redo-Deltas.

        Args:
            path: Zielpfad der Datei.
            content: Neuer Inhalt oder ``None`` zum Löschen.
        """
        ...


class LessonFileRepository(Protocol):
    """Definiert den Vertrag für dateibasierte Stunden-Dateioperationen.

    Die konkrete Implementierung wird in der Infrastructure-Schicht bereitgestellt.
    """

    def is_existing_markdown(self, path: Path) -> bool:
        """Prüft, ob ein Pfad auf eine vorhandene Markdown-Datei zeigt.

        Args:
            path: Zu prüfender Dateipfad.

        Returns:
            ``True``, wenn die Datei existiert, eine Datei ist und ``.md`` endet.
        """
        ...

    def ensure_directory(self, path: Path) -> None:
        """Stellt sicher, dass ein Verzeichnis existiert.

        Args:
            path: Zielverzeichnis.
        """
        ...

    def move_file(self, source: Path, target: Path) -> Path:
        """Verschiebt eine Datei auf einen Zielpfad.

        Args:
            source: Quellpfad.
            target: Zielpfad.

        Returns:
            Tatsächlicher Zielpfad nach der Verschiebung.
        """
        ...

    def read_file_content(self, path: Path) -> str:
        """Liest den Textinhalt einer Datei.

        Args:
            path: Dateipfad.

        Returns:
            Textinhalt der Datei.
        """
        ...

    def write_file_content(self, path: Path, content: str) -> None:
        """Schreibt Textinhalt in eine Datei.

        Args:
            path: Dateipfad.
            content: Zu schreibender Textinhalt.
        """
        ...

    def rename_file(self, source: Path, target: Path) -> Path:
        """Benennt eine Datei um.

        Args:
            source: Quellpfad.
            target: Zielpfad.

        Returns:
            Tatsächlicher Zielpfad.
        """
        ...

    def delete_file(self, path: Path) -> None:
        """Löscht eine Datei, falls vorhanden.

        Args:
            path: Dateipfad der zu löschenden Datei.
        """
        ...

    def unique_markdown_path(
        self,
        target_dir: Path,
        stem_base: str,
        current_path: Path | None = None,
    ) -> Path:
        """Ermittelt einen kollisionsfreien Markdown-Dateipfad.

        Args:
            target_dir: Zielverzeichnis.
            stem_base: Gewünschter Basis-Stem.
            current_path: Optionaler bestehender Pfad, der als gleichwertig gilt.

        Returns:
            Kollisionsfreier Dateipfad mit ``.md``.
        """
        ...


class SubjectSourceRepository(Protocol):
    """Definiert den Vertrag für Baukasten-Quellen je Fach.

    Die konkrete Implementierung wird in der Infrastructure-Schicht bereitgestellt.
    """

    def resolve_subject_sources(self, unterricht_dir: Path, subject_folder: str) -> tuple[list[str], list[str]]:
        """Lädt verfügbare Inhalte-/Methodik-Quellen für ein Fach.

        Args:
            unterricht_dir: Unterrichts-Basisverzeichnis.
            subject_folder: Normalisierter Fachordnername.

        Returns:
            Tupel aus (Inhalte-Stems, Methodik-Stems).
        """
        ...

    def invalidate_cache(self, unterricht_dir: Path | None = None, subject_folder: str | None = None) -> None:
        """Invalidiert den Baukasten-Quellcache gezielt oder vollständig.

        Args:
            unterricht_dir: Optionales Unterrichts-Basisverzeichnis.
            subject_folder: Optionaler Fachordner für gezielte Invalidierung.
        """
        ...


class LessonIndexRepository(Protocol):
    """Port für einen index-basierten, batch-fähigen Read-Repository für Stunden-Metadaten.

    Dieses Interface liefert nur Metadaten (z. B. `Stundenthema`, `Oberthema`, `mtime`, `path`)
    und erlaubt inkrementelle Invalidation/Rebuild-Operationen.
    """

    def load_lessons_metadata_for_rows(
        self, table: PlanTableData, row_indices: list[int]
    ) -> dict[int, dict[str, object]]:
        """Lädt Metadaten für angegebene Tabellenzeilen.

        Rückgabe ist ein Mapping `row_index -> metadata`, wobei das Metadaten-
        Objekt nur leichte Read-Informationen enthält (z. B. Thema/Oberthema/Pfad/mtime).
        """
        ...

    def load_lessons_metadata_for_all_rows(self, table: PlanTableData) -> dict[int, dict[str, object]]:
        """Lädt Metadaten für alle Zeilen der Planungstabelle in einem Batch."""
        ...

    def invalidate_index(self, unterricht_dir: Path | None = None, subject_folder: str | None = None) -> None:
        """Invalidiert indexinterne Caches gezielt oder vollständig.

        Ohne Parameter ist die Invalidierung global; mit Parametern auf Scope begrenzt.
        """
        ...

    def rebuild_index(self, unterricht_dir: Path) -> None:
        """Erzwingt einen Vollscan und Wiederaufbau des Lesson-Index.

        Diese Operation kann teuer sein und sollte nur über dedizierte Use Cases aufgerufen werden.
        """
        ...


class LessonSetupRepository(Protocol):
    """Definiert Dateisystem-Setup-Operationen für die Unterrichts-Neuanlage.

    Die konkrete Implementierung wird in der Infrastructure-Schicht bereitgestellt.
    """

    def validate_required_paths(self, base_dir: Path, calendar_dir: Path) -> None:
        """Prüft, ob Unterrichts- und Kalenderpfad vorhanden und gültig sind.

        Args:
            base_dir: Unterrichts-Basisverzeichnis.
            calendar_dir: Kalender-Basisverzeichnis.
        """
        ...

    def create_lesson_folder(self, base_dir: Path, folder_name: str) -> Path:
        """Erzeugt den Ziel-Unterrichtsordner.

        Args:
            base_dir: Unterrichts-Basisverzeichnis.
            folder_name: Name des neuen Unterrichtsordners.

        Returns:
            Pfad des erzeugten Unterrichtsordners.
        """
        ...

    def create_plan_markdown(self, lesson_dir: Path, folder_name: str) -> Path:
        """Erzeugt die initiale Plan-Markdown-Datei im Unterrichtsordner.

        Args:
            lesson_dir: Bereits angelegter Unterrichtsordner.
            folder_name: Basisname für die Plan-Datei.

        Returns:
            Pfad der erzeugten Plan-Markdown-Datei.
        """
        ...

    def rollback_lesson_folder(self, lesson_dir: Path) -> None:
        """Rollback für eine fehlgeschlagene Unterrichts-Neuanlage.

        Args:
            lesson_dir: Unterrichtsordner, der entfernt werden soll.
        """
        ...


class UbRepository(Protocol):
    """Vertrag fuer UB-Markdowndateien und UB-Uebersicht im zentralen Orga-Ordner."""

    def ensure_ub_root(self, workspace_root: Path) -> Path:
        """Stellt den zentralen UB-Ordner sicher und liefert seinen Pfad."""
        ...

    def ub_overview_path(self, workspace_root: Path) -> Path:
        """Liefert den Pfad der UB-Uebersichtsdatei."""
        ...

    def unique_ub_markdown_path(self, workspace_root: Path, stem: str) -> Path:
        """Ermittelt einen kollisionsfreien Pfad fuer eine UB-Markdowndatei."""
        ...

    def save_ub_markdown(
        self,
        ub_path: Path,
        yaml_data: dict[str, object],
        reflection_text: str,
        professional_steps: list[str],
        usable_resources: list[str],
    ) -> None:
        """Persistiert einen UB-Eintrag mit YAML-Frontmatter und Standardabschnitten."""
        ...

    def load_ub_markdown(self, ub_path: Path) -> tuple[dict[str, object], str]:
        """Liest YAML-Frontmatter und verbleibenden Markdown-Body einer UB-Datei."""
        ...

    def list_ub_markdown_files(self, workspace_root: Path) -> list[Path]:
        """Listet alle UB-Markdowndateien chronologisch nach Dateinamen."""
        ...

    def save_ub_overview(self, workspace_root: Path, markdown: str) -> Path:
        """Speichert die UB-Uebersichtsdatei und liefert ihren Pfad zurueck."""
        ...

    def load_ub_overview(self, workspace_root: Path) -> str:
        """Liest die UB-Uebersichtsdatei oder liefert einen leeren String."""
        ...

    def rename_ub_markdown(self, source: Path, target: Path) -> Path:
        """Benennt eine UB-Markdown-Datei um und liefert den finalen Zielpfad."""
        ...

    def delete_ub_markdown(self, path: Path) -> None:
        """Löscht eine UB-Markdown-Datei, falls vorhanden."""
        ...
