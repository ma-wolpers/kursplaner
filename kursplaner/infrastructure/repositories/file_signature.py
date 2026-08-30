"""Billige Datei-Änderungssignatur, geteilt zwischen mehreren Repositories.

Extrahiert aus `plan_table_markdown_io.py`, wo dasselbe `(mtime_ns, size)`-Muster
bereits für externe-Änderungs-Erkennung an Plan-Dateien verwendet wird
(`PlanTableData.source_mtime_ns`/`source_size`, `save_plan_table()`). Der
Lesson-YAML-Cache in `plan_table_file_repository.py::FileSystemLessonRepository`
nutzt dieselbe Signatur für denselben Zweck an verlinkten Stunden-Dateien,
statt eine zweite, potenziell abweichende Variante zu erfinden.
"""

from __future__ import annotations

from pathlib import Path


def file_signature(path: Path) -> tuple[int, int]:
    """Liefert `(mtime_ns, size)` einer Datei als billig vergleichbare Änderungssignatur.

    Bewusst mehr als nur `mtime` (wie ursprünglich für den Lesson-YAML-Cache
    vorgeschlagen, auf Nutzerwunsch verschärft): manche Sync-Tools/Dateisysteme
    aktualisieren `mtime` nicht immer zuverlässig bei jeder externen Änderung;
    eine zusätzlich abweichende Dateigröße erkennt zumindest die häufigste
    Klasse solcher Änderungen (Inhalt kürzer/länger) auch dann, wenn `mtime`
    für sich allein trügt. Kein Ersatz für einen echten Hash — bewusst billig
    gehalten (ein `Path.stat()`-Aufruf), da dies bei jedem potenziellen
    Cache-Hit aufgerufen wird.

    Args:
        path: Zu prüfende Datei (muss existieren).

    Returns:
        Tupel aus `(mtime_ns, size)`.

    Raises:
        OSError: Wenn die Datei nicht (mehr) existiert oder nicht lesbar ist
            (z. B. `FileNotFoundError`) — Aufrufer müssen das als "kein
            gültiger Cache-Zustand" behandeln, nicht als harten Fehler.
    """
    stat = path.stat()
    return getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)), stat.st_size
