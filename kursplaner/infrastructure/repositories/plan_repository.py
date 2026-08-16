from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from bw_libs.app_paths import atomic_write_text
from kursplaner.core.domain.course_lifecycle import course_archive_root
from kursplaner.core.domain.course_rhythm import WeekdayRhythm, format_rhythm
from kursplaner.core.domain.course_subject import normalize_course_subject
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.wiki_links import build_wiki_link
from kursplaner.core.domain.yaml_registry import PLAN_METADATA_SCHEMA, parse_yaml_frontmatter
from kursplaner.infrastructure.repositories.plan_table_file_repository import (
    load_last_plan_table,
    save_plan_table,
    sync_thema_ausfall_to_plan_row,
)


@dataclass(frozen=True)
class _PlanListCacheEntry:
    paths: list[Path]
    root_mtime_ns: dict[str, int]
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

    def sync_thema_ausfall_to_plan_row(
        self,
        table: PlanTableData,
        row_index: int,
        yaml_data: dict[str, object],
        group_name: str,
    ) -> None:
        """Aktualisiert die Thema/Ausfall-Spalte einer Planzeile anhand YAML-Stundendaten."""
        sync_thema_ausfall_to_plan_row(table, row_index, yaml_data=yaml_data, group_name=group_name)

    def list_plan_markdown_files(self, base_dir: Path) -> list[Path]:
        """Listet Plan-Markdowndateien (aktiv und archiviert) mit Frische-Cache pro Basisordner.

        Durchsucht sowohl `base_dir` als auch `base_dir/_ALT/Kursordner` (siehe
        `course_lifecycle.course_archive_root`) - die zurückgelieferte Liste
        umfasst also sowohl aktive als auch archivierte Kurse. Aufrufer, die
        beide unterscheiden müssen, nutzen `course_lifecycle.is_archived_course_path`.
        """
        if not base_dir.exists() or not base_dir.is_dir():
            return []

        key = self._cache_key(base_dir)
        cached = self._plan_list_cache.get(key)
        if (
            cached is not None
            and key not in self._dirty_cache_keys
            and self._plan_list_cache_is_fresh(cached)
        ):
            return list(cached.paths)

        roots = [base_dir]
        archive_root = course_archive_root(base_dir)
        if archive_root.exists() and archive_root.is_dir():
            roots.append(archive_root)

        paths: list[Path] = []
        child_mtimes: dict[str, int] = {}
        root_mtimes: dict[str, int] = {}
        for root in roots:
            root_mtime = self._mtime_ns(root)
            if root_mtime is not None:
                root_mtimes[str(root.resolve()).lower()] = root_mtime
            root_paths, root_child_mtimes = self._scan_plan_markdown_files(root)
            paths.extend(root_paths)
            child_mtimes.update(root_child_mtimes)

        self._plan_list_cache[key] = _PlanListCacheEntry(
            paths=paths,
            root_mtime_ns=root_mtimes,
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

    def _plan_list_cache_is_fresh(self, entry: _PlanListCacheEntry) -> bool:
        """Prüft, ob alle beobachteten Wurzeln und Kinder unverändert geblieben sind."""
        for root_key, expected_mtime in entry.root_mtime_ns.items():
            if self._mtime_ns(Path(root_key)) != expected_mtime:
                return False

        for child_key, expected_mtime in entry.child_mtime_ns.items():
            if self._mtime_ns(Path(child_key)) != expected_mtime:
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
        for day, note in rows:
            note_str = str(note) if note else ""
            table.rows.append([day.strftime("%d-%m-%y"), "", note_str])
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

        normalized_rows = [
            [day.strftime("%d-%m-%y"), "", str(note) if note else ""] for day, note in rows
        ]

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
                    "| Datum | Inhalt | Thema/Ausfall |",
                    "| --- | --- | --- |",
                    *rendered_rows,
                ]
            )
            atomic_write_text(markdown_path, prefix + table_text + "\n", encoding="utf-8")
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
        rhythm: tuple[WeekdayRhythm, ...],
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
            "Rhythmus:",
        ]
        lines.extend(f"  - {self._yaml_quote(entry)}" for entry in format_rhythm(rhythm))

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

        atomic_write_text(markdown_path, frontmatter + body, encoding="utf-8")

    def update_plan_rhythm(self, markdown_path: Path, rhythm: tuple[WeekdayRhythm, ...]) -> None:
        """Ersetzt chirurgisch nur den ``Rhythmus``-Block der Plan-Datei-Frontmatter.

        Im Gegensatz zu :meth:`write_plan_metadata` (vollstaendiger Rewrite bei
        Kursanlage) bleiben alle anderen Frontmatter-Felder (z. B.
        ``Kompetenzen``, ``Stundenziel``) unveraendert und in ihrer
        urspruenglichen Reihenfolge erhalten - wird von einer
        Stundenplanaenderung genutzt, die nur den Rhythmus ergaenzt.

        Args:
            markdown_path: Zielpfad der Plan-Markdown-Datei.
            rhythm: Vollstaendige, neue Rhythmus-Eintragsliste (alle Segmente).

        Raises:
            RuntimeError: Wenn die Datei kein ``Rhythmus``-Feld in der
                Frontmatter enthaelt (unmigrierte Datei).
        """
        text = markdown_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            raise RuntimeError(f"Fehlendes YAML-Frontmatter in Plan-Datei: {markdown_path}")

        start_idx: int | None = None
        end_idx: int | None = None
        for idx in range(1, len(lines)):
            stripped = lines[idx].strip()
            if stripped == "---":
                if start_idx is not None and end_idx is None:
                    end_idx = idx
                break
            if stripped.startswith("Rhythmus:"):
                start_idx = idx
                continue
            if start_idx is not None and end_idx is None:
                if stripped.startswith("- ") or stripped.startswith('- "'):
                    continue
                end_idx = idx

        if start_idx is None:
            raise RuntimeError(f"Plan-Datei hat kein 'Rhythmus'-Feld: {markdown_path}")
        if end_idx is None:
            end_idx = len(lines)

        replacement = ["Rhythmus:"] + [f"  - {self._yaml_quote(entry)}" for entry in format_rhythm(rhythm)]
        new_lines = lines[:start_idx] + replacement + lines[end_idx:]

        output = "\n".join(new_lines)
        if text.endswith("\n"):
            output += "\n"
        atomic_write_text(markdown_path, output, encoding="utf-8")
