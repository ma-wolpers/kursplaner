"""Reines Markdown-Tabellen-IO fuer Plan-Dateien (ohne YAML-/Lesson-Bezug.

Ausgelagert aus `plan_table_file_repository.py`, das zuvor sowohl die
Tabellen-IO als auch die Lesson-YAML-/Link-Operationen buendelte und dabei die
projektweite Zeilenrichtgroesse ueberschritt. `plan_table_file_repository.py`
re-exportiert die hier definierten Namen, damit bestehende Importe
unveraendert bleiben.
"""

from __future__ import annotations

import re
from pathlib import Path

from bw_libs.app_paths import atomic_write_text
from kursplaner.core.domain.course_subject import normalize_course_subject
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.yaml_registry import PLAN_METADATA_SCHEMA, parse_yaml_frontmatter

PLAN_DATE_RE = re.compile(r"\d{2}-\d{2}-\d{2}")


def _split_row(row_line: str) -> list[str]:
    """Teilt eine Markdown-Tabellenzeile in Zellen auf."""
    line = row_line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def _is_separator_row(row_line: str) -> bool:
    line = row_line.strip()
    if not line.startswith("|"):
        return False
    parts = _split_row(line)
    if not parts:
        return False
    return all(re.fullmatch(r":?-{3,}:?", part or "") for part in parts)


def _extract_table_blocks(lines: list[str]) -> list[tuple[int, int]]:
    blocks: list[tuple[int, int]] = []
    start = None

    for idx, line in enumerate(lines):
        stripped = line.strip()
        is_row = stripped.startswith("|") and "|" in stripped[1:]
        if is_row:
            if start is None:
                start = idx
        else:
            if start is not None:
                if idx - start >= 2:
                    blocks.append((start, idx - 1))
                start = None

    if start is not None and len(lines) - start >= 2:
        blocks.append((start, len(lines) - 1))

    return blocks


def _validate_plan_rows(rows: list[list[str]], source_label: str) -> None:
    """Validiert zentrale Tabelleninvarianten fuer Datum hart."""
    for index, row in enumerate(rows, start=1):
        if len(row) < 3:
            raise RuntimeError(f"Ungueltige Tabellenzeile in {source_label}: Zeile {index} hat weniger als 3 Spalten.")

        date_text = str(row[0]).strip()
        if not PLAN_DATE_RE.fullmatch(date_text):
            raise RuntimeError(
                f"Ungueltiges Datum in {source_label}: Zeile {index} ('{date_text}'). Erwartet DD-MM-YY."
            )


def _parse_plan_metadata(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    metadata, _ = parse_yaml_frontmatter(text, PLAN_METADATA_SCHEMA, source_label=str(path))
    normalized: dict[str, object] = {
        key: (value if isinstance(value, list) else str(value)) for key, value in metadata.items()
    }

    kursfach_raw = str(normalized.get("Kursfach", "")).strip()
    try:
        normalized["Kursfach"] = normalize_course_subject(kursfach_raw)
    except ValueError:
        raise RuntimeError(
            "Ungueltiges YAML-Feld 'Kursfach' in Plan-Datei: "
            f"{path}\n"
            f"Gefunden: '{kursfach_raw}'\n"
            "Erlaubt sind nur standardisierte Kursfach-Werte: Informatik, Mathematik, Darstellendes Spiel."
        )

    return normalized


def _locate_plan_table_block(lines: list[str], markdown_path: Path) -> tuple[int, int, list[str]]:
    """Findet Zeilenbereich und Header der Planungstabelle in `lines`.

    Wirft RuntimeError, falls keine gültige Planungstabelle gefunden wird.
    """
    blocks = _extract_table_blocks(lines)
    if not blocks:
        raise RuntimeError("Keine Markdown-Tabelle in der Datei gefunden.")

    selected = None
    headers: list[str] = []

    for start, end in blocks:
        head = _split_row(lines[start])
        if start + 1 > end or not _is_separator_row(lines[start + 1]):
            continue

        lowered = [cell.lower().strip() for cell in head]
        if lowered == ["datum", "inhalt", "thema/ausfall"]:
            selected = (start, end)
            headers = head

    if selected is None:
        raise RuntimeError(
            "Keine gültige Planungstabelle gefunden. "
            "Erwartet wird exakt: Datum | Inhalt | Thema/Ausfall. "
            "Alte 4-Spalten-Tabellen bitte mit 'python tools/migrate_plan_table_schema.py' migrieren."
        )

    start, end = selected
    return start, end, headers


def _file_signature(path: Path) -> tuple[int, int]:
    """Liefert `(mtime_ns, size)` einer Datei als billig vergleichbare Änderungssignatur."""
    stat = path.stat()
    return getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)), stat.st_size


def load_last_plan_table(markdown_path: Path) -> PlanTableData:
    text = markdown_path.read_text(encoding="utf-8")
    had_trailing_newline = text.endswith("\n")
    lines = text.splitlines()

    metadata = _parse_plan_metadata(markdown_path)

    start, end, headers = _locate_plan_table_block(lines, markdown_path)

    body_lines = lines[start + 2 : end + 1]
    rows = [_split_row(line) for line in body_lines]

    expected_len = len(headers)
    normalized_rows: list[list[str]] = []
    for row in rows:
        if len(row) < expected_len:
            row = row + [""] * (expected_len - len(row))
        elif len(row) > expected_len:
            row = row[:expected_len]
        normalized_rows.append(row)

    _validate_plan_rows(normalized_rows, str(markdown_path))

    mtime_ns, size = _file_signature(markdown_path)

    return PlanTableData(
        markdown_path=markdown_path,
        headers=headers,
        rows=normalized_rows,
        start_line=start,
        end_line=end,
        source_lines=lines,
        had_trailing_newline=had_trailing_newline,
        metadata=metadata,
        source_mtime_ns=mtime_ns,
        source_size=size,
    )


def _render_table(table: PlanTableData) -> list[str]:
    headers = table.headers
    separator = ["---"] * len(headers)

    output = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(separator) + " |",
    ]

    for row in table.rows:
        safe = [cell.replace("\n", " ").strip() for cell in row]
        output.append("| " + " | ".join(safe) + " |")

    return output


def save_plan_table(table: PlanTableData):
    """Persistiert eine Planungstabelle; erkennt externe Datei-Änderungen seit dem Laden.

    Vergleicht `(mtime_ns, size)` der Datei mit der beim Laden gemerkten Signatur
    (billiger als ein erneutes Volleinlesen bei jedem Speichern). Weicht sie ab
    – die Datei wurde also außerhalb dieser Session verändert –, werden
    `source_lines`/`start_line`/`end_line`/`had_trailing_newline` frisch von der
    Platte übernommen, bevor gerendert wird. So bleibt Text vor/nach der Tabelle,
    der extern hinzugefügt wurde, erhalten; nur die im Speicher editierten `rows`
    (die eigentliche Nutzeraktion) werden übernommen, nicht der frische Tabelleninhalt.
    """
    _validate_plan_rows(table.rows, str(table.markdown_path))

    if table.markdown_path.exists():
        current_mtime_ns, current_size = _file_signature(table.markdown_path)
        if (current_mtime_ns, current_size) != (table.source_mtime_ns, table.source_size):
            fresh_text = table.markdown_path.read_text(encoding="utf-8")
            fresh_lines = fresh_text.splitlines()
            start, end, _headers = _locate_plan_table_block(fresh_lines, table.markdown_path)
            table.source_lines = fresh_lines
            table.start_line = start
            table.end_line = end
            table.had_trailing_newline = fresh_text.endswith("\n")

    rendered = _render_table(table)
    updated_lines = table.source_lines[: table.start_line] + rendered + table.source_lines[table.end_line + 1 :]
    output = "\n".join(updated_lines)
    if table.had_trailing_newline:
        output += "\n"
    atomic_write_text(table.markdown_path, output, encoding="utf-8")

    table.source_mtime_ns, table.source_size = _file_signature(table.markdown_path)
