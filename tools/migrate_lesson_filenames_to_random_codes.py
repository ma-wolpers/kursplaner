"""Migrationsskript: Einheitsdateinamen auf 6-stellige Zufallscodes umstellen.

Altes Schema: ``<Gruppe> mm-dd <Titel>.md``  (z. B. ``grün-6 03-13 Binärdaten.md``)
Neues Schema: ``<6-Zeichen-Code>.md``         (z. B. ``ab12cd.md``)

Ablauf:
1. Vault-weiten Index aller bestehenden Einheiten-Stems aufbauen
2. Für jede Kurs-MD:
   a. 4-Spalten-Tabelle laden
   b. Für jede Zeile mit veralteten Stem (``<Gruppe> mm-dd <Titel>``-Muster):
      - Neuen eindeutigen 6-Zeichen-Code generieren
      - Datei umbenennen
      - Link in col 2 der Plantabelle aktualisieren
   c. Geänderte Plantabelle speichern
   d. **Global**: alle ``.md``-Dateien im Vault auf ``[[alter_stem]]``-Vorkommen
      durchsuchen und durch ``[[neuer_stem]]`` ersetzen (inkl. Alias-Links)
3. Zusammenfassung ausgeben

Muss NACH ``migrate_plan_table_to_four_columns.py`` laufen.

Ausführung::

    py -3 tools/migrate_lesson_filenames_to_random_codes.py

Das Skript ist idempotent: Dateien mit 6-Zeichen-Stems werden übersprungen.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from kursplaner.core.domain.lesson_naming import generate_random_lesson_stem
from kursplaner.infrastructure.repositories.plan_table_file_repository import (
    load_last_plan_table,
    save_plan_table,
)

_LEGACY_STEM_RE = re.compile(r"^.+ \d{2}-\d{2} .+$")
_WIKI_LINK_ONLY_RE = re.compile(r"^\s*\[\[[^\]]+\]\]\s*$")
_WIKI_LINK_STEM_RE = re.compile(r"\[\[([^\|\]]+)(?:\|[^\]]+)?\]\]")


def is_legacy_lesson_stem(stem: str) -> bool:
    """Erkennt, ob ein Datei-Stem das alte ``<Gruppe> mm-dd <Titel>``-Muster hat.

    Das alte Muster enthält zwingend ein Datums-Token der Form ``mm-dd`` (z. B.
    ``03-13``), flankiert von mindestens einem Zeichen auf jeder Seite.  Neue
    6-Zeichen-Codes (``ab12cd``) enthalten kein solches Token.

    Args:
        stem: Dateiname ohne Endung.

    Returns:
        ``True`` wenn ``stem`` dem alten Muster entspricht.

    Example::

        is_legacy_lesson_stem("grün-6 03-13 Binärdaten")  # → True
        is_legacy_lesson_stem("ab12cd")                    # → False
    """
    return bool(_LEGACY_STEM_RE.match(str(stem).strip()))


def _replace_wiki_links_in_file(path: Path, old_stem: str, new_stem: str) -> bool:
    """Ersetzt in einer Markdown-Datei alle Wiki-Links auf ``old_stem`` durch ``new_stem``.

    Behandelt sowohl einfache Links ``[[old_stem]]`` als auch Alias-Links
    ``[[old_stem|Aliasname]]``.  Nur exakte Stem-Treffer werden ersetzt; Stems
    die als Teilstring eines längeren Stems vorkommen bleiben unverändert.

    Args:
        path: Pfad der zu bearbeitenden Markdown-Datei.
        old_stem: Bisheriger Dateiname ohne Endung.
        new_stem: Neuer Dateiname ohne Endung.

    Returns:
        ``True`` wenn mindestens eine Ersetzung vorgenommen wurde, sonst ``False``.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    old_escaped = re.escape(old_stem)
    pattern = re.compile(r"\[\[" + old_escaped + r"(\|[^\]]+)?\]\]")

    def _replace(m: re.Match) -> str:
        alias = m.group(1) or ""
        return f"[[{new_stem}{alias}]]"

    new_text, count = pattern.subn(_replace, text)
    if count:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def _collect_all_existing_stems(unterricht_dir: Path) -> set[str]:
    """Baut einen vault-weiten Index aller bestehenden Einheits-Stems auf.

    Durchsucht alle ``Einheiten/``- und ``Alteinheiten/``-Unterordner der
    Kurs-Verzeichnisse im Unterrichtsordner.

    Args:
        unterricht_dir: Konfigurierter Unterrichtsordner.

    Returns:
        Menge aller .md-Stems (ohne Endung) aus allen Einheitenordnern.
    """
    stems: set[str] = set()
    for plan_dir in unterricht_dir.iterdir():
        if not plan_dir.is_dir():
            continue
        for dir_name in ("Einheiten", "Alteinheiten"):
            lesson_dir = plan_dir / dir_name
            if lesson_dir.exists():
                stems.update(p.stem for p in lesson_dir.glob("*.md"))
    return stems


def migrate_plan_file(
    plan_path: Path,
    vault_root: Path,
    global_stems: set[str],
) -> tuple[int, int]:
    """Migriert alle veralteten Einheits-Stems einer Kurs-MD auf Zufallscodes.

    Für jede Tabellenzeile mit einem veralteten Wiki-Link in col 2 (``Inhalt``):
    1. Stundendatei umbenennen (``Einheiten/`` oder ``Alteinheiten/``)
    2. Link in der Plantabelle aktualisieren
    3. Tabelle auf Disk speichern
    4. Global alle ``.md``-Dateien im Vault auf den alten Link durchsuchen und
       ersetzen (schließt Sequenz-, UB- und andere Markdown-Dateien ein)

    Bereits umbenannte Stems (6-Zeichen-Code) werden übersprungen.  Wenn zwei
    Zeilen auf dieselbe Datei zeigen, wird die Datei nur einmal umbenannt.

    Args:
        plan_path: Pfad zur Kurs-Markdown-Datei (4-Spalten-Format erforderlich).
        vault_root: Wurzelverzeichnis des Vaults für den globalen Suchen-Ersetzen-Lauf.
        global_stems: Vault-weite Menge belegter Stems; wird in-place erweitert.

    Returns:
        Tupel ``(umbenannt, uebersprungen)`` – Zeilen ohne Link oder mit bereits
        aktuellem Stem zählen als übersprungen.
    """
    try:
        table = load_last_plan_table(plan_path)
    except Exception:
        return 0, 0

    header_map = {name.lower(): idx for idx, name in enumerate(table.headers)}
    idx_inhalt = header_map.get("inhalt", 2)

    renamed_map: dict[str, str] = {}
    renamed = 0
    changed = False

    for row in table.rows:
        if idx_inhalt >= len(row):
            continue
        inhalt = row[idx_inhalt].strip()
        if not _WIKI_LINK_ONLY_RE.match(inhalt):
            continue
        m = _WIKI_LINK_STEM_RE.search(inhalt)
        if not m:
            continue
        old_stem = m.group(1).strip()
        if not is_legacy_lesson_stem(old_stem):
            continue

        if old_stem in renamed_map:
            row[idx_inhalt] = f"[[{renamed_map[old_stem]}]]"
            changed = True
            continue

        lesson_path: Path | None = None
        for dir_name in ("Einheiten", "Alteinheiten"):
            candidate = plan_path.parent / dir_name / f"{old_stem}.md"
            if candidate.exists():
                lesson_path = candidate
                break

        if lesson_path is None:
            print(f"  WARNUNG: Datei nicht gefunden für Stem '{old_stem}' in {plan_path.parent.name}")
            continue

        new_stem = generate_random_lesson_stem(global_stems)
        global_stems.add(new_stem)
        lesson_path.rename(lesson_path.parent / f"{new_stem}.md")
        renamed_map[old_stem] = new_stem
        row[idx_inhalt] = f"[[{new_stem}]]"
        changed = True
        renamed += 1

    if changed:
        save_plan_table(table)
        for old_stem, new_stem in renamed_map.items():
            for md_file in vault_root.rglob("*.md"):
                _replace_wiki_links_in_file(md_file, old_stem, new_stem)

    return renamed, 0


def main() -> None:
    """Einstiegspunkt: findet alle Kurs-MDs und migriert ihre Einheitsdateinamen."""
    from kursplaner.core.config.path_store import (
        UNTERRICHT_DIR_KEY,
        load_path_values,
        resolve_path_value,
    )

    path_values = load_path_values()
    unterricht_dir = resolve_path_value(path_values[UNTERRICHT_DIR_KEY])
    if not unterricht_dir.exists():
        print(f"Unterrichtsordner nicht gefunden: {unterricht_dir}")
        return

    vault_root = unterricht_dir.parent
    global_stems = _collect_all_existing_stems(unterricht_dir)

    total_renamed = total_skipped = 0
    for child in sorted(unterricht_dir.iterdir()):
        if not child.is_dir():
            continue
        plan_md = child / f"{child.name}.md"
        if not plan_md.exists():
            continue
        renamed, skipped = migrate_plan_file(plan_md, vault_root, global_stems)
        total_renamed += renamed
        total_skipped += skipped
        if renamed:
            print(f"  {child.name}: {renamed} umbenannt")

    print(f"Einheitsdateien umbenannt:  {total_renamed}")
    print(f"Zeilen übersprungen:        {total_skipped}")


if __name__ == "__main__":
    main()
