from __future__ import annotations

from pathlib import Path

LESSON_DIR_PRIMARY = "Einheiten"
LESSON_DIR_ARCHIVE = "Alteinheiten"

_MANAGED_DIRS = (LESSON_DIR_PRIMARY, LESSON_DIR_ARCHIVE)


def is_lesson_dir_name(name: str) -> bool:
    """Prüft, ob ein Verzeichnisname ein verwaltetes Einheitenverzeichnis ist.

    Berücksichtigt sowohl das primäre Einheitenverzeichnis (``Einheiten``) als
    auch das Archiv-Verzeichnis (``Alteinheiten``), in das vergangene Einheiten
    beim Start automatisch verschoben werden.

    Args:
        name: Zu prüfender Verzeichnisname.

    Returns:
        ``True`` wenn ``name`` (unabhängig von Groß-/Kleinschreibung) einem
        der verwalteten Namen entspricht.
    """
    lowered = str(name or "").strip().lower()
    if not lowered:
        return False
    return lowered in {d.lower() for d in _MANAGED_DIRS}


def managed_lesson_dir_names() -> tuple[str, ...]:
    """Gibt die bekannten Einheitenverzeichnisnamen in Präferenzreihenfolge zurück.

    Das primäre Verzeichnis ``Einheiten`` wird zuerst durchsucht; ``Alteinheiten``
    wird als zweiter Suchpfad gelistet, damit Wiki-Links auf archivierte
    Einheitsdateien weiterhin auflösbar bleiben.

    Returns:
        Tupel ``("Einheiten", "Alteinheiten")``.
    """
    return _MANAGED_DIRS


def resolve_lesson_dir(plan_dir: Path, *, create_if_missing: bool = False) -> Path:
    """Resolves the managed lesson directory for a plan (`Einheiten`)."""
    primary = plan_dir / LESSON_DIR_PRIMARY
    if create_if_missing:
        primary.mkdir(parents=True, exist_ok=True)
    return primary
