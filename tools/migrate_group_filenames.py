from __future__ import annotations

from pathlib import Path

from kursplaner.core.config.path_store import UNTERRICHT_DIR_KEY, load_path_values, resolve_path_value
from kursplaner.core.domain.plan_table import sanitize_hour_title
from kursplaner.infrastructure.repositories.plan_table_file_repository import (
    get_row_link_path,
    load_last_plan_table,
    load_linked_lesson_yaml,
    save_plan_table,
)


def is_lzk(content: str, topic: str) -> bool:
    """Prüft eine fachliche Bedingung in dem Modul.

    Args:
        content: Inhaltstext, der fachlich weiterverarbeitet wird.
        topic: Eingabewert für diesen Verarbeitungsschritt.

    Returns:
        Fachliches Ergebnis der Verarbeitung.
    """
    combined = f"{content} {topic}".lower()
    return "lzk" in combined


def unique_target(original: Path, desired_stem: str) -> Path:
    """Verarbeitet den Schritt unique target im Kontext von dem Modul.

    Args:
        original: Eingabewert für diesen Verarbeitungsschritt.
        desired_stem: Eingabewert für diesen Verarbeitungsschritt.

    Returns:
        Fachliches Ergebnis der Verarbeitung.
    """
    desired = original.parent / f"{desired_stem}.md"
    if not desired.exists() or desired.resolve() == original.resolve():
        return desired

    counter = 2
    while True:
        candidate = original.parent / f"{desired_stem} {counter}.md"
        if not candidate.exists() or candidate.resolve() == original.resolve():
            return candidate
        counter += 1


def migrate_plan(plan_path: Path) -> tuple[int, int]:
    """Verarbeitet den Schritt migrate plan im Kontext von dem Modul.

    Args:
        plan_path: Dateipfad für den betroffenen Lese-/Schreibvorgang.

    Returns:
        Fachliches Ergebnis der Verarbeitung.
    """
    table = load_last_plan_table(plan_path)

    group = str(table.metadata.get("Lerngruppe", "gruppe"))
    group = sanitize_hour_title(group.replace("[[", "").replace("]]", "").strip()) or "gruppe"

    changed_rows = 0
    renamed_files = 0

    for row_index, row in enumerate(table.rows):
        if len(row) < 3:
            continue

        content = row[2].strip()
        link = get_row_link_path(table, row_index)
        if not isinstance(link, Path) or not link.exists():
            continue

        lesson = load_linked_lesson_yaml(link)
        topic = sanitize_hour_title(str(lesson.data.get("Stundenthema", "")).strip())
        if not topic:
            continue

        if is_lzk(content, topic):
            continue

        desired_stem = sanitize_hour_title(f"{group} {topic}")
        if not desired_stem:
            continue

        target = unique_target(link, desired_stem)
        if target.resolve() != link.resolve():
            link.rename(target)
            renamed_files += 1

        relative = f"[[{target.stem}]]"
        if row[2] != relative:
            row[2] = relative
            changed_rows += 1

    if changed_rows or renamed_files:
        save_plan_table(table)

    return changed_rows, renamed_files


def main():
    """Verarbeitet den Schritt main im Kontext von dem Modul."""
    path_values = load_path_values()
    root = resolve_path_value(path_values[UNTERRICHT_DIR_KEY])
    if not root.exists():
        print(f"Unterrichtsordner nicht gefunden: {root}")
        return

    total_plans = 0
    total_rows = 0
    total_renames = 0

    for path in sorted(root.rglob("*.md")):
        if "Einheiten" in {part for part in path.parts}:
            continue
        try:
            rows_changed, files_renamed = migrate_plan(path)
        except Exception:
            continue
        total_plans += 1
        total_rows += rows_changed
        total_renames += files_renamed

    print(f"Pläne geprüft: {total_plans}")
    print(f"Plan-Zeilen aktualisiert: {total_rows}")
    print(f"Dateien umbenannt: {total_renames}")


if __name__ == "__main__":
    main()
