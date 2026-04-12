from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.course_subject import normalize_course_subject
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.unterrichtsbesuch_policy import (
    UB_KIND_FACH,
    UB_KIND_PAEDAGOGIK,
    UB_YAML_KEY_BEOBACHTUNG,
    UB_YAML_KEY_BEREICH,
    UB_YAML_KEY_EINHEIT,
    UB_YAML_KEY_LANGENTWURF,
    build_ub_stem,
    normalize_ub_kinds,
)
from kursplaner.core.domain.wiki_links import build_wiki_link, strip_wiki_link
from kursplaner.core.ports.repositories import LessonRepository, UbRepository
from kursplaner.core.usecases.ub_markdown_sections import parse_list_section
from kursplaner.core.usecases.ub_overview_builder import build_ub_overview_markdown


@dataclass(frozen=True)
class MarkUnitAsUbResult:
    """Ergebnis des UB-Markierungs-Writeflows."""

    proceed: bool
    lesson_path: Path | None = None
    ub_path: Path | None = None
    overview_path: Path | None = None
    error_message: str | None = None


class MarkUnitAsUbUseCase:
    """Erstellt/aktualisiert UB-Markdowns und verknuepft die Einheit-YAML."""

    def __init__(self, lesson_repo: LessonRepository, ub_repo: UbRepository):
        """Initialisiert den Use Case mit Port-basierten Repositoryabhaengigkeiten."""
        self.lesson_repo = lesson_repo
        self.ub_repo = ub_repo

    @staticmethod
    def _header_index(table: PlanTableData, key: str) -> int:
        mapping = {name.lower(): idx for idx, name in enumerate(table.headers)}
        idx = mapping.get(key.lower())
        if idx is None:
            raise RuntimeError(f"Plan-Tabelle muss Spalte '{key}' enthalten.")
        return idx

    def _resolve_existing_ub_path(self, workspace_root: Path, lesson_data: dict[str, object]) -> Path | None:
        raw_link = strip_wiki_link(str(lesson_data.get("Unterrichtsbesuch", "")).strip())
        if not raw_link:
            return None

        root = self.ub_repo.ensure_ub_root(workspace_root)
        candidate = root / f"{raw_link}.md"
        if candidate.exists() and candidate.is_file():
            return candidate
        return None

    @staticmethod
    def _unit_title_from_lesson_stem(lesson_path: Path) -> str:
        """Leitet den inhaltlichen Einheitstitel aus dem Dateistamm ab."""
        stem = str(lesson_path.stem).strip()
        if not stem:
            return ""
        parts = stem.split(" ", 2)
        if len(parts) >= 3:
            return parts[2].strip()
        return stem

    def execute(
        self,
        *,
        workspace_root: Path,
        table: PlanTableData,
        row_index: int,
        ub_kinds: list[str] | tuple[str, ...],
        langentwurf: bool,
        beobachtungsschwerpunkt: str,
    ) -> MarkUnitAsUbResult:
        """Fuehrt die UB-Markierung fuer genau eine Unterrichtseinheit aus."""
        if row_index < 0 or row_index >= len(table.rows):
            return MarkUnitAsUbResult(proceed=False, error_message="Zeilenindex außerhalb der Planungstabelle.")

        try:
            kinds = normalize_ub_kinds(list(ub_kinds))
        except ValueError as exc:
            return MarkUnitAsUbResult(proceed=False, error_message=str(exc))

        lesson_path = self.lesson_repo.resolve_row_link_path(table, row_index)
        if not isinstance(lesson_path, Path) or not lesson_path.exists() or not lesson_path.is_file():
            return MarkUnitAsUbResult(proceed=False, error_message="Keine verlinkte Einheit für die gewählte Zeile.")

        lesson = self.lesson_repo.load_lesson_yaml(lesson_path)
        lesson_data = lesson.data if isinstance(lesson.data, dict) else {}

        if str(lesson_data.get("Stundentyp", "")).strip() != "Unterricht":
            return MarkUnitAsUbResult(proceed=False, error_message="UB-Markierung ist nur für Unterricht erlaubt.")

        idx_datum = self._header_index(table, "datum")
        date_text = table.rows[row_index][idx_datum] if idx_datum < len(table.rows[row_index]) else ""
        unit_title = self._unit_title_from_lesson_stem(lesson_path)

        course_subject = normalize_course_subject(str(table.metadata.get("Kursfach", "")))
        bereich: list[str] = []
        if UB_KIND_PAEDAGOGIK in kinds:
            bereich.append(UB_KIND_PAEDAGOGIK)
        if UB_KIND_FACH in kinds:
            bereich.append(course_subject)

        ub_path = self._resolve_existing_ub_path(workspace_root, lesson_data)
        if ub_path is None:
            desired_stem = build_ub_stem(date_text, unit_title)
            ub_path = self.ub_repo.unique_ub_markdown_path(workspace_root, desired_stem)

        existing_steps: list[str] = []
        existing_resources: list[str] = []
        if ub_path.exists() and ub_path.is_file():
            try:
                _, existing_body = self.ub_repo.load_ub_markdown(ub_path)
                existing_steps = parse_list_section(existing_body, "Professionalisierungsschritte")
                existing_resources = parse_list_section(existing_body, "Nutzbare Ressourcen")
            except Exception:
                existing_steps = []
                existing_resources = []

        ub_yaml = {
            UB_YAML_KEY_BEREICH: bereich,
            UB_YAML_KEY_LANGENTWURF: bool(langentwurf),
            UB_YAML_KEY_BEOBACHTUNG: str(beobachtungsschwerpunkt or "").strip(),
            UB_YAML_KEY_EINHEIT: build_wiki_link(lesson_path.stem),
        }

        self.ub_repo.save_ub_markdown(
            ub_path,
            ub_yaml,
            reflection_text="",
            professional_steps=existing_steps,
            usable_resources=existing_resources,
        )

        lesson_data["Unterrichtsbesuch"] = build_wiki_link(ub_path.stem)
        lesson.data = lesson_data
        self.lesson_repo.save_lesson_yaml(lesson)

        overview_markdown = build_ub_overview_markdown(self.ub_repo, workspace_root)
        overview_path = self.ub_repo.save_ub_overview(workspace_root, overview_markdown)

        return MarkUnitAsUbResult(
            proceed=True,
            lesson_path=lesson_path,
            ub_path=ub_path,
            overview_path=overview_path,
        )
