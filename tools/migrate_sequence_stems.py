"""Migrationsskript: Sequenz-Brainstorming-Dateinamen auf neues Schema umstellen.

Altes Schema: ``<Sequenzname> <Gruppe> <HJ>.md``  (z. B. ``Kodierung li2 26-2.md``)
Neues Schema: ``<Gruppe> <Sequenzname>.md``        (z. B. ``li2 Kodierung.md``)

Ablauf pro Sequenzdatei:
1. YAML-Frontmatter parsen → ``Sequenzname`` und ``Lerngruppe``
2. Neuen Stem berechnen (via :func:`build_sequence_stem`)
3. Kollision prüfen – wenn Zieldatei bereits existiert und != Quelldatei → Warnung, überspringen
4. Datei umbenennen
5. Im selben Verzeichnis alle ``.md``-Dateien nach ``[[alter_stem]]`` und
   ``[[alter_stem|alias]]`` durchsuchen und ersetzen

Ausführung::

    py -3 tools/migrate_sequence_stems.py

Gibt eine Zusammenfassung der umbenannten und übersprungenen Dateien aus.
Das Skript ist idempotent: Dateien die bereits den neuen Namen tragen werden
übersprungen.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Projekt-Root dem Suchpfad hinzufügen, damit kursplaner-Importe funktionieren.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from kursplaner.core.domain.plan_table import sanitize_hour_title
from kursplaner.core.domain.sequence_planning import (
    SEQUENCE_DIR_NAME,
    build_sequence_stem,
)
from kursplaner.core.domain.wiki_links import strip_wiki_link

_FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---", re.DOTALL)
_WIKI_LINK_RE = re.compile(r"\[\[([^\|\]]+)(\|[^\]]+)?\]\]")


def _parse_frontmatter_field(text: str, field: str) -> str:
    """Liest einen einzelnen skalaren Wert aus einem YAML-Frontmatter-Block.

    Parst nur einfache ``Schlüssel: Wert``-Zeilen; komplexe YAML-Strukturen
    werden nicht unterstützt, da Sequenz-Frontmatter nur skalare Felder hat.

    Args:
        text: Vollständiger Dateiinhalt (inklusive ``---`` Rahmen).
        field: Name des zu lesenden Feldes (z. B. ``"Sequenzname"``).

    Returns:
        Bereinigter Wert oder leerer String, wenn das Feld fehlt.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return ""
    for line in match.group(1).splitlines():
        if line.startswith(f"{field}:"):
            value = line[len(f"{field}:"):].strip().strip('"')
            return value
    return ""


def _replace_wiki_links_in_file(path: Path, old_stem: str, new_stem: str) -> bool:
    """Ersetzt in einer Markdown-Datei alle Wiki-Links auf ``old_stem`` durch ``new_stem``.

    Behandelt sowohl einfache Links ``[[old_stem]]`` als auch Alias-Links
    ``[[old_stem|Aliasname]]``.  Nur exakte Stem-Treffer werden ersetzt; Stems
    die nur teilweise übereinstimmen bleiben unverändert.

    Args:
        path: Pfad der zu bearbeitenden Markdown-Datei.
        old_stem: Bisheriger Dateiname ohne Endung.
        new_stem: Neuer Dateiname ohne Endung.

    Returns:
        ``True`` wenn mindestens eine Ersetzung vorgenommen wurde, sonst ``False``.
    """
    text = path.read_text(encoding="utf-8")
    old_escaped = re.escape(old_stem)
    pattern = re.compile(
        r"\[\[" + old_escaped + r"(\|[^\]]+)?\]\]"
    )

    def _replace(m: re.Match) -> str:
        alias = m.group(1) or ""
        return f"[[{new_stem}{alias}]]"

    new_text, count = pattern.subn(_replace, text)
    if count:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def _migrate_sequence_file(
    seq_path: Path,
) -> tuple[str, str] | None:
    """Benennt eine einzelne Sequenzdatei auf den neuen Stem um.

    Args:
        seq_path: Absoluter Pfad zur Sequenz-Markdown-Datei.

    Returns:
        Tupel ``(old_stem, new_stem)`` wenn umbenannt wurde, sonst ``None``.

    Raises:
        RuntimeError: Wenn ``Sequenzname`` oder ``Lerngruppe`` nicht im
            Frontmatter gefunden werden.
    """
    text = seq_path.read_text(encoding="utf-8")
    sequence_name = _parse_frontmatter_field(text, "Sequenzname")
    group_name = _parse_frontmatter_field(text, "Lerngruppe")

    if not sequence_name or not group_name:
        raise RuntimeError(
            f"Fehlendes 'Sequenzname' oder 'Lerngruppe' im Frontmatter: {seq_path}"
        )

    group_plain = strip_wiki_link(group_name)
    new_stem = build_sequence_stem(
        sequence_name=sequence_name,
        group_name=group_plain,
        halfyear_token="00-0",
    )
    old_stem = seq_path.stem

    if old_stem == new_stem:
        return None

    target = seq_path.with_name(f"{new_stem}.md")
    if target.exists() and target.resolve() != seq_path.resolve():
        raise FileExistsError(
            f"Kollision: Zieldatei existiert bereits: {target}\n"
            f"  Quelle: {seq_path}"
        )

    seq_path.rename(target)
    return old_stem, new_stem


def migrate_sequence_directory(seq_dir: Path) -> tuple[int, int, int]:
    """Migriert alle Sequenzdateien in einem ``Sequenzen``-Ordner.

    Für jede umbenannte Datei werden anschließend alle Markdown-Dateien im
    übergeordneten Plan-Verzeichnis auf alte Wiki-Links durchsucht und
    korrigiert.

    Args:
        seq_dir: Pfad zum ``Sequenzen``-Verzeichnis.

    Returns:
        Tupel ``(umbenannt, uebersprungen, kollisionen)``.
    """
    renamed = 0
    skipped = 0
    collisions = 0

    for seq_path in sorted(seq_dir.glob("*.md")):
        try:
            result = _migrate_sequence_file(seq_path)
        except FileExistsError as exc:
            print(f"  KOLLISION: {exc}")
            collisions += 1
            continue
        except RuntimeError as exc:
            print(f"  FEHLER: {exc}")
            skipped += 1
            continue

        if result is None:
            skipped += 1
            continue

        old_stem, new_stem = result
        renamed += 1

        # Wiki-Links im Plan-Verzeichnis aktualisieren.
        plan_dir = seq_dir.parent
        for md_file in plan_dir.rglob("*.md"):
            _replace_wiki_links_in_file(md_file, old_stem, new_stem)

    return renamed, skipped, collisions


def main() -> None:
    """Einstiegspunkt: sucht alle Sequenzen-Ordner unterhalb des konfigurierten Unterrichtsordners."""
    from kursplaner.core.config.path_store import UNTERRICHT_DIR_KEY, load_path_values, resolve_path_value

    path_values = load_path_values()
    root = resolve_path_value(path_values[UNTERRICHT_DIR_KEY])
    if not root.exists():
        print(f"Unterrichtsordner nicht gefunden: {root}")
        return

    total_renamed = 0
    total_skipped = 0
    total_collisions = 0

    for seq_dir in sorted(root.rglob(SEQUENCE_DIR_NAME)):
        if not seq_dir.is_dir():
            continue
        r, s, c = migrate_sequence_directory(seq_dir)
        total_renamed += r
        total_skipped += s
        total_collisions += c

    print(f"Sequenzdateien umbenannt:  {total_renamed}")
    print(f"Übersprungen (kein Diff):  {total_skipped}")
    print(f"Kollisionen:               {total_collisions}")


if __name__ == "__main__":
    main()
