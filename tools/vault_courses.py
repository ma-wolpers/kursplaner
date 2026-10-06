"""Gemeinsame Kurs-Iteration für die Upgrade-/Prüftools in ``tools/``.

Liefert die Kursordner unter dem konfigurierten Unterrichtsordner (und
optional dem Archiv ``_ALT/Kursordner``) sowie deren Stunden- und
Sequenzdateien. Gleiches Muster wie ``tools/migrate_plan_table_schema.py``
(``<Kursordner>/<Kursordner>.md`` = Kursplan), hier als wiederverwendbares
Modul für ``check_list_field_entries`` (ursprünglich auch für das inzwischen entfernte
Migrationswerkzeug ``migrate_sequence_focus_competencies``).

Aufruf der Tools immer vom Repo-Wurzelverzeichnis als Modul
(``python -m tools.<name>``), damit ``kursplaner`` und ``tools`` importierbar sind.
"""

from __future__ import annotations

from pathlib import Path

from kursplaner.core.config.path_store import UNTERRICHT_DIR_KEY, load_path_values, resolve_path_value
from kursplaner.core.domain.course_lifecycle import course_archive_root
from kursplaner.core.domain.lesson_directory import managed_lesson_dir_names
from kursplaner.core.domain.lesson_files import list_lesson_files
from kursplaner.core.domain.sequence_planning import SEQUENCE_DIR_NAME, list_sequence_document_paths


def resolve_unterricht_dir(override: Path | None) -> Path:
    """Ermittelt den Unterrichtsordner (Override oder konfigurierter Pfad).

    Args:
        override: Optionaler Pfad von der Kommandozeile (z. B. eine Vault-Kopie
            oder ein synthetisches Testverzeichnis).

    Returns:
        Der aufgelöste Unterrichtsordner.
    """
    if override is not None:
        return override.expanduser().resolve()
    return resolve_path_value(load_path_values()[UNTERRICHT_DIR_KEY])


def iter_course_dirs(unterricht_dir: Path, *, include_archive: bool) -> list[Path]:
    """Listet alle Kursordner (Ordner mit gleichnamiger Plan-Datei).

    Args:
        unterricht_dir: Wurzel der aktiven Kurse.
        include_archive: Ob archivierte Kurse (``course_archive_root``) mit
            durchlaufen werden.

    Returns:
        Die Kursordner, je Wurzel alphabetisch (case-insensitiv) sortiert.
    """
    roots = [unterricht_dir]
    if include_archive:
        archive_root = course_archive_root(unterricht_dir)
        if archive_root.is_dir():
            roots.append(archive_root)

    course_dirs: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir(), key=lambda item: item.name.lower()):
            if child.is_dir() and (child / f"{child.name}.md").is_file():
                course_dirs.append(child)
    return course_dirs


def iter_lesson_files(course_dir: Path) -> list[Path]:
    """Listet alle Stundendateien (``.md``/``.ebw``) der verwalteten Stundenordner eines Kurses.

    Args:
        course_dir: Ein Kursordner aus `iter_course_dirs`.

    Returns:
        Die Stundendateien aus ``Einheiten``/``Alteinheiten`` (soweit vorhanden).
    """
    files: list[Path] = []
    for dir_name in managed_lesson_dir_names():
        lesson_dir = course_dir / dir_name
        if lesson_dir.is_dir():
            files.extend(list_lesson_files(lesson_dir))
    return files


def iter_sequence_files(course_dir: Path) -> list[Path]:
    """Listet alle Sequenzdateien eines Kurses (Ordner ``Sequenzen``).

    Args:
        course_dir: Ein Kursordner aus `iter_course_dirs`.

    Returns:
        Die Sequenz-Markdown-Dateien (leer, wenn der Ordner fehlt).
    """
    sequence_dir = course_dir / SEQUENCE_DIR_NAME
    if not sequence_dir.is_dir():
        return []
    return list_sequence_document_paths(sequence_dir)
