from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bw_libs.app_paths import atomic_write_json
from bw_libs.safe_read import read_json_or_default
from kursplaner.core.config.settings import SCRIPT_DIR

CACHE_FORMAT_VERSION = 1
"""Wird bei jeder Struktur-Änderung des Cache-Eintragsformats hochgezählt.

Ein Mismatch beim Laden führt dazu, dass der gesamte Cache wie leer
behandelt wird (voller Neuaufbau) -- keine Migration alter Cache-Stände,
kein Fehlerzustand des Popups. Der Cache ist eine reine Beschleunigung,
niemals eine Wahrheitsquelle."""


@dataclass(frozen=True)
class CachedFileEntry:
    """Ein persistierter Cache-Eintrag für genau eine gescannte Vault-Datei.

    Deckt sowohl Kompetenz- (`kind="node"`) als auch Bereichs-Dateien
    (`kind="bereich"`) ab, mit jeweils nur den dafür relevanten Feldern
    befüllt: `frontmatter` (roh, via `yaml.safe_load`) + `title` für
    Kompetenz-Knoten (der vollständige Markdown-Body wird laut
    Lazy-Body-Entscheidung NIE gecacht); `body` (vollständiger Text) für
    Bereichs-Hubs, die -- da nur ~11 kleine Dateien pro Fach -- bewusst
    weiterhin eager gehalten werden.

    Attributes:
        mtime_ns, size: Momentaufnahme zum Zeitpunkt des letzten
            erfolgreichen Scans -- Grundlage der Cache-Invalidierung
            (beide müssen übereinstimmen, sonst wird neu gelesen).
        kind: `"node"` oder `"bereich"`.
        frontmatter: Rohes Frontmatter-Dict (nur `kind="node"`).
        body: Vollständiger Dateitext (nur `kind="bereich"`).
        title: Vorab abgeleiteter Anzeigetitel (nur `kind="node"` --
            Bereichs-Titel werden bei jedem Zugriff frisch aus `body`
            abgeleitet, das ohnehin schon vollständig im Cache liegt).
    """

    mtime_ns: int
    size: int
    kind: str
    frontmatter: dict[str, object] | None
    body: str | None
    title: str


def cache_file_path() -> Path:
    """Liefert den Pfad der persistenten Kompetenzgraph-Cache-Datei (app-lokal, nicht im Vault)."""
    return SCRIPT_DIR / "config" / "kompetenzgraph_cache.json"


def _deserialize_entry(raw_entry: object) -> CachedFileEntry | None:
    """Baut einen `CachedFileEntry` aus einem rohen JSON-Objekt, oder `None` bei Formatfehlern.

    Jede Abweichung vom erwarteten Format (fehlendes Feld, falscher Typ)
    wird wie ein Cache-Miss für genau diese eine Datei behandelt --
    niemals als Absturz des gesamten Ladevorgangs.
    """
    if not isinstance(raw_entry, dict):
        return None
    try:
        frontmatter = raw_entry.get("frontmatter")
        body = raw_entry.get("body")
        return CachedFileEntry(
            mtime_ns=int(raw_entry["mtime_ns"]),
            size=int(raw_entry["size"]),
            kind=str(raw_entry["kind"]),
            frontmatter=frontmatter if isinstance(frontmatter, dict) else None,
            body=body if isinstance(body, str) else None,
            title=str(raw_entry.get("title", "")),
        )
    except (KeyError, TypeError, ValueError):
        return None


def load_cache_from_disk() -> dict[str, CachedFileEntry]:
    """Lädt den persistenten Cache; jede Beschädigung/Versions-Abweichung liefert einen leeren Cache.

    Ein leerer Rückgabewert löst in `FileSystemKompetenzGraphRepository`
    keinen Fehler aus -- er führt lediglich dazu, dass jede Datei beim
    nächsten Scan als Cache-Miss behandelt (und danach neu gecacht) wird.
    """
    payload = read_json_or_default(cache_file_path(), default=None)
    if not isinstance(payload, dict) or payload.get("cache_version") != CACHE_FORMAT_VERSION:
        return {}

    raw_files = payload.get("files")
    if not isinstance(raw_files, dict):
        return {}

    entries: dict[str, CachedFileEntry] = {}
    for path_str, raw_entry in raw_files.items():
        entry = _deserialize_entry(raw_entry)
        if entry is not None:
            entries[str(path_str)] = entry
    return entries


def save_cache_to_disk(cache: dict[str, CachedFileEntry]) -> None:
    """Persistiert den Cache atomar; ein Schreibfehler propagiert bewusst NICHT.

    Der Cache ist reiner Performance-Cache -- ein Schreibfehler (z. B. kein
    Schreibzugriff auf `config/`) darf das Popup niemals funktionsunfähig
    machen, es wird beim nächsten Mal einfach erneut versucht.
    """
    payload = {
        "cache_version": CACHE_FORMAT_VERSION,
        "files": {
            path_str: {
                "mtime_ns": entry.mtime_ns,
                "size": entry.size,
                "kind": entry.kind,
                "frontmatter": entry.frontmatter,
                "body": entry.body,
                "title": entry.title,
            }
            for path_str, entry in cache.items()
        },
    }
    try:
        atomic_write_json(cache_file_path(), payload)
    except OSError:
        pass
