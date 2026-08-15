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


def is_valid_unterricht_link(link: Path | None) -> bool:
    """Prüft, ob ein Link auf eine verwaltete, tatsächlich existierende Stunden-Datei zeigt.

    Args:
        link: Aufgelöster Pfad einer verlinkten Stunden-Datei, oder ``None``.

    Returns:
        ``True``, wenn ``link`` existiert, eine Datei ist und in einem
        verwalteten Einheitenverzeichnis liegt (siehe `is_lesson_dir_name`).
    """
    if not (isinstance(link, Path) and link.exists() and link.is_file()):
        return False
    return is_lesson_dir_name(link.parent.name)


def resolve_lesson_dir(plan_dir: Path, *, create_if_missing: bool = False) -> Path:
    """Resolves the managed lesson directory for a plan (`Einheiten`)."""
    primary = plan_dir / LESSON_DIR_PRIMARY
    if create_if_missing:
        primary.mkdir(parents=True, exist_ok=True)
    return primary
