"""Migration: alte 4-Spalten-Plantabellen auf das neue Format heben.

Hebt Plan-Dateien vom alten Format (Tabelle ``Datum | Stunden | Inhalt |
Thema/Ausfall``, kein ``Rhythmus``-YAML-Feld) auf das neue Format:

* Tabelle wird auf ``Datum | Inhalt | Thema/Ausfall`` (3 Spalten) reduziert.
* Ein neues YAML-Feld ``Rhythmus`` wird aus der alten Stunden-Spalte
  abgeleitet (häufigste Stundenzahl je Wochentag; Startzeit immer ``00:00``,
  da diese vorher nirgends erfasst wurde).
* Ferien-Zeilen (alte ``Stunden == 0``-Zeilen) bekommen das neue
  Ferien-Marker-Format ``X <Grund> X``; normale manuelle Ausfälle (alte
  ``Stunden > 0``-Zeilen mit ``X ...``) bleiben beim einfachen
  ``X <Grund>``-Format, nur normalisiert.

Läuft über jeden Kurs unter dem konfigurierten ``unterricht_dir`` und -
sofern nicht ``--no-archive`` gesetzt ist - zusätzlich über bereits
archivierte Kurse unter ``unterricht_dir/_ALT/Kursordner``.

Das Skript ist idempotent: bereits migrierte Dateien (3-Spalten-Tabelle,
``Rhythmus``-Feld vorhanden) werden übersprungen. Es bringt einen eigenen,
in sich geschlossenen Leser für das alte 4-Spalten-Format mit, da die
produktive Repository-Schicht (``plan_table_file_repository``) nach dieser
Migration nur noch das neue Format akzeptiert.

Usage::

    python tools/migrate_plan_table_schema.py [--dry-run] [--no-archive] [--check]

WICHTIG: Das Skript legt selbst kein Backup an. Vor einem echten Lauf das
Vault committen oder anderweitig sichern (z. B. via Obsidian-Sync-Historie
oder git, falls der Vault versioniert ist).
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

from bw_libs.app_paths import atomic_write_text
from kursplaner.core.config.path_store import UNTERRICHT_DIR_KEY, load_path_values, resolve_path_value
from kursplaner.core.domain.content_markers import (
    build_ausfall_marker,
    build_ferien_marker,
    is_ausfall_marker,
    marker_reason_text,
)
from kursplaner.core.domain.course_lifecycle import course_archive_root
from kursplaner.core.domain.course_rhythm import WeekdayRhythm, format_rhythm
from kursplaner.core.domain.plan_table import parse_plan_row_date
from kursplaner.infrastructure.repositories.plan_table_markdown_io import (
    _extract_table_blocks,
    _is_separator_row,
    _split_row,
)

LEGACY_HEADER = ["datum", "stunden", "inhalt", "thema/ausfall"]
NEW_HEADER = ["Datum", "Inhalt", "Thema/Ausfall"]


def _locate_table_by_header(lines: list[str], expected_lower: list[str]) -> tuple[int, int, list[str]] | None:
    """Findet einen Tabellenblock mit exakt passendem (case-insensitiv) Header.

    Nutzt bewusst die privaten, formatunabhängigen Zeilen-Helfer aus
    `plan_table_markdown_io` (Tabellenblock-Erkennung/-Zerlegung) statt sie
    zu duplizieren; nur die Header-Erwartung unterscheidet sich hier vom
    produktiven, strikt-neuen Loader.
    """
    for start, end in _extract_table_blocks(lines):
        head = _split_row(lines[start])
        if start + 1 > end or not _is_separator_row(lines[start + 1]):
            continue
        if [cell.lower().strip() for cell in head] == expected_lower:
            return start, end, head
    return None


def _frontmatter_bounds(lines: list[str]) -> tuple[int, int] | None:
    """Liefert `(start, end)`-Zeilenindizes der `---`-Frontmatter-Begrenzer, oder `None`."""
    if not lines or lines[0].strip() != "---":
        return None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return 0, idx
    return None


def _derive_rhythm(rows: list[list[str]]) -> tuple[WeekdayRhythm, ...]:
    """Leitet je Wochentag die häufigste Stundenzahl aus den alten Planzeilen ab.

    Bei Gleichstand gewinnt die größere Stundenzahl (deterministisch). Die
    Startzeit ist immer ``"00:00"`` - sie wurde vom alten Format nirgends
    strukturiert erfasst.
    """
    hours_by_weekday: dict[int, Counter[int]] = defaultdict(Counter)
    for row in rows:
        if len(row) < 2:
            continue
        row_date = parse_plan_row_date(row[0])
        if row_date is None:
            continue
        hours_text = str(row[1]).strip()
        if not hours_text.isdigit():
            continue
        hours = int(hours_text)
        if hours <= 0:
            continue
        hours_by_weekday[row_date.weekday()][hours] += 1

    entries: list[WeekdayRhythm] = []
    for weekday in sorted(hours_by_weekday):
        counts = hours_by_weekday[weekday]
        best_count = max(counts.values())
        chosen_hours = max(hours for hours, count in counts.items() if count == best_count)
        entries.append(WeekdayRhythm(weekday=weekday, start_time="00:00", hours=chosen_hours, valid_from=None))
    return tuple(entries)


def _rewrite_marker(cell: str, hours_text: str) -> str:
    """Migriert den Thema/Ausfall-Zellwert einer Zeile, solange Stunden noch lesbar sind.

    ``Stunden == 0`` → Ferien-Marker (``X <Grund> X``); ``Stunden > 0`` mit
    bestehendem Ausfall-Marker → auf das kanonische ``X <Grund>`` normalisiert
    (z. B. altes ``Ausfall ...``-Präfix); alle anderen Zellen bleiben
    unverändert.
    """
    hours = int(hours_text) if hours_text.strip().isdigit() else None
    if hours == 0:
        return build_ferien_marker(marker_reason_text(cell))
    if hours is not None and hours > 0 and is_ausfall_marker(cell):
        return build_ausfall_marker(marker_reason_text(cell))
    return cell


def migrate_plan(plan_path: Path, *, dry_run: bool) -> str:
    """Migriert eine einzelne Plan-Datei; liefert einen Statustext für das Log.

    Returns:
        Kurzer Statustext: ``"SKIP (bereits migriert)"``,
        ``"OK: <Rhythmus> | N Zeilen | F Ferien | A Ausfall normalisiert"``
        oder ``"ERROR: <Meldung>"``.
    """
    try:
        text = plan_path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"ERROR: Datei nicht lesbar ({exc})"

    lines = text.splitlines()
    fm_bounds = _frontmatter_bounds(lines)
    if fm_bounds is None:
        return "ERROR: Kein YAML-Frontmatter gefunden."
    fm_start, fm_end = fm_bounds
    has_rhythm_field = any(line.strip().startswith("Rhythmus:") for line in lines[fm_start + 1 : fm_end])

    legacy = _locate_table_by_header(lines, LEGACY_HEADER)
    if legacy is None:
        if has_rhythm_field:
            return "SKIP (bereits migriert)"
        return "ERROR: Weder alte 4-Spalten-Tabelle noch Rhythmus-Feld gefunden - manuell prüfen."

    table_start, table_end, _header = legacy
    body_lines = lines[table_start + 2 : table_end + 1]
    old_rows = [_split_row(line) for line in body_lines]

    rhythm = _derive_rhythm(old_rows)
    ferien_count = 0
    ausfall_count = 0
    new_rows: list[list[str]] = []
    for row in old_rows:
        if len(row) < 4:
            new_rows.append([cell for idx, cell in enumerate(row) if idx != 1])
            continue
        hours_text = row[1]
        old_cell = row[3]
        new_cell = _rewrite_marker(old_cell, hours_text)
        if new_cell != old_cell:
            if hours_text.strip() == "0":
                ferien_count += 1
            else:
                ausfall_count += 1
        new_row = [row[0], row[2], new_cell]
        new_rows.append(new_row)

    new_lines = list(lines)
    rendered_table = [
        "| " + " | ".join(NEW_HEADER) + " |",
        "| " + " | ".join(["---"] * len(NEW_HEADER)) + " |",
        *(("| " + " | ".join(row) + " |") for row in new_rows),
    ]
    new_lines[table_start : table_end + 1] = rendered_table

    stufe_idx = next(
        (idx for idx in range(fm_start + 1, fm_end) if new_lines[idx].strip().startswith("Stufe:")),
        None,
    )
    insert_at = stufe_idx + 1 if stufe_idx is not None else fm_end
    rhythm_block = ["Rhythmus:"] + [f'  - "{entry}"' for entry in format_rhythm(rhythm)]
    new_lines[insert_at:insert_at] = rhythm_block

    output = "\n".join(new_lines)
    if text.endswith("\n"):
        output += "\n"

    rhythm_display = ", ".join(format_rhythm(rhythm)) or "(leer)"
    status = f"OK: Rhythmus [{rhythm_display}] | {len(new_rows)} Zeilen | {ferien_count} Ferien | {ausfall_count} Ausfall normalisiert"

    if not dry_run:
        atomic_write_text(plan_path, output, encoding="utf-8")

    return status


def _iter_plan_files(unterricht_dir: Path, *, include_archive: bool) -> list[Path]:
    """Listet alle `<Kursordner>/<Kursordner>.md`-Pfade unter aktivem und ggf. archiviertem Wurzelordner."""
    roots = [unterricht_dir]
    if include_archive:
        archive_root = course_archive_root(unterricht_dir)
        if archive_root.exists() and archive_root.is_dir():
            roots.append(archive_root)

    paths: list[Path] = []
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for child in sorted(root.iterdir(), key=lambda item: item.name.lower()):
            if not child.is_dir():
                continue
            plan_path = child / f"{child.name}.md"
            if plan_path.exists() and plan_path.is_file():
                paths.append(plan_path)
    return paths


def _run_check(plan_paths: list[Path]) -> int:
    """Lädt jede Datei über den neuen, strikten Loader; gibt die Fehleranzahl zurück."""
    from kursplaner.infrastructure.repositories.plan_table_file_repository import load_last_plan_table

    failures = 0
    for path in plan_paths:
        try:
            load_last_plan_table(path)
        except Exception as exc:
            failures += 1
            print(f"  FEHLER: {path}: {exc}")
    return failures


def main() -> None:
    """CLI-Einstiegspunkt."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Nur anzeigen, keine Dateien schreiben.")
    parser.add_argument(
        "--no-archive", action="store_true", help="Archivierte Kurse unter _ALT/Kursordner nicht mitmigrieren."
    )
    parser.add_argument(
        "--check", action="store_true", help="Nach der Migration jede Datei mit dem neuen Loader gegenprüfen."
    )
    parser.add_argument(
        "--unterricht-dir",
        type=Path,
        default=None,
        help="Optionaler Override des Unterrichtsordners (Standard: konfigurierter Pfad aus paths.json). "
        "Nützlich, um das Skript zuerst gegen eine Kopie des Vaults zu testen.",
    )
    args = parser.parse_args()

    if args.unterricht_dir is not None:
        unterricht_dir = args.unterricht_dir.expanduser().resolve()
    else:
        path_values = load_path_values()
        unterricht_dir = resolve_path_value(path_values[UNTERRICHT_DIR_KEY])
    if not unterricht_dir.exists():
        print(f"Unterrichtsordner nicht gefunden: {unterricht_dir}")
        sys.exit(1)

    plan_paths = _iter_plan_files(unterricht_dir, include_archive=not args.no_archive)
    print(f"Gefundene Plan-Dateien: {len(plan_paths)}" + (" (inkl. Archiv)" if not args.no_archive else ""))
    if args.dry_run:
        print("[dry-run] Es werden keine Dateien geschrieben.\n")

    ok_count = 0
    skip_count = 0
    error_count = 0
    for path in plan_paths:
        status = migrate_plan(path, dry_run=args.dry_run)
        print(f"{path}: {status}")
        if status.startswith("OK"):
            ok_count += 1
        elif status.startswith("SKIP"):
            skip_count += 1
        else:
            error_count += 1

    print(f"\nZusammenfassung: {ok_count} migriert, {skip_count} übersprungen, {error_count} Fehler.")

    if args.check:
        print("\n--check: Lade alle Dateien über den neuen Loader ...")
        if args.dry_run:
            print("(--check zusammen mit --dry-run prüft die UNVERÄNDERTEN Dateien - wenig aussagekräftig.)")
        failures = _run_check(plan_paths)
        print(f"--check abgeschlossen: {failures} Datei(en) nicht ladbar." if failures else "--check: alle Dateien ladbar.")
        if failures:
            sys.exit(1)


if __name__ == "__main__":
    main()
