from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from kursplaner.core.config.path_store import infer_workspace_root_from_path
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.wiki_links import build_wiki_link, strip_wiki_link
from kursplaner.core.ports.repositories import LessonRepository, UbRepository
from kursplaner.core.usecases.ub_overview_builder import build_ub_overview_markdown

UbReconcileAction = Literal["fix_overview", "fix_lesson", "ignore"]


@dataclass(frozen=True)
class UbReconcileConflict:
    """Ein identifizierter UB-Konsistenzkonflikt für genau eine Einheit."""

    kind: str
    row_index: int
    lesson_path: Path
    ub_stem: str
    ub_path: Path
    message: str


@dataclass(frozen=True)
class UbReconcileScanResult:
    """Konfliktliste des UB-Abgleichs."""

    conflicts: list[UbReconcileConflict]


@dataclass(frozen=True)
class UbReconcileApplyResult:
    """Ergebnis einer angewendeten Konfliktauflösung."""

    proceed: bool
    error_message: str | None = None


class ReconcileUbOverviewUseCase:
    """Vergleicht Einheit-YAML, UB-Dateien und UB-Übersicht und löst Konflikte auf."""

    def __init__(self, lesson_repo: LessonRepository, ub_repo: UbRepository):
        self.lesson_repo = lesson_repo
        self.ub_repo = ub_repo

    @staticmethod
    def _overview_links(text: str) -> set[str]:
        links: set[str] = set()
        for line in str(text or "").splitlines():
            line_text = line.strip()
            if not line_text.startswith("|"):
                continue
            if "[[" not in line_text or "]]" not in line_text:
                continue
            start = line_text.find("[[")
            end = line_text.find("]]", start + 2)
            if start < 0 or end < 0:
                continue
            stem = line_text[start + 2 : end].split("|", 1)[0].strip()
            if stem:
                links.add(stem)
        return links

    @staticmethod
    def _workspace_root_from_table(table: PlanTableData) -> Path:
        return infer_workspace_root_from_path(table.markdown_path)

    def scan(self, table: PlanTableData) -> UbReconcileScanResult:
        """Identifiziert UB-Konflikte für den geladenen Plan."""
        workspace_root = self._workspace_root_from_table(table)
        overview_links = self._overview_links(self.ub_repo.load_ub_overview(workspace_root))

        conflicts: list[UbReconcileConflict] = []
        for row_index in range(len(table.rows)):
            lesson_path = self.lesson_repo.resolve_row_link_path(table, row_index)
            if not isinstance(lesson_path, Path) or not lesson_path.exists() or not lesson_path.is_file():
                continue

            lesson = self.lesson_repo.load_lesson_yaml(lesson_path)
            data = lesson.data if isinstance(lesson.data, dict) else {}
            ub_stem = strip_wiki_link(str(data.get("Unterrichtsbesuch", "")).strip())
            if not ub_stem:
                continue

            ub_path = self.ub_repo.ensure_ub_root(workspace_root) / f"{ub_stem}.md"
            if not ub_path.exists() or not ub_path.is_file():
                conflicts.append(
                    UbReconcileConflict(
                        kind="missing_ub_file",
                        row_index=row_index,
                        lesson_path=lesson_path,
                        ub_stem=ub_stem,
                        ub_path=ub_path,
                        message="Einheit verweist auf UB-Datei, die nicht existiert.",
                    )
                )
                continue

            try:
                ub_yaml, _ = self.ub_repo.load_ub_markdown(ub_path)
                backlink = strip_wiki_link(str(ub_yaml.get("Einheit", "")).strip())
            except Exception:
                conflicts.append(
                    UbReconcileConflict(
                        kind="ub_yaml_invalid",
                        row_index=row_index,
                        lesson_path=lesson_path,
                        ub_stem=ub_stem,
                        ub_path=ub_path,
                        message="UB-Datei hat kein gültiges YAML-Frontmatter.",
                    )
                )
                continue

            if backlink != lesson_path.stem:
                conflicts.append(
                    UbReconcileConflict(
                        kind="backlink_mismatch",
                        row_index=row_index,
                        lesson_path=lesson_path,
                        ub_stem=ub_stem,
                        ub_path=ub_path,
                        message="UB-Backlink verweist auf eine andere Einheit.",
                    )
                )

            if ub_stem not in overview_links:
                conflicts.append(
                    UbReconcileConflict(
                        kind="overview_missing_entry",
                        row_index=row_index,
                        lesson_path=lesson_path,
                        ub_stem=ub_stem,
                        ub_path=ub_path,
                        message="UB fehlt in der Übersicht.",
                    )
                )

        return UbReconcileScanResult(conflicts=conflicts)

    def apply_resolution(
        self,
        *,
        table: PlanTableData,
        conflict: UbReconcileConflict,
        action: UbReconcileAction,
    ) -> UbReconcileApplyResult:
        """Wendet eine Benutzerentscheidung auf einen einzelnen Konflikt an."""
        if action == "ignore":
            return UbReconcileApplyResult(proceed=True)

        workspace_root = self._workspace_root_from_table(table)
        if action == "fix_overview":
            markdown = build_ub_overview_markdown(self.ub_repo, workspace_root)
            self.ub_repo.save_ub_overview(workspace_root, markdown)
            return UbReconcileApplyResult(proceed=True)

        if action == "fix_lesson":
            lesson = self.lesson_repo.load_lesson_yaml(conflict.lesson_path)
            data = lesson.data if isinstance(lesson.data, dict) else {}
            if conflict.kind in {"missing_ub_file", "ub_yaml_invalid", "backlink_mismatch"}:
                data["Unterrichtsbesuch"] = ""
                lesson.data = data
                self.lesson_repo.save_lesson_yaml(lesson)
                return UbReconcileApplyResult(proceed=True)

            if conflict.kind == "overview_missing_entry":
                data["Unterrichtsbesuch"] = build_wiki_link(conflict.ub_stem)
                lesson.data = data
                self.lesson_repo.save_lesson_yaml(lesson)
                return UbReconcileApplyResult(proceed=True)

        return UbReconcileApplyResult(proceed=False, error_message="Unbekannte Konfliktaktion.")
