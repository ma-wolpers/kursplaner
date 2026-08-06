"""Migration: rename UB files from ``UB yy-mm-dd Titel`` to ``ub yy-mm-dd``.

Updates the 10 existing UB files in the vault, fixes all ``Unterrichtsbesuch``
wikilinks in lesson Einheit files (adding mandatory YAML quoting), and
regenerates ``UB Übersicht.md``.

Usage::

    python tools/migrate_ub_filenames.py [--dry-run]

The script is idempotent: re-running after a successful migration finds no
old-format files and exits cleanly without making changes.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from kursplaner.core.config.path_store import (
    UNTERRICHT_DIR_KEY,
    infer_workspace_root_from_path,
    load_path_values,
    resolve_path_value,
)
from kursplaner.core.domain.unterrichtsbesuch_policy import UB_OVERVIEW_FILE_NAME, UB_ROOT_RELATIVE_PARTS, UbStem
from kursplaner.core.usecases.ub_markdown_sections import parse_list_section, parse_reflection
from kursplaner.core.usecases.ub_overview_builder import build_ub_overview_markdown
from kursplaner.infrastructure.repositories.ub_repository import FileSystemUbRepository

_OLD_UB_STEM_RE = re.compile(r"^UB\s+(\d{2}-\d{2}-\d{2})(\s+.+)?$")

_NON_MIGRATED_NAMES = frozenset(
    {
        UB_OVERVIEW_FILE_NAME,
        "BUB.md",
        "Pädagogische UB.md",
    }
)


def _extract_old_date_token(stem: str) -> str | None:
    """Extracts yy-mm-dd from an old-format stem ``UB yy-mm-dd Titel``."""
    match = _OLD_UB_STEM_RE.match(str(stem or "").strip())
    return match.group(1) if match else None


def _build_rename_map(ub_root: Path) -> dict[str, str]:
    """Scans ub_root and builds {old_stem: new_stem} for all old-format UB files.

    Only files whose names start with ``UB `` and contain a parseable
    ``yy-mm-dd`` date token are included.  Files in ``_NON_MIGRATED_NAMES``
    and files already in the new format are skipped.

    Returns:
        Mapping from old stem (no extension) to new stem (no extension).
    """
    rename_map: dict[str, str] = {}
    for ub_path in sorted(ub_root.glob("*.md")):
        if ub_path.name in _NON_MIGRATED_NAMES or ub_path.name.startswith("UBplus"):
            continue
        date_token = _extract_old_date_token(ub_path.stem)
        if date_token is None:
            continue
        new_stem = str(UbStem(date_token=date_token))
        rename_map[ub_path.stem] = new_stem
    return rename_map


def _check_collisions(rename_map: dict[str, str]) -> None:
    """Aborts with an error message if two old stems would map to the same new stem."""
    seen: dict[str, str] = {}
    for old_stem, new_stem in rename_map.items():
        if new_stem in seen:
            print(f"FEHLER: Kollision – '{old_stem}' und '{seen[new_stem]}' ergeben beide '{new_stem}'.")
            sys.exit(1)
        seen[new_stem] = old_stem


def _rename_and_fix_ub_files(
    ub_repo: FileSystemUbRepository,
    ub_root: Path,
    rename_map: dict[str, str],
) -> None:
    """Renames each UB file and re-saves it via the repository.

    Re-saving through ``FileSystemUbRepository.save_ub_markdown`` ensures that
    all YAML wikilink values are written with mandatory double quotes, fixing
    any pre-existing quoting issues in the ``Einheit`` field.

    Args:
        ub_repo: Repository for UB file I/O.
        ub_root: Directory containing the UB files.
        rename_map: Mapping from old stem to new stem.
    """
    for old_stem, new_stem in sorted(rename_map.items()):
        old_path = ub_root / f"{old_stem}.md"
        new_path = ub_root / f"{new_stem}.md"

        if not old_path.exists():
            print(f"  WARNUNG: Datei nicht gefunden, übersprungen: {old_path.name}")
            continue

        ub_yaml, ub_body = ub_repo.load_ub_markdown(old_path)
        final_path = ub_repo.rename_ub_markdown(old_path, new_path)
        ub_repo.save_ub_markdown(
            final_path,
            ub_yaml,
            reflection_text=parse_reflection(ub_body),
            professional_steps=parse_list_section(ub_body, "Professionalisierungsschritte"),
            usable_resources=parse_list_section(ub_body, "Nutzbare Ressourcen"),
        )
        print(f"  {old_path.name}  →  {final_path.name}")


def _update_unterrichtsbesuch_links(unterricht_root: Path, rename_map: dict[str, str]) -> int:
    """Rewrites ``Unterrichtsbesuch`` YAML fields in lesson Einheit files.

    For each lesson file that contains a reference to an old-format UB stem,
    the line is rewritten to ``Unterrichtsbesuch: "[[new_stem]]"`` — always
    with double quotes, regardless of whether the original was quoted or not.

    The function only rewrites within the YAML frontmatter (lines between the
    first two ``---`` delimiters) to avoid false matches in body text.

    Args:
        unterricht_root: Root of the Unterricht directory tree.
        rename_map: Mapping from old UB stem to new UB stem.

    Returns:
        Number of lesson files that were updated.
    """
    updated = 0
    for lesson_path in sorted(unterricht_root.rglob("Einheiten/*.md")):
        text = lesson_path.read_text(encoding="utf-8")
        new_text = _rewrite_frontmatter_ub_link(text, rename_map)
        if new_text != text:
            lesson_path.write_text(new_text, encoding="utf-8")
            updated += 1
            print(f"  Link aktualisiert: {lesson_path.name}")
    return updated


def _rewrite_frontmatter_ub_link(text: str, rename_map: dict[str, str]) -> str:
    """Returns ``text`` with any matching ``Unterrichtsbesuch`` link rewritten.

    Only operates within the YAML frontmatter block (between the first pair of
    ``---`` delimiters).  Handles both quoted and unquoted wiki-link values.

    Args:
        text: Full file text including frontmatter.
        rename_map: Mapping from old UB stem to new UB stem.

    Returns:
        Potentially modified text.
    """
    if not text.startswith("---"):
        return text

    end = text.find("\n---", 4)
    if end == -1:
        return text

    frontmatter = text[: end + 4]
    body = text[end + 4 :]

    new_frontmatter = frontmatter
    for old_stem, new_stem in rename_map.items():
        escaped = re.escape(old_stem)
        pattern = re.compile(
            r'(^Unterrichtsbesuch:\s*)"?\[\[' + escaped + r'\]\]"?\s*$',
            re.MULTILINE,
        )
        replacement = f'\\1"[[{new_stem}]]"'
        new_frontmatter = pattern.sub(replacement, new_frontmatter)

    return new_frontmatter + body


def migrate(workspace_root: Path, unterricht_root: Path, *, dry_run: bool) -> None:
    """Runs the full UB filename migration.

    Steps:
    1. Build a rename map from old-format to new-format UB stems.
    2. Check for stem collisions (abort if found).
    3. Print the rename plan.
    4. If not dry-run: rename UB files, update lesson links, rebuild overview.

    Args:
        workspace_root: Root of the workspace containing the ``7thVault`` subdirectory.
        unterricht_root: Directory containing course plan subdirectories with ``Einheiten``.
        dry_run: If True, only print the plan without writing any files.
    """
    ub_repo = FileSystemUbRepository()
    ub_root = ub_repo.ensure_ub_root(workspace_root)

    rename_map = _build_rename_map(ub_root)
    if not rename_map:
        print("Keine UB-Dateien mit altem Format gefunden. Nichts zu tun.")
        return

    _check_collisions(rename_map)

    print(f"Rename-Plan ({len(rename_map)} Dateien):")
    for old_stem in sorted(rename_map):
        print(f"  {old_stem}.md  →  {rename_map[old_stem]}.md")

    if dry_run:
        print("\n[dry-run] Keine Änderungen vorgenommen.")
        return

    print("\nUmbenennen der UB-Dateien ...")
    _rename_and_fix_ub_files(ub_repo, ub_root, rename_map)

    print("\nAktualisierung der Unterrichtsbesuch-Links ...")
    updated_count = _update_unterrichtsbesuch_links(unterricht_root, rename_map)

    print("\nNeu-Erstellung der UB Übersicht ...")
    overview_md = build_ub_overview_markdown(ub_repo, workspace_root)
    ub_repo.save_ub_overview(workspace_root, overview_md)

    print(f"\nFertig. {updated_count} Lektionsdatei(en) aktualisiert.")


def main() -> None:
    """Einstiegspunkt für das Migrations-Skript."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Zeige den Plan ohne Dateien zu schreiben.",
    )
    parser.add_argument(
        "--unterricht-dir",
        type=Path,
        default=None,
        help="Unterrichtsordner (Standard: aus Anwendungskonfiguration).",
    )
    args = parser.parse_args()

    if args.unterricht_dir is not None:
        unterricht_root = args.unterricht_dir.expanduser().resolve()
    else:
        path_values = load_path_values()
        unterricht_root = resolve_path_value(path_values[UNTERRICHT_DIR_KEY])

    if not unterricht_root.exists():
        print(f"FEHLER: Unterrichtsordner nicht gefunden: {unterricht_root}")
        sys.exit(1)

    workspace_root = infer_workspace_root_from_path(unterricht_root)
    print(f"Workspace:      {workspace_root}")
    print(f"Unterricht:     {unterricht_root}")
    print()

    migrate(workspace_root, unterricht_root, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
