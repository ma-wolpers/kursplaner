from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from bw_libs.app_paths import atomic_write_json
from kursplaner.core.config.path_store import (
    BAUKASTEN_DIR_KEY,
    FACHDIDAKTIK_DIR_KEY,
    FACHINHALTE_DIR_KEY,
    load_path_values,
    resolve_path_value,
)


@dataclass(frozen=True)
class _SubjectSourceCacheEntry:
    inhalte: list[str]
    methodik: list[str]
    inhalte_dir_key: str
    methodik_dir_key: str
    inhalte_dir_mtime_ns: int | None
    methodik_dir_mtime_ns: int | None


class FileSystemSubjectSourceRepository:
    _MANIFEST_NAME = ".kursplaner_subject_index.json"

    def __init__(self):
        """Initialisiert den in-memory Cache pro Unterrichtspfad und Fach."""
        self._cache: dict[tuple[str, str], _SubjectSourceCacheEntry] = {}

    @staticmethod
    def _find_named_child(parent: Path, keywords: tuple[str, ...]) -> Path | None:
        """Findet ein Unterverzeichnis, dessen Name eines der Keywords enthält."""
        if not parent.exists() or not parent.is_dir():
            return None

        normalized = [keyword.lower().replace(" ", "") for keyword in keywords]
        for child in parent.iterdir():
            if not child.is_dir():
                continue
            token = child.name.lower().replace(" ", "")
            if any(keyword in token for keyword in normalized):
                return child
        return None

    @staticmethod
    def _mtime_ns(path: Path) -> int | None:
        """Liest `mtime` in Nanosekunden oder `None`, falls der Pfad fehlt."""
        if not path.exists():
            return None
        stat = path.stat()
        return getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))

    @staticmethod
    def _dir_key(path: Path) -> str:
        """Erzeugt einen stabilen, case-insensitiven Schlüssel für Verzeichnisse."""
        return str(path.resolve()).lower()

    def _manifest_path(self, folder: Path) -> Path:
        """Liefert den Pfad zur Index-Manifestdatei eines Quellenordners."""
        return folder / self._MANIFEST_NAME

    def _load_manifest(self, folder: Path) -> dict[str, object] | None:
        """Lädt ein gültiges Manifest (Version 1) oder `None` bei Ungültigkeit."""
        manifest_path = self._manifest_path(folder)
        if not manifest_path.exists() or not manifest_path.is_file():
            return None

        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return None

        if not isinstance(raw, dict):
            return None
        if raw.get("version") != 1:
            return None
        return raw

    def _collect_dir_mtimes(self, folder: Path) -> dict[str, int]:
        """Erfasst `mtime`-Signaturen aller Unterordner relativ zum Root."""
        if not folder.exists() or not folder.is_dir():
            return {}

        mtimes: dict[str, int] = {".": self._mtime_ns(folder) or 0}
        for path in folder.rglob("*"):
            if not path.is_dir():
                continue
            rel = path.relative_to(folder).as_posix()
            mtimes[rel] = self._mtime_ns(path) or 0
        return mtimes

    def _scan_markdown_files(self, folder: Path) -> dict[str, int]:
        """Scannt Markdown-Dateien rekursiv und liefert relative Pfade mit `mtime`."""
        if not folder.exists() or not folder.is_dir():
            return {}

        collected: dict[str, int] = {}
        for path in folder.rglob("*.md"):
            if not path.is_file() or path.name == self._MANIFEST_NAME:
                continue
            rel = path.relative_to(folder).as_posix()
            mtime = self._mtime_ns(path)
            if mtime is not None:
                collected[rel] = mtime
        return collected

    def _stems_from_files(self, files: dict[str, int]) -> list[str]:
        """Leitet eindeutige Dateistämme aus relativen Dateipfaden ab."""
        stems = [Path(rel).stem.strip() for rel in files.keys() if Path(rel).stem.strip()]
        return sorted(set(stems), key=lambda text: text.lower())

    def _write_manifest(self, folder: Path, files: dict[str, int], dirs: dict[str, int]) -> None:
        """Schreibt Manifestdaten robust; I/O-Fehler werden toleriert."""
        payload = {
            "version": 1,
            "root_mtime_ns": self._mtime_ns(folder),
            "dirs": dirs,
            "files": files,
            "stems": self._stems_from_files(files),
        }
        try:
            atomic_write_json(self._manifest_path(folder), payload)
        except Exception:
            return

    def _load_stems_incremental(self, folder: Path) -> tuple[list[str], int | None]:
        """Lädt Themenstämme inkrementell über Manifest + Verzeichnisänderungen."""
        if not folder.exists() or not folder.is_dir():
            return [], None

        current_root_mtime = self._mtime_ns(folder)
        manifest = self._load_manifest(folder)
        if manifest is not None:
            manifest_root_mtime = manifest.get("root_mtime_ns")
            stems = manifest.get("stems")
            if manifest_root_mtime == current_root_mtime and isinstance(stems, list):
                normalized_stems = [str(item).strip() for item in stems if str(item).strip()]
                return sorted(set(normalized_stems), key=lambda text: text.lower()), current_root_mtime

        if manifest is None:
            files = self._scan_markdown_files(folder)
            dirs = self._collect_dir_mtimes(folder)
            self._write_manifest(folder, files, dirs)
            return self._stems_from_files(files), current_root_mtime

        known_files_raw = manifest.get("files", {})
        known_dirs_raw = manifest.get("dirs", {})
        known_files_dict = known_files_raw if isinstance(known_files_raw, dict) else {}
        known_dirs_dict = known_dirs_raw if isinstance(known_dirs_raw, dict) else {}
        known_files: dict[str, int] = {str(rel): int(mtime) for rel, mtime in known_files_dict.items()}
        known_dirs: dict[str, int] = {str(rel): int(mtime) for rel, mtime in known_dirs_dict.items()}

        updated_files: dict[str, int] = {}
        for rel in list(known_files.keys()):
            path = folder / rel
            mtime = self._mtime_ns(path) if path.exists() and path.is_file() else None
            if mtime is not None:
                updated_files[rel] = mtime

        current_dirs = self._collect_dir_mtimes(folder)
        changed_dirs: set[str] = set()
        for rel, mtime in current_dirs.items():
            if known_dirs.get(rel) != mtime:
                changed_dirs.add(rel)
        for rel in known_dirs.keys():
            if rel not in current_dirs:
                changed_dirs.add(rel)

        def _is_under(rel_file: str, rel_dir: str) -> bool:
            if rel_dir in {"", "."}:
                return True
            return rel_file == rel_dir or rel_file.startswith(f"{rel_dir}/")

        if changed_dirs:
            for rel_dir in changed_dirs:
                for rel_file in list(updated_files.keys()):
                    if _is_under(rel_file, rel_dir):
                        updated_files.pop(rel_file, None)

            for rel_dir in changed_dirs:
                target_dir = folder if rel_dir in {"", "."} else (folder / rel_dir)
                if not target_dir.exists() or not target_dir.is_dir():
                    continue
                for path in target_dir.rglob("*.md"):
                    if not path.is_file() or path.name == self._MANIFEST_NAME:
                        continue
                    rel = path.relative_to(folder).as_posix()
                    mtime = self._mtime_ns(path)
                    if mtime is not None:
                        updated_files[rel] = mtime

        self._write_manifest(folder, updated_files, current_dirs)
        return self._stems_from_files(updated_files), current_root_mtime

    def _subject_roots(self, unterricht_dir: Path) -> tuple[Path | None, Path | None]:
        """Ermittelt Fachinhalte-/Fachdidaktik-Roots aus Settings mit Fallback."""
        values = load_path_values()
        baukasten_dir = resolve_path_value(values.get(BAUKASTEN_DIR_KEY, ""))
        if not baukasten_dir.exists() or not baukasten_dir.is_dir():
            baukasten_dir = unterricht_dir.parent / "30 Baukasten"

        fachinhalte_candidate = resolve_path_value(values.get(FACHINHALTE_DIR_KEY, ""))
        if fachinhalte_candidate.exists() and fachinhalte_candidate.is_dir():
            fachinhalte_root = fachinhalte_candidate
        else:
            fachinhalte_root = self._find_named_child(baukasten_dir, ("34 fachinhalte", "34 fachenhalte"))

        fachdidaktik_candidate = resolve_path_value(values.get(FACHDIDAKTIK_DIR_KEY, ""))
        if fachdidaktik_candidate.exists() and fachdidaktik_candidate.is_dir():
            fachdidaktik_root = fachdidaktik_candidate
        else:
            fachdidaktik_root = self._find_named_child(baukasten_dir, ("33 fachdidaktik",))
        return fachinhalte_root, fachdidaktik_root

    def _available_subjects(self, fachinhalte_root: Path | None, fachdidaktik_root: Path | None) -> list[str]:
        """Vereinigt verfügbare Fachordner aus beiden Quellenwurzeln."""
        subjects: set[str] = set()
        for root in (fachinhalte_root, fachdidaktik_root):
            if root is None or not root.exists() or not root.is_dir():
                continue
            for child in root.iterdir():
                if child.is_dir() and child.name.strip():
                    subjects.add(child.name.strip())
        return sorted(subjects, key=lambda text: text.lower())

    def rebuild_index(self, unterricht_dir: Path, subject_folder: str | None = None) -> int:
        """Baut Manifest-Indizes vollständig neu auf, optional nur für ein Fach."""
        resolved_dir = unterricht_dir.expanduser().resolve()
        if not resolved_dir.exists() or not resolved_dir.is_dir():
            return 0

        fachinhalte_root, fachdidaktik_root = self._subject_roots(resolved_dir)
        if subject_folder is not None and subject_folder.strip():
            targets = [subject_folder.strip()]
        else:
            targets = self._available_subjects(fachinhalte_root, fachdidaktik_root)

        rebuilt = 0
        for subject in targets:
            inhalte_dir = (fachinhalte_root / subject) if fachinhalte_root is not None else Path()
            methodik_dir = (fachdidaktik_root / subject) if fachdidaktik_root is not None else Path()

            for folder in (inhalte_dir, methodik_dir):
                if not folder.exists() or not folder.is_dir():
                    continue
                files = self._scan_markdown_files(folder)
                dirs = self._collect_dir_mtimes(folder)
                self._write_manifest(folder, files, dirs)
                rebuilt += 1

        self.invalidate_cache(unterricht_dir=resolved_dir, subject_folder=subject_folder)
        return rebuilt

    def resolve_subject_sources(self, unterricht_dir: Path, subject_folder: str) -> tuple[list[str], list[str]]:
        """Liefert Fachquellen (Inhalte/Methodik) für ein Fach mit Cache-Validierung."""
        key = (str(unterricht_dir.expanduser().resolve()).lower(), subject_folder.strip().lower())

        fachinhalte_root, fachdidaktik_root = self._subject_roots(unterricht_dir)

        inhalte_dir = (fachinhalte_root / subject_folder) if fachinhalte_root else Path()
        methodik_dir = (fachdidaktik_root / subject_folder) if fachdidaktik_root else Path()

        inhalte_dir_key = self._dir_key(inhalte_dir) if inhalte_dir.exists() and inhalte_dir.is_dir() else ""
        methodik_dir_key = self._dir_key(methodik_dir) if methodik_dir.exists() and methodik_dir.is_dir() else ""
        inhalte_mtime = self._mtime_ns(inhalte_dir) if inhalte_dir_key else None
        methodik_mtime = self._mtime_ns(methodik_dir) if methodik_dir_key else None

        cached = self._cache.get(key)
        if (
            cached is not None
            and cached.inhalte_dir_key == inhalte_dir_key
            and cached.methodik_dir_key == methodik_dir_key
            and cached.inhalte_dir_mtime_ns == inhalte_mtime
            and cached.methodik_dir_mtime_ns == methodik_mtime
        ):
            return cached.inhalte, cached.methodik

        inhalte, inhalte_current_mtime = self._load_stems_incremental(inhalte_dir)
        methodik, methodik_current_mtime = self._load_stems_incremental(methodik_dir)

        entry = _SubjectSourceCacheEntry(
            inhalte=inhalte,
            methodik=methodik,
            inhalte_dir_key=inhalte_dir_key,
            methodik_dir_key=methodik_dir_key,
            inhalte_dir_mtime_ns=inhalte_current_mtime,
            methodik_dir_mtime_ns=methodik_current_mtime,
        )
        self._cache[key] = entry
        return inhalte, methodik

    def invalidate_cache(self, unterricht_dir: Path | None = None, subject_folder: str | None = None) -> None:
        """Invalidiert den Quellen-Cache global oder gefiltert nach Pfad/Fach."""
        if unterricht_dir is None and subject_folder is None:
            self._cache.clear()
            return

        normalized_dir = str(unterricht_dir.expanduser().resolve()).lower() if unterricht_dir is not None else None
        normalized_subject = subject_folder.strip().lower() if subject_folder is not None else None

        to_remove: list[tuple[str, str]] = []
        for key_dir, key_subject in self._cache.keys():
            if normalized_dir is not None and key_dir != normalized_dir:
                continue
            if normalized_subject is not None and key_subject != normalized_subject:
                continue
            to_remove.append((key_dir, key_subject))

        for key in to_remove:
            self._cache.pop(key, None)
