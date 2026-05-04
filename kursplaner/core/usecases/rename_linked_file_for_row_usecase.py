from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.config.path_store import infer_workspace_root_from_path
from kursplaner.core.domain.lesson_naming import row_mmdd
from kursplaner.core.domain.plan_table import PlanTableData, sanitize_hour_title
from kursplaner.core.domain.unterrichtsbesuch_policy import UB_YAML_KEY_EINHEIT, build_ub_stem
from kursplaner.core.domain.wiki_links import build_wiki_link, strip_wiki_link
from kursplaner.core.ports.repositories import LessonRepository, PlanRepository, UbRepository
from kursplaner.core.usecases.lesson_transfer_usecase import LessonTransferUseCase
from kursplaner.core.usecases.ub_markdown_sections import parse_list_section, parse_reflection
from kursplaner.core.usecases.ub_overview_builder import build_ub_overview_markdown


@dataclass(frozen=True)
class RenameLinkedFileResult:
    """Ergebnis des Umbenennens einer verlinkten Stunden-Datei."""

    proceed: bool
    target_path: Path | None = None
    error_message: str | None = None


class RenameLinkedFileForRowUseCase:
    """Benennt eine verlinkte Stunde um, aktualisiert den Link und persistiert die Planung."""

    def __init__(
        self,
        plan_repo: PlanRepository,
        lesson_transfer: LessonTransferUseCase,
        lesson_repo: LessonRepository | None = None,
        ub_repo: UbRepository | None = None,
    ):
        """Initialisiert Rename-Use-Case mit Transfer- und Persistenzabhängigkeiten."""
        self.plan_repo = plan_repo
        self.lesson_transfer = lesson_transfer
        self.lesson_repo = lesson_repo
        self.ub_repo = ub_repo

    @staticmethod
    def _row_date_text(table: PlanTableData, row_index: int) -> str:
        header_map = {name.lower(): idx for idx, name in enumerate(table.headers)}
        idx_datum = header_map.get("datum", 0)
        if not (0 <= row_index < len(table.rows)):
            return ""
        row = table.rows[row_index]
        if not (0 <= idx_datum < len(row)):
            return ""
        return str(row[idx_datum]).strip()

    @staticmethod
    def _topic_from_lesson_stem(table: PlanTableData, row_index: int, lesson_stem: str) -> str:
        group = strip_wiki_link(str(table.metadata.get("Lerngruppe", "gruppe")))
        mmdd = row_mmdd(table, row_index)
        prefix = f"{group} {mmdd} "
        stem = str(lesson_stem or "").strip()
        if stem.lower().startswith(prefix.lower()):
            topic = stem[len(prefix) :].strip()
            if topic:
                return topic
        return stem

    @staticmethod
    def _workspace_root_from_table(table: PlanTableData) -> Path:
        return infer_workspace_root_from_path(table.markdown_path)

    def _sync_ub_after_lesson_rename(self, *, table: PlanTableData, row_index: int, lesson_path: Path) -> None:
        if self.lesson_repo is None or self.ub_repo is None:
            return
        try:
            lesson = self.lesson_repo.load_lesson_yaml(lesson_path)
        except Exception:
            return
        data = lesson.data if isinstance(lesson.data, dict) else {}
        ub_stem = strip_wiki_link(str(data.get("Unterrichtsbesuch", "")).strip())
        if not ub_stem:
            return

        workspace_root = self._workspace_root_from_table(table)
        ub_root = self.ub_repo.ensure_ub_root(workspace_root)
        ub_path = ub_root / f"{ub_stem}.md"
        if not ub_path.exists() or not ub_path.is_file():
            return

        try:
            ub_yaml, ub_body = self.ub_repo.load_ub_markdown(ub_path)
        except Exception:
            return

        new_topic = self._topic_from_lesson_stem(table, row_index, lesson_path.stem)
        date_text = self._row_date_text(table, row_index)
        desired_ub_stem = build_ub_stem(date_text, new_topic)
        desired_ub_path = ub_root / f"{desired_ub_stem}.md"
        if desired_ub_path.exists() and desired_ub_path.resolve() != ub_path.resolve():
            desired_ub_path = self.ub_repo.unique_ub_markdown_path(workspace_root, desired_ub_stem)

        final_ub_path = ub_path
        if desired_ub_path.resolve() != ub_path.resolve():
            final_ub_path = self.ub_repo.rename_ub_markdown(ub_path, desired_ub_path)

        ub_yaml[UB_YAML_KEY_EINHEIT] = build_wiki_link(lesson_path.stem)
        reflection_text = parse_reflection(ub_body)
        professional_steps = parse_list_section(ub_body, "Professionalisierungsschritte")
        usable_resources = parse_list_section(ub_body, "Nutzbare Ressourcen")
        self.ub_repo.save_ub_markdown(
            final_ub_path,
            ub_yaml,
            reflection_text=reflection_text,
            professional_steps=professional_steps,
            usable_resources=usable_resources,
        )

        data["Unterrichtsbesuch"] = build_wiki_link(final_ub_path.stem)
        lesson.data = data
        self.lesson_repo.save_lesson_yaml(lesson)
        self.ub_repo.save_ub_overview(workspace_root, build_ub_overview_markdown(self.ub_repo, workspace_root))

    def execute(
        self,
        *,
        table: PlanTableData,
        row_index: int,
        desired_stem: str,
        allow_rename: bool,
        allow_plan_save: bool,
        allow_conflict_suffix: bool = True,
        preserve_alias: bool = True,
    ) -> RenameLinkedFileResult:
        """Führt den vollständigen Rename-Write-Flow für eine Tabellenzeile aus."""
        link = self.lesson_transfer.resolve_existing_link(table, row_index)
        if not isinstance(link, Path) or not link.exists() or not link.is_file():
            return RenameLinkedFileResult(proceed=True, target_path=None)

        if allow_conflict_suffix:
            target = self.lesson_transfer.compute_rename_target(link, desired_stem)
        else:
            normalized_stem = sanitize_hour_title(desired_stem)
            if not normalized_stem:
                target = link
            else:
                target = link.with_name(f"{normalized_stem}.md")
                if target.exists() and target.resolve() != link.resolve():
                    return RenameLinkedFileResult(
                        proceed=False,
                        error_message=(f"Verschieben abgebrochen: Zielname existiert bereits:\n{target.name}"),
                    )

        if target.resolve() != link.resolve():
            if not allow_rename:
                return RenameLinkedFileResult(
                    proceed=False,
                    error_message="Umbenennen abgebrochen.",
                )
            target = self.lesson_transfer.rename_lesson_file(link, target)

        self.lesson_transfer.relink_row_to_stem(table, row_index, target.stem, preserve_alias=preserve_alias)
        self._sync_ub_after_lesson_rename(table=table, row_index=row_index, lesson_path=target)
        if not allow_plan_save:
            return RenameLinkedFileResult(proceed=True, target_path=target)

        self.plan_repo.save_plan_table(table)
        return RenameLinkedFileResult(proceed=True, target_path=target)
