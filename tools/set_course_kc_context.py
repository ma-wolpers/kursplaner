"""Setzt ``Bundesland``/``Schulform`` in den Plan-Dateien aller Kurse (aktive und archivierte).

Kurse tragen seit 2026-11-04 ihren KC-Kontext (siehe
``kursplaner/core/domain/course_kc_context.py``); ältere Plan-Dateien haben die
Felder noch nicht. Das Werkzeug schreibt sie chirurgisch über
``FileSystemPlanRepository.update_plan_kc_context`` – alle anderen Zeilen
bleiben unverändert.

Standardmäßig werden nur fehlende Felder ergänzt; ``--overwrite`` ersetzt auch
vorhandene Werte. Ohne ``--bundesland``/``--schulform`` gelten die Standardwerte
aus den Einstellungen („Neue Kurse“). Die Ausgabe nennt nur Anzahlen, keine
Kursnamen.

Aufruf vom Repo-Wurzelverzeichnis::

    python -m tools.set_course_kc_context --dry-run
    python -m tools.set_course_kc_context [--bundesland Niedersachsen] [--schulform IGS]
        [--overwrite] [--no-archive] [--unterricht-dir PFAD]

WICHTIG: Das Werkzeug legt selbst kein Backup an – vorher den Vault sichern.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

from kursplaner.core.config.ui_preferences_store import load_course_kc_defaults
from kursplaner.core.domain.course_kc_context import (
    BUNDESLAND_KEY,
    SCHULFORM_KEY,
    CourseKcContext,
    course_kc_context,
)
from kursplaner.core.domain.yaml_registry import PLAN_METADATA_SCHEMA, parse_yaml_frontmatter
from kursplaner.infrastructure.repositories.plan_repository import FileSystemPlanRepository
from tools.vault_courses import iter_course_dirs, resolve_unterricht_dir


@dataclass
class KcContextRun:
    """Ergebnis eines Laufs (nur Anzahlen und Fehler, keine Kursinhalte)."""

    changed: int = 0
    unchanged: int = 0
    errors: list[str] = field(default_factory=list)


def _target_for(plan_path: Path, wanted: CourseKcContext, *, overwrite: bool) -> CourseKcContext:
    """Zu schreibender Kontext: ohne *overwrite* nur Felder, die in der Datei noch fehlen."""
    if overwrite:
        return wanted
    data, _body = parse_yaml_frontmatter(plan_path.read_text(encoding="utf-8"), PLAN_METADATA_SCHEMA, str(plan_path))
    present = course_kc_context(data)
    return CourseKcContext(
        wanted.bundesland if present.bundesland is None else None,
        wanted.schulform if present.schulform is None else None,
    )


def run(
    unterricht_dir: Path,
    wanted: CourseKcContext,
    *,
    include_archive: bool,
    overwrite: bool = False,
    dry_run: bool = False,
) -> KcContextRun:
    """Setzt den KC-Kontext in allen Plan-Dateien unter *unterricht_dir*.

    Args:
        unterricht_dir: Wurzel der aktiven Kurse.
        wanted: Zu setzende Werte (``None``-Felder werden nicht angefasst).
        include_archive: Archivierte Kurse mit bearbeiten.
        overwrite: Vorhandene Werte ersetzen statt nur fehlende zu ergänzen.
        dry_run: Nichts schreiben, nur zählen.
    """
    result = KcContextRun()
    repo = FileSystemPlanRepository()
    for course_dir in iter_course_dirs(unterricht_dir, include_archive=include_archive):
        plan_path = course_dir / f"{course_dir.name}.md"
        try:
            target = _target_for(plan_path, wanted, overwrite=overwrite)
            if target == CourseKcContext():
                result.unchanged += 1
                continue
            if dry_run:
                result.changed += 1
                continue
            if repo.update_plan_kc_context(plan_path, target):
                result.changed += 1
            else:
                result.unchanged += 1
        except (OSError, RuntimeError) as exc:
            result.errors.append(f"{plan_path}: {exc}")
    return result


def main(argv: list[str] | None = None) -> int:
    """CLI-Einstiegspunkt; Exit-Code 1 bei Fehlern oder fehlenden Werten."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bundesland", default=None, help="Standard: Einstellung „Standard-Bundesland“.")
    parser.add_argument("--schulform", default=None, help="Standard: Einstellung „Standard-Schulform“.")
    parser.add_argument("--overwrite", action="store_true", help="Vorhandene Werte ersetzen.")
    parser.add_argument("--no-archive", action="store_true", help="Archivierte Kurse auslassen.")
    parser.add_argument("--dry-run", action="store_true", help="Nur zählen, nichts schreiben.")
    parser.add_argument("--unterricht-dir", type=Path, default=None, help="Override des Unterrichtsordners.")
    args = parser.parse_args(argv)

    defaults = load_course_kc_defaults()
    wanted = course_kc_context(
        {BUNDESLAND_KEY: args.bundesland or defaults.bundesland, SCHULFORM_KEY: args.schulform or defaults.schulform}
    )
    if wanted == CourseKcContext():
        print("Weder Bundesland noch Schulform angegeben (auch keine Standardwerte in den Einstellungen).")
        return 1
    unterricht_dir = resolve_unterricht_dir(args.unterricht_dir)
    if not unterricht_dir.is_dir():
        print(f"Unterrichtsordner nicht gefunden: {unterricht_dir}")
        return 1

    result = run(
        unterricht_dir, wanted, include_archive=not args.no_archive, overwrite=args.overwrite, dry_run=args.dry_run
    )
    verb = "würden geändert" if args.dry_run else "geändert"
    print(
        f"Bundesland={wanted.bundesland} Schulform={wanted.schulform}: {result.changed} Kurse {verb}, "
        f"{result.unchanged} unverändert, {len(result.errors)} Fehler."
    )
    for error in result.errors:
        print(f"  {error}")
    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())
