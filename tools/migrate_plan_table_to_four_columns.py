"""Migrationsskript: Planungstabelle von 3 auf 4 Spalten erweitern.

Altes Format: ``| Datum | Stunden | Inhalt |``
Neues Format: ``| Datum | Stunden | Inhalt | Thema/Ausfall |``

Neue Spaltenrollen:
* ``Inhalt`` (col 2): nur Wiki-Link zur Stundendatei oder leer
* ``Thema/Ausfall`` (col 3): kontextabhängig:
  - Unterricht/Hospitation mit Oberthema → ``[[gruppe oberthema]]``
  - LZK mit Oberthema                    → ``LZK [[gruppe oberthema]]``
  - Ausfall                              → ``X Ausfallsgrund``
  - Ferien / leer                        → leer

Ablauf für jede Kurs-Markdown-Datei:
1. Datei einlesen – wenn schon 4 Spalten erkannt, überspringen (Idempotenz)
2. Alte 3-Spalten-Tabelle mit eigenem Parser laden (der neue Validator würde ablehnen)
3. Für jede Zeile den Inhalt analysieren und migrieren
4. 4-Spalten-Tabelle via ``save_plan_table`` zurückschreiben

Reihenfolge der Migrations-Skripte:
1. ``migrate_sequence_stems.py``  (Sequenzdateien umbenennen)
2. dieses Skript                  (Plantabelle auf 4 Spalten erweitern)
3. ``migrate_lesson_filenames_to_random_codes.py``

Ausführung::

    py -3 tools/migrate_plan_table_to_four_columns.py

Das Skript ist idempotent: Dateien, die schon eine 4-Spalten-Tabelle enthalten,
werden übersprungen.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.wiki_links import strip_wiki_link
from kursplaner.infrastructure.repositories.plan_table_file_repository import save_plan_table

_FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---", re.DOTALL)
_WIKI_LINK_ONLY_RE = re.compile(r"^\s*\[\[[^\]]+\]\]\s*$")
_WIKI_LINK_STEM_RE = re.compile(r"\[\[([^\|\]]+)(?:\|[^\]]+)?\]\]")
_DATE_RE = re.compile(r"\d{2}-\d{2}-\d{2}")
_SEP_ROW_RE = re.compile(r"^\|(?:\s*:?-{3,}:?\s*\|)+\s*$")


def _read_yaml_scalar(text: str, field: str) -> str:
    """Liest einen einzelnen skalaren Wert aus einem YAML-Frontmatter-Block.

    Parst nur einfache ``Schlüssel: Wert``-Zeilen; verschachtelte YAML-Strukturen
    werden nicht unterstützt.  Führende und abschließende Anführungszeichen im
    Wert werden automatisch entfernt.

    Args:
        text: Vollständiger Dateiinhalt inklusive ``---``-Rahmen.
        field: Name des zu lesenden Felds (z. B. ``"Stundentyp"``).

    Returns:
        Bereinigter Wert oder leerer String, wenn das Feld fehlt.

    Example::

        _read_yaml_scalar('---\\nStundentyp: LZK\\n---\\n', 'Stundentyp')
        # → 'LZK'
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return ""
    for line in match.group(1).splitlines():
        if line.startswith(f"{field}:"):
            return line[len(f"{field}:"):].strip().strip('"')
    return ""


def _split_row(line: str) -> list[str]:
    """Teilt eine Markdown-Tabellenzeile an ``|`` auf."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [cell.strip() for cell in s.split("|")]


def _parse_three_column_table(
    path: Path,
) -> tuple[list[list[str]], list[str], int, int, bool] | None:
    """Parst die erste 3-Spalten-Planungstabelle aus einer Markdown-Datei.

    Verwendet einen eigenen, toleranten Parser, da ``load_last_plan_table`` nach
    der Migration nur noch 4-Spalten-Tabellen akzeptiert.

    Args:
        path: Pfad zur Kurs-Markdown-Datei.

    Returns:
        Tupel ``(rows, source_lines, start_line, end_line, had_trailing_newline)``
        wenn eine 3-Spalten-Tabelle gefunden wurde, sonst ``None``.
        ``start_line`` / ``end_line`` sind 0-basierte inklusive Zeilenindizes.
    """
    text = path.read_text(encoding="utf-8")
    had_trailing_newline = text.endswith("\n")
    source_lines = text.splitlines()

    for idx, line in enumerate(source_lines):
        stripped = line.strip()
        cells = [c.lower() for c in _split_row(stripped)]
        if cells == ["datum", "stunden", "inhalt"]:
            if idx + 1 >= len(source_lines) or not _SEP_ROW_RE.match(source_lines[idx + 1]):
                continue
            start = idx
            end = idx + 1
            for body_idx in range(idx + 2, len(source_lines)):
                if source_lines[body_idx].strip().startswith("|"):
                    end = body_idx
                else:
                    break
            rows = [_split_row(source_lines[r]) for r in range(idx + 2, end + 1)]
            return rows, source_lines, start, end, had_trailing_newline

    return None


def _resolve_lesson_yaml(plan_dir: Path, link_text: str) -> dict[str, str]:
    """Lädt ``Stundentyp`` und ``Oberthema`` aus der verlinkten Stundendatei.

    Sucht die Datei im ``Einheiten``-Unterordner des Plan-Verzeichnisses.
    Gibt ein leeres Dict zurück, wenn die Datei nicht existiert oder das
    Frontmatter nicht parsbar ist – der Aufrufer soll in diesem Fall die
    ``Thema/Ausfall``-Spalte leer lassen.

    Args:
        plan_dir: Verzeichnis der Kurs-Markdown-Datei.
        link_text: Wiki-Link-Text, z. B. ``"[[grün-6 03-13 Binärdaten]]"``.

    Returns:
        Dict mit ``"Stundentyp"`` und ``"Oberthema"`` (beide Strings, ggf. leer).
    """
    match = _WIKI_LINK_STEM_RE.search(link_text)
    if not match:
        return {}
    stem = match.group(1).strip()
    candidate = plan_dir / "Einheiten" / f"{stem}.md"
    if not candidate.exists():
        return {}
    try:
        text = candidate.read_text(encoding="utf-8")
        return {
            "Stundentyp": _read_yaml_scalar(text, "Stundentyp") or "Unterricht",
            "Oberthema": _read_yaml_scalar(text, "Oberthema"),
        }
    except OSError:
        return {}


def _build_thema_ausfall(stundentyp: str, oberthema: str, group_plain: str) -> str:
    """Baut den Wert für die ``Thema/Ausfall``-Spalte aus YAML-Felder.

    Args:
        stundentyp: Wert des ``Stundentyp``-Felds (z. B. ``"LZK"``).
        oberthema: Wert des ``Oberthema``-Felds (leer = kein Oberthema gesetzt).
        group_plain: Lerngruppen-Bezeichnung ohne Wiki-Link-Syntax.

    Returns:
        Fertig formatierter Spalteninhalt oder leerer String.

    Example::

        _build_thema_ausfall("LZK", "Kodierung", "li2")
        # → "LZK [[li2 Kodierung]]"
    """
    if not oberthema:
        return ""
    seq_stem = f"{group_plain} {oberthema}"
    if stundentyp == "LZK":
        return f"LZK [[{seq_stem}]]"
    return f"[[{seq_stem}]]"


def _migrate_row(row: list[str], plan_dir: Path, group_plain: str) -> list[str]:
    """Konvertiert eine 3-Spalten-Zeile in eine 4-Spalten-Zeile.

    Analysiert den Inhalt der dritten Spalte (Index 2) und verteilt ihn auf
    die neuen Spalten ``Inhalt`` (Index 2) und ``Thema/Ausfall`` (Index 3):

    * Wiki-Link → Link bleibt in col 2, col 3 aus YAML (Stundentyp + Oberthema)
    * Freitext   → col 2 leer, col 3 = ``"X "`` + Freitext (Ausfall-Normierung)
    * Leer        → beide Spalten leer

    Args:
        row: Originale 3-Spalten-Zeile (mindestens 3 Elemente).
        plan_dir: Verzeichnis der Kurs-Datei (für YAML-Lookup).
        group_plain: Lerngruppen-Bezeichnung ohne Wiki-Link-Syntax.

    Returns:
        Liste mit 4 Elementen: ``[datum, stunden, inhalt, thema_ausfall]``.
    """
    while len(row) < 3:
        row = row + [""]
    datum, stunden, inhalt = row[0], row[1], row[2].strip()

    if _WIKI_LINK_ONLY_RE.match(inhalt):
        yaml = _resolve_lesson_yaml(plan_dir, inhalt)
        thema = _build_thema_ausfall(
            yaml.get("Stundentyp", "Unterricht"),
            yaml.get("Oberthema", ""),
            group_plain,
        )
        return [datum, stunden, inhalt, thema]

    if inhalt:
        upper = inhalt.upper()
        if upper == "X":
            thema = "X"
        elif upper.startswith("X "):
            thema = "X " + inhalt[2:].strip()
        else:
            thema = "X " + inhalt
        return [datum, stunden, "", thema]

    return [datum, stunden, "", ""]


def migrate_plan_file(plan_path: Path) -> str:
    """Migriert eine einzelne Kurs-Markdown-Datei auf das 4-Spalten-Format.

    Ist die Datei schon im 4-Spalten-Format, wird sie unverändert gelassen
    (idempotenter Betrieb).

    Args:
        plan_path: Absoluter Pfad zur Kurs-Markdown-Datei.

    Returns:
        Status-String: ``"migrated"``, ``"skipped"`` oder ``"error: <text>"``.
    """
    try:
        text = plan_path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"error: {exc}"

    for line in text.splitlines():
        cells = [c.lower() for c in _split_row(line.strip())]
        if cells == ["datum", "stunden", "inhalt", "thema/ausfall"]:
            return "skipped"

    result = _parse_three_column_table(plan_path)
    if result is None:
        return "skipped"

    rows, source_lines, start_line, end_line, had_trailing = result

    metadata_raw = {}
    fm_match = _FRONTMATTER_RE.match(text)
    if fm_match:
        for line in fm_match.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                metadata_raw[k.strip()] = v.strip().strip('"')

    group_name = metadata_raw.get("Lerngruppe", "")
    group_plain = strip_wiki_link(group_name) or group_name

    try:
        migrated_rows = [_migrate_row(row, plan_path.parent, group_plain) for row in rows]
    except Exception as exc:
        return f"error: {exc}"

    table = PlanTableData(
        markdown_path=plan_path,
        headers=["Datum", "Stunden", "Inhalt", "Thema/Ausfall"],
        rows=migrated_rows,
        start_line=start_line,
        end_line=end_line,
        source_lines=source_lines,
        had_trailing_newline=had_trailing,
        metadata=metadata_raw,
    )
    try:
        save_plan_table(table)
    except Exception as exc:
        return f"error: {exc}"

    return "migrated"


def main() -> None:
    """Einstiegspunkt: findet alle Plan-Markdown-Dateien via konfiguriertem Unterrichtsordner."""
    from kursplaner.core.config.path_store import (
        UNTERRICHT_DIR_KEY,
        load_path_values,
        resolve_path_value,
    )

    path_values = load_path_values()
    root = resolve_path_value(path_values[UNTERRICHT_DIR_KEY])
    if not root.exists():
        print(f"Unterrichtsordner nicht gefunden: {root}")
        return

    migrated = skipped = errors = 0
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        plan_md = child / f"{child.name}.md"
        if not plan_md.exists():
            continue
        status = migrate_plan_file(plan_md)
        if status == "migrated":
            migrated += 1
            print(f"  OK: {plan_md.name}")
        elif status == "skipped":
            skipped += 1
        else:
            errors += 1
            print(f"  FEHLER ({plan_md.name}): {status}")

    print(f"Migriert:      {migrated}")
    print(f"Übersprungen:  {skipped}")
    print(f"Fehler:        {errors}")


if __name__ == "__main__":
    main()
