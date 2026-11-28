"""Einmal-Aufräumtool: entfernt ``Ressourcen``/``Baustellen`` aus Stundendateien.

Entwicklungsfelder gehören allein zur UB-Datei (dort ``Baustellen``/``Ressourcen``
im Frontmatter). Hospitationen trugen früher eigene gleichnamige Listen in der
Stunden-YAML; der Kursplaner kennt sie nicht mehr, `canonicalize_lesson_yaml`
verwirft sie beim nächsten Speichern, und ``tools/ci/check_einheiten_schema.py``
meldet sie bis dahin als unerlaubte Felder. Auf Wunsch der Nutzerin werden die
Einträge ersatzlos gelöscht.

Das Tool lädt und speichert jede betroffene Datei über das Lesson-Repository –
derselbe Kanonisierungsweg wie in der App, ohne eigene YAML-Regeln.

Usage (vom Repo-Wurzelverzeichnis)::

    python -m tools.remove_hospitation_development_fields [--dry-run] [--no-archive] [--unterricht-dir PFAD]

Ausgabe: Anzahl und Pfade der betroffenen Dateien, nie ihre Inhalte.
Exit-Code 0 bei Erfolg, 1 bei fehlendem Ordner oder nicht speicherbaren Dateien.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kursplaner.infrastructure.repositories.lesson_repository import FileSystemLessonRepository
from tools.vault_courses import iter_course_dirs, iter_lesson_files, resolve_unterricht_dir

REMOVED_KEYS: tuple[str, ...] = ("Ressourcen", "Baustellen")
"""Frühere Hospitationsfelder, die keine Stunden-YAML mehr tragen darf."""


def affected_lesson_files(unterricht_dir: Path, *, include_archive: bool) -> list[Path]:
    """Stundendateien, deren rohes Frontmatter einen der `REMOVED_KEYS` enthält.

    Args:
        unterricht_dir: Unterrichtsordner.
        include_archive: Ob archivierte Kurse mit durchsucht werden.

    Returns:
        Betroffene Dateien in Kurs- und Dateireihenfolge.
    """
    repo = FileSystemLessonRepository()
    affected: list[Path] = []
    for course_dir in iter_course_dirs(unterricht_dir, include_archive=include_archive):
        for path in iter_lesson_files(course_dir):
            try:
                raw = repo.load_raw_lesson_frontmatter(path)
            except (OSError, RuntimeError, UnicodeDecodeError):
                continue
            if any(key in raw for key in REMOVED_KEYS):
                affected.append(path)
    return affected


def remove_fields(paths: list[Path]) -> list[tuple[Path, str]]:
    """Lädt und speichert jede Datei kanonisch; die Altfelder fallen dabei weg.

    Args:
        paths: Betroffene Dateien aus `affected_lesson_files`.

    Returns:
        ``(Pfad, Fehlertext)`` für Dateien, die nicht gespeichert werden konnten.
    """
    repo = FileSystemLessonRepository()
    failures: list[tuple[Path, str]] = []
    for path in paths:
        try:
            repo.save_lesson_yaml(repo.load_lesson_yaml(path))
        except (OSError, RuntimeError, ValueError) as exc:
            failures.append((path, str(exc)))
    return failures


def main(argv: list[str] | None = None) -> int:
    """CLI-Einstiegspunkt.

    Args:
        argv: Argumente (Standard: ``sys.argv[1:]``).

    Returns:
        Exit-Code: 0 bei Erfolg, 1 bei fehlendem Ordner oder Speicherfehlern.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Nur zählen, nichts schreiben.")
    parser.add_argument("--no-archive", action="store_true", help="Archivierte Kurse auslassen.")
    parser.add_argument("--unterricht-dir", type=Path, default=None, help="Override des Unterrichtsordners.")
    args = parser.parse_args(argv)

    unterricht_dir = resolve_unterricht_dir(args.unterricht_dir)
    if not unterricht_dir.is_dir():
        print(f"Unterrichtsordner nicht gefunden: {unterricht_dir}")
        return 1

    paths = affected_lesson_files(unterricht_dir, include_archive=not args.no_archive)
    for path in paths:
        print(path)
    print(f"{len(paths)} Datei(en) mit {' / '.join(REMOVED_KEYS)}.")
    if args.dry_run or not paths:
        return 0

    failures = remove_fields(paths)
    for path, message in failures:
        print(f"Nicht gespeichert: {path}: {message}")
    print(f"{len(paths) - len(failures)} Datei(en) bereinigt.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
