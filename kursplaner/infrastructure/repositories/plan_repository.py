from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from kursplaner.core.domain.course_subject import normalize_course_subject
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.wiki_links import build_wiki_link
from kursplaner.core.domain.yaml_registry import PLAN_METADATA_SCHEMA, parse_yaml_frontmatter
from kursplaner.infrastructure.repositories.plan_table_file_repository import (
    load_last_plan_table,
    save_plan_table,
)


@dataclass(frozen=True)
class _PlanListCacheEntry:
    paths: list[Path]
    base_mtime_ns: int | None
    child_mtime_ns: dict[str, int]


class FileSystemPlanRepository:
    """Plan-Repository (Dateisystem) - cached plan lists and plan tables."""

    def __init__(self):
        """Initialisiert Caches für Planlisten und geladene Tabellen."""
        self._plan_list_cache: dict[str, _PlanListCacheEntry] = {}
        self._dirty_cache_keys: set[str] = set()
        self._table_cache: dict[Path, tuple[float, int, PlanTableData]] = {}

    @staticmethod
    def _cache_key(base_dir: Path) -> str:
        """Bildet einen stabilen, case-insensitiven Cache-Key für ein Basisverzeichnis."""
        return str(base_dir.expanduser().resolve()).lower()

    def invalidate_plan_list_cache(self, base_dir: Path | None = None) -> None:
        """Markiert Planlisten-Cache global oder für ein Basisverzeichnis als dirty."""
        if base_dir is None:
            self._dirty_cache_keys = set(self._plan_list_cache.keys())
            self._table_cache.clear()
            return
        key = self._cache_key(base_dir)
        self._dirty_cache_keys.add(key)
        cached_paths = self._plan_list_cache.get(key, [])
        if cached_paths:
            for path in cached_paths.paths:
                self._table_cache.pop(path, None)

    def invalidate_cache(self, base_dir: Path | None = None) -> None:
        """Kompatibilitätsalias zur allgemeinen Cache-Invalidierung."""
        self.invalidate_plan_list_cache(base_dir)

    def load_plan_table(self, markdown_path: Path) -> PlanTableData:
        """Lädt die letzte Planungstabelle aus einer Plan-Markdowndatei."""
        return load_last_plan_table(markdown_path)

    def load_plan_tables(self, base_dir: Path) -> list[PlanTableData]:
        """Lädt alle Plan-Tabellen eines Basisordners mit Dateisignatur-Cache."""
        tables: list[PlanTableData] = []
        for markdown_path in self.list_plan_markdown_files(base_dir):
            stat = markdown_path.stat()
            signature = (stat.st_mtime, stat.st_size)
            cached = self._table_cache.get(markdown_path)
            if cached is not None and cached[0] == signature[0] and cached[1] == signature[1]:
                table = cached[2]
            else:
                table = load_last_plan_table(markdown_path)
                self._table_cache[markdown_path] = (signature[0], signature[1], table)
            tables.append(table)
        return tables

    def save_plan_table(self, table: PlanTableData) -> None:
        """Persistiert eine Planungstabelle in ihre zugehörige Datei."""
        save_plan_table(table)

    def list_plan_markdown_files(self, base_dir: Path) -> list[Path]:
        """Listet Plan-Markdowndateien und nutzt einen Frische-Cache pro Basisordner."""
        if not base_dir.exists() or not base_dir.is_dir():
            return []

        key = self._cache_key(base_dir)
        cached = self._plan_list_cache.get(key)
        if (
            cached is not None
            and key not in self._dirty_cache_keys
            and self._plan_list_cache_is_fresh(base_dir, cached)
        ):
            return list(cached.paths)

        paths, child_mtimes = self._scan_plan_markdown_files(base_dir)

        base_stat = base_dir.stat()
        self._plan_list_cache[key] = _PlanListCacheEntry(
            paths=list(paths),
            base_mtime_ns=getattr(base_stat, "st_mtime_ns", int(base_stat.st_mtime * 1_000_000_000)),
            child_mtime_ns=child_mtimes,
        )
        self._dirty_cache_keys.discard(key)
        return paths

    @staticmethod
    def _mtime_ns(path: Path) -> int | None:
        """Liefert Dateizeitstempel in Nanosekunden oder `None` bei fehlendem Pfad."""
        if not path.exists():
            return None
        stat = path.stat()
        return getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))

    def _scan_plan_markdown_files(self, base_dir: Path) -> tuple[list[Path], dict[str, int]]:
        """Scannt Kinderordner nach gleichnamigen Plan-Markdowndateien."""
        paths: list[Path] = []
        child_mtimes: dict[str, int] = {}

        for child in sorted(base_dir.iterdir(), key=lambda item: item.name.lower()):
            if not child.is_dir():
                continue
            mtime = self._mtime_ns(child)
            if mtime is not None:
                child_mtimes[str(child.resolve()).lower()] = mtime

            plan_path = child / f"{child.name}.md"
            if plan_path.exists() and plan_path.is_file():
                paths.append(plan_path)

        return paths, child_mtimes

    def _plan_list_cache_is_fresh(self, base_dir: Path, entry: _PlanListCacheEntry) -> bool:
        """Prüft, ob Basisordner und beobachtete Kinder unverändert geblieben sind."""
        current_base_mtime = self._mtime_ns(base_dir)
        if current_base_mtime is None:
            return False

        if current_base_mtime != entry.base_mtime_ns:
            return False

        for child_key, expected_mtime in entry.child_mtime_ns.items():
            child_path = Path(child_key)
            current_child_mtime = self._mtime_ns(child_path)
            if current_child_mtime is None or current_child_mtime != expected_mtime:
                return False

        return True

    def load_plan_metadata(self, markdown_path: Path) -> dict[str, str]:
        """Extrahiert YAML-Frontmatter-Metadaten als String-Dictionary."""
        text = markdown_path.read_text(encoding="utf-8")
        metadata, _ = parse_yaml_frontmatter(text, PLAN_METADATA_SCHEMA, source_label=str(markdown_path))
        return {key: str(value) for key, value in metadata.items()}

    def append_plan_rows(
        self, markdown_path: Path, rows: list[tuple], confirm_change: Callable[[str, str], bool] | None = None
    ) -> None:
        """Haengt neue Planzeilen an die bestehende letzte Planungstabelle an."""

        if not rows:
            return

        if confirm_change is not None:
            allowed = confirm_change(
                "Plan-Tabelle anhängen",
                f"Datei wird geändert:\n{markdown_path}\n\nNeue Zeilen: {len(rows)}",
            )
            if not allowed:
                raise RuntimeError("Schreibvorgang für Plan-Tabelle abgebrochen.")

        table = load_last_plan_table(markdown_path)
        for day, hours, note in rows:
            table.rows.append([day.strftime("%d-%m-%y"), str(hours), str(note)])
        save_plan_table(table)

    def write_plan_rows(
        self, markdown_path: Path, rows: list[tuple], confirm_change: Callable[[str, str], bool] | None = None
    ) -> None:
        """Schreibt Planzeilen als initiale oder ersetzte Haupttabelle."""
        if not rows:
            return

        if confirm_change is not None:
            allowed = confirm_change(
                "Plan-Tabelle schreiben",
                f"Datei wird geändert:\n{markdown_path}\n\nNeue Zeilen: {len(rows)}",
            )
            if not allowed:
                raise RuntimeError("Schreibvorgang für Plan-Tabelle abgebrochen.")

        normalized_rows = [[day.strftime("%d-%m-%y"), str(hours), str(note)] for day, hours, note in rows]

        try:
            table = load_last_plan_table(markdown_path)
        except RuntimeError:
            base_text = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
            prefix = base_text
            if prefix and not prefix.endswith("\n"):
                prefix += "\n"
            if prefix and not prefix.endswith("\n\n"):
                prefix += "\n"

            rendered_rows = [f"| {row[0]} | {row[1]} | {row[2]} |" for row in normalized_rows]
            table_text = "\n".join(
                [
                    "| Datum | Stunden | Inhalt |",
                    "| --- | --- | --- |",
                    *rendered_rows,
                ]
            )
            markdown_path.write_text(prefix + table_text + "\n", encoding="utf-8")
            return

        table.rows = normalized_rows
        save_plan_table(table)

    @staticmethod
    def _yaml_quote(value: str) -> str:
        """Quotet Frontmatter-Werte robust für einfache YAML-Scalars."""
        escaped = value.replace('"', '\\"')
        return f'"{escaped}"'

    def write_plan_metadata(
        self,
        markdown_path: Path,
        group_name: str,
        course_subject: str,
        grade_level: int,
        kc_profile_label: str | None = None,
        process_competencies: tuple[str, ...] = (),
        content_competency: str | None = None,
    ) -> None:
        """Schreibt/ersetzt den YAML-Frontmatterblock für Plan-Metadaten."""
        text = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
        body = text

        if body.startswith("---\n"):
            end = body.find("\n---", 4)
            if end != -1:
                body = body[end + 4 :]
                body = body.lstrip("\n")

        group_link = build_wiki_link(group_name)
        canonical_course_subject = normalize_course_subject(course_subject)

        lines = [
            "---",
            f"Lerngruppe: {self._yaml_quote(group_link)}",
            f"Kursfach: {self._yaml_quote(canonical_course_subject)}",
            f"Stufe: {grade_level}",
        ]

        normalized_process = tuple(item.strip() for item in process_competencies if item.strip())
        if kc_profile_label and kc_profile_label.strip():
            lines.append(f"KC-Profil: {self._yaml_quote(kc_profile_label.strip())}")
        if normalized_process:
            lines.append("Kompetenzen:")
            for item in normalized_process:
                lines.append(f"  - {self._yaml_quote(item)}")
        if content_competency and content_competency.strip():
            lines.append(f"Stundenziel: {self._yaml_quote(content_competency.strip())}")

        frontmatter = "\n".join(lines) + "\n---\n\n"

        markdown_path.write_text(frontmatter + body, encoding="utf-8")
