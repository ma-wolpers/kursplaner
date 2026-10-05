"""Zentrale Regel, welche Dateien Stundendateien sind.

Stundendateien sind Markdown (``.md``) oder Blattwerk-Kurzentwürfe
(``.ebw``). Blattwerk erkennt den Dokumenttyp ausschließlich an der Endung;
Stunden mit Kurzentwurf-Inhalt werden deshalb zu ``.ebw`` migriert und
müssen weiterhin als Stunden gelten. Neue Stunden legt der Kursplaner
weiterhin als ``.md`` an; bestehende Dateien behalten beim Umbenennen und
Verschieben ihre Endung.

Alle Stellen, die Stundendateien aufzählen, auflösen oder umbenennen, nutzen
diese Funktionen statt eigener ``.md``-Annahmen.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_LESSON_SUFFIX = ".md"
"""Endung neu angelegter Stundendateien."""

LESSON_FILE_SUFFIXES = (DEFAULT_LESSON_SUFFIX, ".ebw")
"""Alle Endungen, die als Stundendatei gelten (Reihenfolge = Suchreihenfolge)."""

BLATTWERK_MARKER_KEY = "document_type"
"""Blattwerk-Konsistenzmarker im Frontmatter; der Kursplaner reicht ihn beim Speichern durch."""


def is_lesson_suffix(suffix: str) -> bool:
    """Prüft, ob eine Endung (mit Punkt, Groß/Klein egal) eine Stunden-Endung ist.

    Args:
        suffix: Dateiendung, z. B. ``".md"`` oder ``".EBW"``.

    Returns:
        ``True`` für ``.md`` und ``.ebw``.
    """
    return str(suffix or "").lower() in LESSON_FILE_SUFFIXES


def is_lesson_file(path: Path) -> bool:
    """Prüft, ob ``path`` eine existierende Datei mit Stunden-Endung ist.

    Args:
        path: Zu prüfender Pfad.

    Returns:
        ``True``, wenn die Datei existiert und auf ``.md``/``.ebw`` endet.
    """
    return is_lesson_suffix(path.suffix) and path.exists() and path.is_file()


def strip_lesson_suffix(name: str) -> str:
    """Entfernt eine Stunden-Endung (``.md``/``.ebw``) am Ende eines Namens.

    Args:
        name: Dateiname oder Linkziel, z. B. ``"ab12cd.ebw"``.

    Returns:
        Name ohne Endung; andere Endungen bleiben unverändert.
    """
    text = str(name or "")
    for suffix in LESSON_FILE_SUFFIXES:
        if text.lower().endswith(suffix):
            return text[: -len(suffix)]
    return text


def list_lesson_files(directory: Path) -> list[Path]:
    """Listet alle Stundendateien eines Verzeichnisses (nicht rekursiv), nach Namen sortiert.

    Args:
        directory: Einheiten-Verzeichnis.

    Returns:
        Dateien mit Stunden-Endung; leere Liste, wenn das Verzeichnis fehlt.
    """
    if not directory.exists() or not directory.is_dir():
        return []
    files = [path for path in directory.iterdir() if path.is_file() and is_lesson_suffix(path.suffix)]
    return sorted(files, key=lambda path: path.name.lower())


def lesson_stems(directory: Path) -> set[str]:
    """Liefert die Stems aller Stundendateien eines Verzeichnisses (für Kollisionsprüfungen)."""
    return {path.stem for path in list_lesson_files(directory)}


def lesson_file_candidates(base: Path, target: str) -> list[Path]:
    """Liefert die möglichen Pfade eines Stundenlinks in Suchreihenfolge.

    Ein Ziel mit expliziter Stunden-Endung wird genau so genommen; sonst
    werden ``.md`` und danach ``.ebw`` angehängt.

    Args:
        base: Verzeichnis, relativ zu dem das Ziel aufgelöst wird.
        target: Linkziel ohne Alias, z. B. ``"Einheiten/ab12cd"``.

    Returns:
        Kandidatenpfade (noch nicht auf Existenz geprüft).
    """
    if is_lesson_suffix(Path(target).suffix):
        return [base / target]
    return [base / f"{target}{suffix}" for suffix in LESSON_FILE_SUFFIXES]


def resolve_lesson_file(base: Path, target: str) -> Path | None:
    """Löst ein Linkziel auf die erste existierende Stundendatei auf.

    Args:
        base: Basisverzeichnis.
        target: Linkziel ohne Alias.

    Returns:
        Aufgelöster Pfad oder ``None``, wenn keine Kandidatendatei existiert.
    """
    for candidate in lesson_file_candidates(base, target):
        resolved = candidate.resolve()
        if resolved.exists() and resolved.is_file():
            return resolved
    return None
