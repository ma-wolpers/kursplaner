"""Einmal-Migration: UB-Entwicklungslisten vom Body ins Frontmatter.

Bisher standen die Listen einer UB-Datei als Abschnitte im Text::

    ## Professionalisierungsschritte
    - …
    ## Nutzbare Ressourcen
    - …

Jetzt sind sie YAML-Listen im Frontmatter (``Baustellen``/``Ressourcen``,
`unterrichtsbesuch_policy.UB_DEVELOPMENT_FIELDS`). Das Tool liest die alten
Abschnitte, prüft jeden Eintrag gegen die Listen-Invariante, schreibt die Listen
über das UB-Repository ins Frontmatter und entfernt die beiden Abschnitte; der
übrige Body (Reflexion, Langentwurf-Abschnitte, eigener Text) bleibt wörtlich.

Leere Platzhalter-Bullets (``- ``) der alten Vorlage ergeben keine Einträge.
Mehrfach ausführbar: Dateien ohne alte Abschnitte werden übersprungen. Hat eine
Datei schon Einträge im Frontmatter **und** alte Abschnitte, bricht das Tool für
diese Datei ab, statt zu raten.

Usage (vom Repo-Wurzelverzeichnis)::

    python -m tools.migrate_ub_development_frontmatter [--dry-run] [--ub-dir PFAD]

Ohne ``--ub-dir`` wird der UB-Ordner aus dem konfigurierten Unterrichtsordner abgeleitet.
Exit-Code 0 bei Erfolg, 1 bei Problemen.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.config.path_store import infer_workspace_root_from_path
from kursplaner.core.domain.list_cell_text import list_field_violations
from kursplaner.core.domain.markdown_sections import extract_bullet_items, extract_section, replace_section
from kursplaner.core.domain.unterrichtsbesuch_policy import (
    UB_OVERVIEW_FILE_NAME,
    UB_RESOURCES_FIELD,
    UB_ROOT_RELATIVE_PARTS,
    UB_STEPS_FIELD,
    ub_development_lists,
    with_ub_development_list,
)
from kursplaner.infrastructure.repositories.ub_repository import FileSystemUbRepository
from tools.vault_courses import resolve_unterricht_dir

LEGACY_SECTIONS: dict[str, str] = {
    "Professionalisierungsschritte": UB_STEPS_FIELD,
    "Nutzbare Ressourcen": UB_RESOURCES_FIELD,
}
"""Alte ``##``-Abschnittsüberschrift → neues Frontmatter-Feld."""


@dataclass(frozen=True)
class MigrationPlan:
    """Geplante Änderung einer UB-Datei.

    Attributes:
        path: UB-Datei.
        lists: Feld → Einträge aus den alten Abschnitten.
        body: Body ohne die alten Abschnitte.
        problem: Grund, warum die Datei nicht migriert wird (leer = in Ordnung).
    """

    path: Path
    lists: dict[str, list[str]]
    body: str
    problem: str = ""


def plan_file(repo: FileSystemUbRepository, path: Path) -> MigrationPlan | None:
    """Plant die Migration einer UB-Datei.

    Args:
        repo: UB-Repository (Lesen über den regulären Parser).
        path: UB-Datei.

    Returns:
        ``None``, wenn die Datei keine alten Abschnitte hat (auch andere Notizen im
        UB-Ordner ohne UB-Frontmatter); sonst den Plan (ggf. mit ``problem``).
    """
    try:
        yaml_data, body = repo.load_ub_markdown(path)
    except (OSError, RuntimeError, UnicodeDecodeError) as exc:
        text = path.read_text(encoding="utf-8", errors="replace")
        if not any(extract_section(text, heading, target_level=2) is not None for heading in LEGACY_SECTIONS):
            return None
        return MigrationPlan(path=path, lists={}, body="", problem=f"nicht lesbar: {exc}")

    lists: dict[str, list[str]] = {}
    new_body = body
    for heading, field in LEGACY_SECTIONS.items():
        section = extract_section(new_body, heading, target_level=2, stop_at_level=2)
        if section is None:
            continue
        lists[field] = [item.strip() for item in extract_bullet_items(section) if item.strip()]
        new_body = replace_section(new_body, heading, [], level=2)
    if not lists:
        return None

    try:
        existing = dict(zip((UB_STEPS_FIELD, UB_RESOURCES_FIELD), ub_development_lists(yaml_data)))
    except RuntimeError as exc:
        return MigrationPlan(path=path, lists=lists, body=new_body, problem=str(exc))
    if any(existing[field] for field in lists):
        return MigrationPlan(
            path=path, lists=lists, body=new_body, problem="Frontmatter hat schon Einträge und alte Abschnitte"
        )
    for field, entries in lists.items():
        violations = list_field_violations(entries, allow_scalar=False)
        if violations:
            entry, reason = violations[0]
            return MigrationPlan(path=path, lists=lists, body=new_body, problem=f"{field}: {entry!r}: {reason}")
    return MigrationPlan(path=path, lists=lists, body=new_body.rstrip("\n") + "\n")


def apply_plan(repo: FileSystemUbRepository, plan: MigrationPlan) -> None:
    """Schreibt die Listen ins Frontmatter und den bereinigten Body.

    Args:
        repo: UB-Repository.
        plan: Plan ohne ``problem``.
    """
    yaml_data, _body = repo.load_ub_markdown(plan.path)
    for field, entries in plan.lists.items():
        yaml_data = with_ub_development_list(yaml_data, field, entries)
    repo.save_ub_markdown(plan.path, yaml_data, plan.body)


def ub_files(ub_dir: Path) -> list[Path]:
    """UB-Dateien (``*.md`` ohne Übersicht) eines Ordners, nach Namen sortiert."""
    return sorted(
        (path for path in ub_dir.glob("*.md") if path.name != UB_OVERVIEW_FILE_NAME),
        key=lambda item: item.name.lower(),
    )


def default_ub_dir() -> Path:
    """UB-Ordner aus dem konfigurierten Unterrichtsordner (wie in der App)."""
    workspace_root = infer_workspace_root_from_path(resolve_unterricht_dir(None))
    return workspace_root.joinpath(*UB_ROOT_RELATIVE_PARTS)


def main(argv: list[str] | None = None) -> int:
    """CLI-Einstiegspunkt.

    Args:
        argv: Argumente (Standard: ``sys.argv[1:]``).

    Returns:
        Exit-Code: 0 bei Erfolg, 1 bei fehlendem Ordner oder Problemdateien.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Nur planen, nichts schreiben.")
    parser.add_argument("--ub-dir", type=Path, default=None, help="UB-Ordner (Standard: aus der Pfad-Konfiguration).")
    args = parser.parse_args(argv)

    ub_dir = args.ub_dir.expanduser().resolve() if args.ub_dir else default_ub_dir()
    if not ub_dir.is_dir():
        print(f"UB-Ordner nicht gefunden: {ub_dir}")
        return 1

    repo = FileSystemUbRepository()
    plans = [plan for path in ub_files(ub_dir) if (plan := plan_file(repo, path)) is not None]
    problems = [plan for plan in plans if plan.problem]
    ready = [plan for plan in plans if not plan.problem]
    for plan in ready:
        counts = ", ".join(f"{field}: {len(entries)}" for field, entries in plan.lists.items())
        print(f"{'würde migrieren' if args.dry_run else 'migriert'}: {plan.path.name} ({counts})")
        if not args.dry_run:
            apply_plan(repo, plan)
    for plan in problems:
        print(f"übersprungen: {plan.path.name}: {plan.problem}")
    print(f"{len(ready)} Datei(en) {'zu migrieren' if args.dry_run else 'migriert'}, {len(problems)} Problem(e).")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
