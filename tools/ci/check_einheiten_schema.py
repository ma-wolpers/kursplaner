#!/usr/bin/env python3
"""Schema-Check für Einheiten-Dateien (`Einheiten/`, `Alteinheiten/`).

Ersetzt das frühere PowerShell-Skript, das Pflichtfelder, Stundentypen und
erlaubte Felder als eigene Kopie führte. Dieser Check hat **keine** eigenen
Regeln, sondern importiert sie aus dem Code (Single Source of Truth):

* Dateinamen-Format → `lesson_naming.is_random_lesson_stem`
* Endungen und Blattwerk-Marker → `lesson_files.is_lesson_file`, `BLATTWERK_MARKER_KEY`
* Verzeichnisnamen → `lesson_directory.is_lesson_dir_name`
* Pflichtfelder, leere Pflichtfelder, gültiger Stundentyp und Dauer →
  `yaml_registry.parse_yaml_frontmatter` mit `LESSON_SCHEMA`
* Erlaubte Felder → `lesson_yaml_policy.allowed_keys_for_type` (Vereinigung über
  alle `LESSON_TYPE_VALUES`)

Aufruf::

    python tools/ci/check_einheiten_schema.py [WURZEL]

Ohne ``WURZEL`` wird wie bisher der Ordner ``10 Unterricht`` im benachbarten
``7thVault`` gesucht; fehlt er (CI, isolierte Umgebung), endet der Check mit
SKIP und Exit-Code 0. Exit-Code 1 bei Verstößen.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kursplaner.core.domain.lesson_directory import is_lesson_dir_name  # noqa: E402
from kursplaner.core.domain.lesson_files import BLATTWERK_MARKER_KEY, is_lesson_file  # noqa: E402
from kursplaner.core.domain.lesson_naming import is_random_lesson_stem  # noqa: E402
from kursplaner.core.domain.lesson_yaml_policy import LESSON_TYPE_VALUES, allowed_keys_for_type  # noqa: E402
from kursplaner.core.domain.yaml_registry import LESSON_SCHEMA, parse_yaml_frontmatter  # noqa: E402

UNTERRICHT_DIR_NAME = "10 Unterricht"
"""Name des Vault-Ordners mit allen Kursen (nur für die Standard-Suche ohne Argument)."""

KNOWN_KEYS = frozenset(
    {key for lesson_type in LESSON_TYPE_VALUES for key in allowed_keys_for_type(lesson_type)} | {BLATTWERK_MARKER_KEY}
)
"""Alle Felder, die irgendein Stundentyp tragen darf (abgeleitet, keine eigene Liste)."""


def lesson_files_under(root: Path) -> list[Path]:
    """Alle Einheiten-Dateien unterhalb von *root* (nur in verwalteten Einheitenordnern).

    Args:
        root: Wurzelverzeichnis (z. B. ``10 Unterricht`` oder ein Testordner).

    Returns:
        Sortierte Liste der Dateien.
    """
    return sorted(path for path in root.rglob("*") if is_lesson_file(path) and is_lesson_dir_name(path.parent.name))


def check_lesson_file(path: Path) -> list[str]:
    """Prüft eine Einheiten-Datei gegen Namensregel und Schema.

    Args:
        path: Einheiten-Datei.

    Returns:
        Nutzerlesbare Verstöße (leer = in Ordnung).
    """
    errors: list[str] = []
    if not is_random_lesson_stem(path.stem):
        errors.append(f"Ungültiger Dateiname: {path}")
    try:
        data, _text = parse_yaml_frontmatter(path.read_text(encoding="utf-8"), LESSON_SCHEMA, str(path))
    except (OSError, RuntimeError, UnicodeDecodeError) as exc:
        return [*errors, str(exc)]
    errors.extend(f"Unerlaubtes YAML-Feld '{key}' in {path}" for key in sorted(set(data) - KNOWN_KEYS))
    return errors


def check_lesson_files(files: Iterable[Path]) -> list[str]:
    """Prüft mehrere Einheiten-Dateien und sammelt alle Verstöße."""
    return [error for path in files for error in check_lesson_file(path)]


def _default_root() -> Path | None:
    """Sucht ``10 Unterricht`` im benachbarten Vault (wie das frühere Skript)."""
    for candidate in (ROOT / ".." / ".." / "7thVault", ROOT / ".." / "7thVault", Path.cwd() / "7thVault"):
        if candidate.is_dir():
            return next((p for p in candidate.rglob(UNTERRICHT_DIR_NAME) if p.is_dir()), None)
    return None


def main(argv: list[str]) -> int:
    """Einstieg: prüft *argv[0]* oder den Standardordner; Exit-Code 0/1."""
    root = Path(argv[0]) if argv else _default_root()
    if root is None or not root.is_dir():
        print("Schema-Check SKIP: Einheiten-Wurzel nicht vorhanden (CI/isolierte Umgebung).")
        return 0
    files = lesson_files_under(root)
    errors = check_lesson_files(files)
    if errors:
        print("Schema-Check FEHLGESCHLAGEN:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Schema-Check OK: {len(files)} Einheitendateien geprüft.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
