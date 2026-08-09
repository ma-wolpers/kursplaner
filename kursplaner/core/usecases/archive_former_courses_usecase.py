"""Automatische Archivierung ehemaliger Kurse.

Verschiebt Kursordner zwischen dem aktiven Unterrichtsordner und dem
Kurs-Archiv (`unterricht_dir/_ALT/Kursordner`), abhängig davon, ob
`course_lifecycle.is_former_course` für den jeweiligen Kurs zutrifft.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from kursplaner.core.domain.course_lifecycle import (
    course_archive_root,
    is_archived_course_path,
    is_former_course,
)
from kursplaner.core.ports.repositories import LessonFileRepository, PlanRepository


@dataclass(frozen=True)
class ArchiveFormerCoursesResult:
    """Ergebnis eines Archivierungslaufs."""

    archived: list[Path] = field(default_factory=list)
    restored: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class ArchiveFormerCoursesUseCase:
    """Verschiebt Kursordner automatisch in/aus dem Kurs-Archiv.

    Nutzt ausschließlich `course_lifecycle.is_former_course` als Entscheidung -
    keine eigene Heuristik (siehe dortige Docstring-Begründung).
    """

    def __init__(self, plan_repo: PlanRepository, lesson_file_repo: LessonFileRepository):
        """Bindet Port-basierte Abhängigkeiten für Planzugriff und Dateisystemoperationen."""
        self._plan_repo = plan_repo
        self._lesson_file_repo = lesson_file_repo

    def execute(
        self,
        unterricht_dir: Path,
        *,
        today: date | None = None,
        skip_paths: frozenset[Path] = frozenset(),
    ) -> ArchiveFormerCoursesResult:
        """Prüft alle Kurse und verschiebt sie bei Bedarf ins/aus dem Archiv.

        Args:
            unterricht_dir: Aktiver Unterrichts-Basisordner.
            today: Referenzdatum; Standard ist das heutige Datum.
            skip_paths: Absolute, aufgelöste Plan-Dateipfade, die nie
                verschoben werden (z. B. der aktuell geöffnete Kurs - ein
                Verschieben während der offenen Ansicht würde den geladenen
                Pfad unter der Nutzung entziehen).

        Returns:
            Zusammenfassung der verschobenen Kurse und aufgetretenen Fehler.
        """
        reference_day = today or date.today()
        archived: list[Path] = []
        restored: list[Path] = []
        errors: list[str] = []
        moved_any = False

        for markdown in self._plan_repo.list_plan_markdown_files(unterricht_dir):
            if markdown.resolve() in skip_paths:
                continue

            try:
                table = self._plan_repo.load_plan_table(markdown)
            except Exception as exc:
                errors.append(f"{markdown.name}: {exc}")
                continue

            former = is_former_course(table, reference_day)
            archived_now = is_archived_course_path(markdown, unterricht_dir)
            if former == archived_now:
                continue

            course_folder = markdown.parent
            if former:
                target = course_archive_root(unterricht_dir) / course_folder.name
            else:
                target = unterricht_dir / course_folder.name

            try:
                self._lesson_file_repo.move_directory(course_folder, target)
            except Exception as exc:
                errors.append(f"{course_folder.name}: {exc}")
                continue

            moved_any = True
            (archived if former else restored).append(target / markdown.name)

        if moved_any:
            self._plan_repo.invalidate_plan_list_cache(unterricht_dir)

        return ArchiveFormerCoursesResult(archived=archived, restored=restored, errors=errors)
