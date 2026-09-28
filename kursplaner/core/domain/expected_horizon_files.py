"""Ablage eines Kompetenzhorizonts (KH): Default-Dateiname und Obsidian-Link.

Der Dateiname ist **keine** Identität des KH — die Identität ist *LZK +
bereinigte Themenwahl*. Der Name ist nur ein lesbarer, kollisionsarmer
Vorschlag für den Speichern-Dialog (Datum + Themen + Erstellzeit).

Die in der LZK gespeicherte Link-Form hängt vom Speicherort ab:

* Datei im Kursordner → ``[[stem]]`` (wie bisher),
* Datei anderswo im Obsidian-Vault → ``[[vault/relativer/pfad/stem]]``,
* Datei außerhalb des Vaults → kein Link (Obsidian könnte ihn nicht auflösen).

Alle Funktionen sind reine Pfad-/Textlogik ohne Dateisystemzugriff.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Sequence

from kursplaner.core.domain.wiki_links import build_wiki_link

_FORBIDDEN_NAME_CHARS_RE = re.compile(r'[\\/:*?"<>|#^\[\]]')
_WIKI_LINK_RE = re.compile(r"^\[\[([^\]]+)\]\]$")
MAX_TOPICS_IN_NAME = 3
MAX_TOPIC_PART_LENGTH = 80


def _sanitize_topic(topic: str) -> str:
    cleaned = _FORBIDDEN_NAME_CHARS_RE.sub("", str(topic or ""))
    return re.sub(r"\s+", " ", cleaned).strip(" .")


def _topic_part(topics: Sequence[str]) -> str:
    """Themenanteil: bis zu drei Themen mit `` + ``, mehr als drei mit `` + weitere``, auf 80 Zeichen gekürzt."""
    names = [name for name in (_sanitize_topic(topic) for topic in topics) if name]
    part = " + ".join(names[:MAX_TOPICS_IN_NAME])
    if len(names) > MAX_TOPICS_IN_NAME:
        part += " + weitere"
    if len(part) <= MAX_TOPIC_PART_LENGTH:
        return part or "ohne Thema"
    cut = part[: MAX_TOPIC_PART_LENGTH - 1]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" +") + "…"


def default_lzk_horizon_filename(topics: Sequence[str], *, lzk_date: date, created_at: datetime) -> str:
    """Default-Dateiname eines LZK-KH (Markdown).

    Example::

        default_lzk_horizon_filename(["Potenzfunktionen", "Exponentialfunktionen"],
                                     lzk_date=date(2026, 10, 14), created_at=datetime(2026, 9, 29, 15, 30))
        # -> "KH LZK 2026-10-14 - Potenzfunktionen + Exponentialfunktionen (2026-09-29 1530).md"
    """
    return f"KH LZK {lzk_date:%Y-%m-%d} - {_topic_part(topics)} ({created_at:%Y-%m-%d %H%M}).md"


def default_adhoc_horizon_filename(
    topics: Sequence[str], *, cutoff_date: date, created_at: datetime, extension: str
) -> str:
    """Default-Dateiname eines Ad-hoc-KH aus "Exportieren als…" (``extension`` inkl. Punkt)."""
    return f"KH bis {cutoff_date:%Y-%m-%d} - {_topic_part(topics)} ({created_at:%Y-%m-%d %H%M}){extension}"


def build_horizon_link(markdown_path: Path, *, course_dir: Path, vault_root: Path | None) -> str | None:
    """Obsidian-Link auf eine KH-Datei für das LZK-Feld ``Kompetenzhorizont``.

    Args:
        markdown_path: Aufgelöster Pfad der KH-Markdown-Datei.
        course_dir: Aufgelöster Kursordner.
        vault_root: Aufgelöste Obsidian-Vault-Wurzel oder ``None`` (unbekannt).

    Returns:
        ``[[stem]]`` im Kursordner, ``[[pfad/stem]]`` relativ zur Vault-Wurzel,
        oder ``None`` außerhalb des Vaults.
    """
    if markdown_path.parent == course_dir:
        return build_wiki_link(markdown_path.stem)
    if vault_root is None:
        return None
    try:
        relative = markdown_path.with_suffix("").relative_to(vault_root)
    except ValueError:
        return None
    return build_wiki_link(PurePosixPath(*relative.parts).as_posix())


def resolve_horizon_link(raw_link: object, *, course_dir: Path, vault_root: Path | None) -> Path | None:
    """Zielpfad eines gespeicherten ``Kompetenzhorizont``-Links (ohne Existenzprüfung).

    Gegenstück zu `build_horizon_link`: ein Link ohne Pfadanteil zeigt in den
    Kursordner, ein Link mit Pfad ist relativ zur Vault-Wurzel. Alias (``|…``)
    und eine ``.md``-Endung werden ignoriert.

    Returns:
        Der Zielpfad der Markdown-Datei, oder ``None`` bei leerem Link bzw.
        Pfad-Link ohne bekannte Vault-Wurzel.
    """
    text = str(raw_link or "").strip()
    if not text:
        return None
    match = _WIKI_LINK_RE.match(text)
    target = (match.group(1) if match else text).split("|", 1)[0].strip().replace("\\", "/")
    if target.lower().endswith(".md"):
        target = target[:-3].strip()
    if not target:
        return None
    if "/" not in target:
        return course_dir / f"{target}.md"
    if vault_root is None:
        return None
    *folders, stem = target.split("/")
    # Kein `with_suffix`: Themennamen dürfen Punkte enthalten ("Kap. 3").
    return vault_root.joinpath(*folders) / f"{stem}.md"
