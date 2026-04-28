from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from kursplaner.core.config.path_store import serialize_workspace_relative_path
from kursplaner.core.domain.lesson_directory import managed_lesson_dir_names
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.yaml_registry import LESSON_SCHEMA, parse_yaml_frontmatter
from kursplaner.infrastructure.repositories.plan_table_file_repository import get_row_link_path


@dataclass
class _IndexEntry:
    path: Path
    mtime_ns: int
    size: int
    ctime_ns: int
    data: dict


class FileSystemLessonIndexRepository:
    """Dateisystembasierter, inkrementeller Read-Index für Stunden-Metadaten.

    Der Repository-Cache wird über `mtime_ns` gepflegt und liefert nur leichte
    Metadaten für Übersichtsabfragen, keine vollständigen Fachobjekte.
    """

    INDEX_FORMAT_VERSION = 2

    def __init__(self):
        """Initialisiert den thread-sicheren In-Memory-Cache pro Stundenordner."""
        # key: folder path (str) -> map: file path (str) -> _IndexEntry
        self._cache: Dict[str, Dict[str, _IndexEntry]] = {}
        self._lock = threading.RLock()
        self._logger = logging.getLogger(__name__)

    @staticmethod
    def _mtime_ns(path: Path) -> int | None:
        """Liest die Nanosekunden-Modification-Time einer Datei robust aus."""
        if not path.exists():
            return None
        stat = path.stat()
        return getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))

    @staticmethod
    def _file_signature(path: Path) -> tuple[int, int, int] | None:
        """Liefert eine robuste Dateisignatur aus mtime/size/ctime in ns."""
        if not path.exists():
            return None
        stat = path.stat()
        mtime_ns = getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))
        ctime_ns = getattr(stat, "st_ctime_ns", int(stat.st_ctime * 1_000_000_000))
        return (mtime_ns, int(stat.st_size), ctime_ns)

    def _read_metadata_from_file(self, path: Path) -> dict:
        """Liest und validiert YAML-Metadaten aus einer Stunden-Datei.

        Bei Lesefehlern oder ungültigem Frontmatter wird ein leeres Mapping
        zurückgegeben (best-effort Read-Pfad).
        """
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            return {}

        try:
            data, _ = parse_yaml_frontmatter(text, LESSON_SCHEMA, source_label=str(path))
            return {k: v for k, v in data.items()}
        except Exception:
            return {}

    def _ensure_index_for_path(self, lesson_path: Path) -> None:
        """Aktualisiert den Cache-Eintrag einer Datei bei fehlendem/veraltetem Zustand."""
        folder = str(lesson_path.parent.resolve()).lower()
        key = str(lesson_path.resolve()).lower()
        signature = self._file_signature(lesson_path) or (0, 0, 0)
        mtime, size, ctime_ns = signature
        with self._lock:
            table = self._cache.setdefault(folder, {})
            entry = table.get(key)
            if entry is None or entry.mtime_ns != mtime or entry.size != size or entry.ctime_ns != ctime_ns:
                data = self._read_metadata_from_file(lesson_path)
                table[key] = _IndexEntry(
                    path=lesson_path,
                    mtime_ns=mtime,
                    size=size,
                    ctime_ns=ctime_ns,
                    data=data,
                )

    def load_lessons_metadata_for_rows(self, table: PlanTableData, row_indices: List[int]) -> Dict[int, dict]:
        """Lädt indexbasierte Metadaten für ausgewählte Planzeilen."""
        result: Dict[int, dict] = {}
        for row_index in row_indices:
            link = get_row_link_path(table, row_index)
            if not link:
                continue
            self._ensure_index_for_path(link)
            folder = str(link.parent.resolve()).lower()
            key = str(link.resolve()).lower()
            with self._lock:
                entry = self._cache.get(folder, {}).get(key)
            if entry:
                result[row_index] = {
                    "Stundenthema": entry.data.get("Stundenthema", ""),
                    "Stundentyp": entry.data.get("Stundentyp", ""),
                    "Oberthema": entry.data.get("Oberthema", ""),
                    "path": entry.path,
                    "mtime_ns": entry.mtime_ns,
                    "index_version": self.INDEX_FORMAT_VERSION,
                }
        return result

    def load_lessons_metadata_for_all_rows(self, table: PlanTableData) -> Dict[int, dict]:
        """Lädt indexbasierte Metadaten für alle Zeilen einer Planung."""
        return self.load_lessons_metadata_for_rows(table, list(range(len(table.rows))))

    def invalidate_index(self, unterricht_dir: Path | None = None, subject_folder: str | None = None) -> None:
        """Invalidiert den In-Memory-Index global oder scoped."""
        started_at = time.perf_counter()
        scope = "global"
        if unterricht_dir is not None:
            scope = f"unterricht_dir={serialize_workspace_relative_path(unterricht_dir)}"
        elif subject_folder is not None:
            scope = f"subject_folder={subject_folder}"

        removed_folders = 0
        removed_entries = 0
        with self._lock:
            if unterricht_dir is None and subject_folder is None:
                removed_folders = len(self._cache)
                removed_entries = sum(len(entries) for entries in self._cache.values())
                self._cache.clear()
            elif unterricht_dir is not None:
                key = str(unterricht_dir.resolve()).lower()
                to_delete = [k for k in self._cache.keys() if k.startswith(key)]
                removed_folders = len(to_delete)
                removed_entries = sum(len(self._cache.get(k, {})) for k in to_delete)
                for k in to_delete:
                    self._cache.pop(k, None)
            elif subject_folder is not None:
                to_delete = [k for k in self._cache.keys() if Path(k).name.lower() == subject_folder.lower()]
                removed_folders = len(to_delete)
                removed_entries = sum(len(self._cache.get(k, {})) for k in to_delete)
                for k in to_delete:
                    self._cache.pop(k, None)

        duration_ms = (time.perf_counter() - started_at) * 1000.0
        self._logger.info(
            "lesson_index.invalidate completed",
            extra={
                "scope": scope,
                "removed_folders": removed_folders,
                "removed_entries": removed_entries,
                "duration_ms": round(duration_ms, 3),
            },
        )

    def rebuild_index(self, unterricht_dir: Path) -> None:
        """Führt einen vollständigen Neuaufbau des Index unterhalb eines Unterrichts-Roots aus."""
        started_at = time.perf_counter()
        scanned_files = 0
        updated_entries = 0
        errors = 0

        for child in unterricht_dir.iterdir():
            if not child.is_dir():
                continue
            for dir_name in managed_lesson_dir_names():
                stunden_dir = child / dir_name
                if not stunden_dir.exists() or not stunden_dir.is_dir():
                    continue
                for path in stunden_dir.iterdir():
                    if path.suffix.lower() != ".md":
                        continue
                    scanned_files += 1
                    try:
                        before_mtime = self._mtime_ns(path) or 0
                        folder = str(path.parent.resolve()).lower()
                        key = str(path.resolve()).lower()
                        with self._lock:
                            existing = self._cache.get(folder, {}).get(key)
                        existing_mtime = existing.mtime_ns if existing is not None else None
                        self._ensure_index_for_path(path)
                        if existing_mtime is None or existing_mtime != before_mtime:
                            updated_entries += 1
                    except Exception:
                        errors += 1
                        continue

        duration_ms = (time.perf_counter() - started_at) * 1000.0
        self._logger.info(
            "lesson_index.rebuild completed",
            extra={
                "unterricht_dir": serialize_workspace_relative_path(unterricht_dir),
                "scanned_files": scanned_files,
                "updated_entries": updated_entries,
                "errors": errors,
                "duration_ms": round(duration_ms, 3),
            },
        )

    def export_index_snapshot(self) -> dict:
        """Exportiert den aktuellen In-Memory-Index als versioniertes Snapshot-Objekt."""
        with self._lock:
            cache_data: dict[str, dict[str, dict]] = {}
            for folder, entries in self._cache.items():
                cache_data[folder] = {}
                for key, entry in entries.items():
                    cache_data[folder][key] = {
                        "path": serialize_workspace_relative_path(entry.path),
                        "mtime_ns": entry.mtime_ns,
                        "size": entry.size,
                        "ctime_ns": entry.ctime_ns,
                        "data": dict(entry.data),
                    }

            return {
                "version": self.INDEX_FORMAT_VERSION,
                "cache": cache_data,
            }

    def import_index_snapshot(self, snapshot: dict) -> None:
        """Importiert Snapshot-Daten; migriert ältere Snapshot-Versionen robust auf v2."""
        normalized = self._normalize_snapshot(snapshot)
        cache_raw = normalized.get("cache", {})
        if not isinstance(cache_raw, dict):
            raise RuntimeError("Invalid lesson index snapshot: cache must be a dict")

        new_cache: Dict[str, Dict[str, _IndexEntry]] = {}
        for folder, entries in cache_raw.items():
            if not isinstance(entries, dict):
                continue
            folder_key = str(folder).lower()
            new_cache[folder_key] = {}
            for key, item in entries.items():
                if not isinstance(item, dict):
                    continue
                path_text = str(item.get("path", ""))
                if not path_text:
                    continue
                mtime_ns = int(item.get("mtime_ns", 0))
                size = int(item.get("size", 0))
                ctime_ns = int(item.get("ctime_ns", 0))
                data = item.get("data", {})
                if not isinstance(data, dict):
                    data = {}
                new_cache[folder_key][str(key).lower()] = _IndexEntry(
                    path=Path(path_text),
                    mtime_ns=mtime_ns,
                    size=size,
                    ctime_ns=ctime_ns,
                    data=data,
                )

        with self._lock:
            self._cache = new_cache

    def _normalize_snapshot(self, snapshot: dict) -> dict:
        """Normalisiert Snapshot-Daten auf das aktuelle Indexformat (v2)."""
        if not isinstance(snapshot, dict):
            raise RuntimeError("Invalid lesson index snapshot")

        version = int(snapshot.get("version", 1))
        if version == self.INDEX_FORMAT_VERSION:
            return snapshot

        if version == 1:
            cache_raw = snapshot.get("cache", {})
            migrated: dict[str, dict[str, dict]] = {}
            if isinstance(cache_raw, dict):
                for folder, entries in cache_raw.items():
                    if not isinstance(entries, dict):
                        continue
                    folder_out: dict[str, dict] = {}
                    for key, item in entries.items():
                        if not isinstance(item, dict):
                            continue
                        mtime_ns = item.get("mtime_ns")
                        if mtime_ns is None:
                            mtime_ns = item.get("mtime", 0)
                        folder_out[str(key)] = {
                            "path": item.get("path", ""),
                            "mtime_ns": int(mtime_ns),
                            "size": int(item.get("size", 0)),
                            "ctime_ns": int(item.get("ctime_ns", 0)),
                            "data": item.get("data", {}),
                        }
                    migrated[str(folder)] = folder_out

            return {
                "version": self.INDEX_FORMAT_VERSION,
                "cache": migrated,
            }

        raise RuntimeError(f"Unsupported lesson index snapshot version: {version}")
