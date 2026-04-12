from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.lesson_naming import row_mmdd
from kursplaner.core.domain.plan_table import PlanTableData, sanitize_hour_title
from kursplaner.core.domain.wiki_links import build_wiki_link, strip_wiki_link
from kursplaner.core.ports.repositories import PlanRepository
from kursplaner.core.usecases.lesson_edit_usecase import LessonEditUseCase
from kursplaner.core.usecases.lesson_transfer_usecase import LessonTransferUseCase
from kursplaner.core.usecases.rename_linked_file_for_row_usecase import (
    RenameLinkedFileForRowUseCase,
)
from kursplaner.core.usecases.row_display_mode_usecase import RowDisplayModeUseCase
from kursplaner.core.usecases.sync_ub_development_focus_usecase import SyncUbDevelopmentFocusUseCase


@dataclass(frozen=True)
class SaveCellValueResult:
    """Ergebnis des Save-Flows für eine editierte Grid-Zelle."""

    proceed: bool
    lesson_path: Path | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class SaveCellEditPlan:
    """Fachliche Vorabplanung für Save-Dialoge und Rename-Entscheidung."""

    list_entries: list[str] | None
    should_rename_topic: bool
    desired_stem: str
    rename_target_preview: Path | None


@dataclass(frozen=True)
class SaveCellConfirmationPlan:
    """Beschreibt, welche Bestätigungen im UI-Flow einzuholen sind."""

    require_plan_hours_save: bool
    require_duration_save: bool
    require_yaml_save: bool
    require_rename: bool
    require_plan_save_for_rename: bool
    rename_target_preview: Path | None


@dataclass(frozen=True)
class SaveCellRuntimeContext:
    """Laufzeitkontext inkl. fachlicher Editierbarkeit einer Grid-Zelle."""

    proceed: bool
    row_index: int | None
    lesson_path: Path | None
    message_kind: str | None
    message_title: str | None
    message_text: str | None


class SaveCellValueUseCase:
    """Persistiert Zelländerungen für Plan-/Lesson-Felder als ein Write-Flow."""

    UB_DEVELOPMENT_FIELDS: tuple[str, str] = (
        "Professionalisierungsschritte",
        "Nutzbare Ressourcen",
    )

    def __init__(
        self,
        lesson_edit: LessonEditUseCase,
        plan_repo: PlanRepository,
        lesson_transfer: LessonTransferUseCase,
        rename_linked_file_for_row: RenameLinkedFileForRowUseCase,
        row_display_mode_usecase: RowDisplayModeUseCase,
        sync_ub_development_focus_usecase: SyncUbDevelopmentFocusUseCase | None = None,
    ):
        """Initialisiert den Save-Flow mit Edit-, Transfer- und Persistenzabhängigkeiten."""
        self.lesson_edit = lesson_edit
        self.plan_repo = plan_repo
        self.lesson_transfer = lesson_transfer
        self.rename_linked_file_for_row = rename_linked_file_for_row
        self.row_display_mode_usecase = row_display_mode_usecase
        self.sync_ub_development_focus_usecase = sync_ub_development_focus_usecase

    @staticmethod
    def _keyword_match(text: str, keywords: list[str]) -> bool:
        """Prüft case-insensitiv, ob eines der Keywords im Text vorkommt."""
        lowered = text.lower()
        return any(keyword.lower() in lowered for keyword in keywords)

    @staticmethod
    def _parse_list_entries(text: str) -> list[str]:
        """Parst Freitext in bereinigte Listenpunkte für YAML-Listenfelder."""
        if not text.strip():
            return []
        result: list[str] = []
        normalized = text.replace("\n—\n", "\n\n")
        chunks = re.split(r"(?:\n\s*\n|;|\s*\|\s*)", normalized)
        for chunk in chunks:
            if not chunk:
                continue
            lines = [line.strip() for line in chunk.splitlines() if line.strip()]
            if not lines:
                continue
            joined = " ".join(lines)
            joined = re.sub(r"^\[(\d+)\]\s*", "", joined)
            joined = re.sub(r"^(\d+)[\).:]\s*", "", joined)
            if joined:
                result.append(joined)
        return result

    @staticmethod
    def _sanitize_link_alias(text: str) -> str:
        """Bereinigt Alias-Text für Wiki-Links ohne den Zielstem zu verändern."""
        alias = str(text or "").replace("|", " ").replace("[", " ").replace("]", " ")
        alias = alias.replace("\n", " ").replace("\r", " ")
        return re.sub(r"\s+", " ", alias).strip()

    @staticmethod
    def _alias_from_stem(table: PlanTableData, row_index: int, stem: str) -> str:
        """Leitet den sichtbaren Inhalt aus einem Dateistem ab (`gruppe mm-dd <alias>`)."""
        group = strip_wiki_link(str(table.metadata.get("Lerngruppe", "gruppe")))
        group = sanitize_hour_title(group) or "gruppe"
        mmdd = row_mmdd(table, row_index)
        prefix = f"{group} {mmdd} "
        if stem.lower().startswith(prefix.lower()):
            alias = stem[len(prefix) :].strip()
            if alias:
                return alias
        return stem.strip()

    @staticmethod
    def _workspace_root_from_table(table: PlanTableData) -> Path:
        resolved = table.markdown_path.expanduser().resolve()
        for parent in (resolved, *resolved.parents):
            if parent.name == "7thCloud":
                return parent
        return resolved.parent

    def _compose_inhalt_value(self, table: PlanTableData, row_index: int, value: str) -> str:
        """Persistiert Inhalts-Edits linkstabil als Wiki-Link-Alias, falls ein Link existiert."""
        raw = str(value or "").strip()
        if "[[" in raw and "]]" in raw:
            return raw

        link = self.lesson_transfer.resolve_existing_link(table, row_index)
        if not isinstance(link, Path):
            return raw

        alias = self._sanitize_link_alias(raw)
        if not alias:
            alias = self._alias_from_stem(table, row_index, link.stem)
        built = build_wiki_link(link.stem, alias or None)
        return built or raw

    def build_edit_plan(
        self,
        *,
        table: PlanTableData,
        row_index: int,
        field_key: str,
        value: str,
        lesson_path: Path,
    ) -> SaveCellEditPlan:
        """Ermittelt fachliche Vorabdaten für den Zell-Speicherfluss."""
        list_entries: list[str] | None = None
        if field_key in self.row_display_mode_usecase.list_like_fields():
            list_entries = self._parse_list_entries(value)

        return SaveCellEditPlan(
            list_entries=list_entries,
            should_rename_topic=False,
            desired_stem="",
            rename_target_preview=None,
        )

    def build_runtime_context(
        self,
        *,
        field_key: str,
        day: dict[str, object],
    ) -> SaveCellRuntimeContext:
        """Prüft fachliche Editierbarkeit und liefert Laufzeitdaten für den Save-Flow."""
        if field_key in {"datum", "stunden", "inhalt"}:
            return SaveCellRuntimeContext(
                proceed=False,
                row_index=None,
                lesson_path=None,
                message_kind=None,
                message_title=None,
                message_text=None,
            )

        if not self.row_display_mode_usecase.field_is_relevant_for_day(field_key, day):
            return SaveCellRuntimeContext(
                proceed=False,
                row_index=None,
                lesson_path=None,
                message_kind=None,
                message_title=None,
                message_text=None,
            )

        link_obj = day.get("link")
        raw_row_index = day.get("row_index", 0)
        try:
            row_index = int(raw_row_index)
        except (TypeError, ValueError):
            row_index = 0
        has_known_lesson = isinstance(link_obj, Path) and link_obj.exists() and link_obj.is_file()
        if not has_known_lesson:
            return SaveCellRuntimeContext(
                proceed=False,
                row_index=row_index,
                lesson_path=None,
                message_kind="info",
                message_title="Bearbeitung gesperrt",
                message_text=(
                    "Diese Spalte hat keine bekannte Stunden-Markdown.\n"
                    "Nutze 'Stunde erstellen' oder 'Markdown finden'."
                ),
            )

        lesson_path = link_obj if isinstance(link_obj, Path) else None
        if not isinstance(lesson_path, Path) or not lesson_path.exists():
            return SaveCellRuntimeContext(
                proceed=False,
                row_index=row_index,
                lesson_path=None,
                message_kind="error",
                message_title="Speichern fehlgeschlagen",
                message_text=(
                    "Keine bekannte Stunden-Markdown für diese Spalte.\n"
                    "Nutze 'Stunde erstellen' oder 'Markdown finden'."
                ),
            )

        return SaveCellRuntimeContext(
            proceed=True,
            row_index=row_index,
            lesson_path=lesson_path,
            message_kind=None,
            message_title=None,
            message_text=None,
        )

    def build_confirmation_plan(
        self,
        *,
        field_key: str,
        lesson_path: Path | None,
        edit_plan: SaveCellEditPlan,
    ) -> SaveCellConfirmationPlan:
        """Leitet den fachlichen Bestätigungsbedarf des Save-Flows ab."""
        if field_key == "stunden":
            return SaveCellConfirmationPlan(
                require_plan_hours_save=True,
                require_duration_save=isinstance(lesson_path, Path) and lesson_path.exists(),
                require_yaml_save=False,
                require_rename=False,
                require_plan_save_for_rename=False,
                rename_target_preview=None,
            )

        if field_key == "inhalt":
            return SaveCellConfirmationPlan(
                require_plan_hours_save=False,
                require_duration_save=False,
                require_yaml_save=False,
                require_rename=False,
                require_plan_save_for_rename=False,
                rename_target_preview=None,
            )

        requires_rename = bool(
            edit_plan.should_rename_topic
            and isinstance(edit_plan.rename_target_preview, Path)
            and isinstance(lesson_path, Path)
            and edit_plan.rename_target_preview.resolve() != lesson_path.resolve()
        )

        return SaveCellConfirmationPlan(
            require_plan_hours_save=False,
            require_duration_save=False,
            require_yaml_save=True,
            require_rename=requires_rename,
            require_plan_save_for_rename=edit_plan.should_rename_topic,
            rename_target_preview=edit_plan.rename_target_preview,
        )

    def execute(
        self,
        *,
        table: PlanTableData,
        row_index: int,
        field_key: str,
        value: str,
        lesson_path: Path | None,
        list_entries: list[str] | None,
        should_rename_topic: bool,
        desired_stem: str,
        allow_plan_hours_save: bool,
        allow_yaml_save: bool,
        allow_duration_save: bool,
        allow_rename: bool,
        allow_plan_save_for_rename: bool,
    ) -> SaveCellValueResult:
        """Führt den Speichern-Flow für eine einzelne Zelle aus."""
        self.lesson_edit.validate_table(table)

        if field_key == "inhalt":
            self.lesson_edit.set_content_value(table, row_index, self._compose_inhalt_value(table, row_index, value))
            self.plan_repo.save_plan_table(table)
            return SaveCellValueResult(proceed=True, lesson_path=lesson_path)

        if field_key == "stunden":
            if lesson_path is None:
                return SaveCellValueResult(
                    proceed=False,
                    error_message="Keine verknüpfte Stunden-Datei für das Feld 'stunden'.",
                )
            if not allow_plan_hours_save:
                return SaveCellValueResult(
                    proceed=False,
                    error_message="Speichern des Stundenwerts in der Planung abgebrochen.",
                )

            self.lesson_edit.set_hours_value(table, row_index, value)
            self.plan_repo.save_plan_table(table)

            if allow_duration_save:
                self.lesson_edit.set_lesson_duration(lesson_path, value)
            return SaveCellValueResult(proceed=True, lesson_path=lesson_path)

        if lesson_path is None:
            return SaveCellValueResult(
                proceed=False,
                error_message=f"Keine verknüpfte Stunden-Datei für das Feld '{field_key}'.",
            )

        if not allow_yaml_save:
            return SaveCellValueResult(
                proceed=False,
                error_message=f"Speichern des Felds '{field_key}' in der Stunden-YAML abgebrochen.",
            )

        if field_key in self.UB_DEVELOPMENT_FIELDS:
            if self.sync_ub_development_focus_usecase is None:
                return SaveCellValueResult(
                    proceed=False,
                    error_message="UB-Synchronisierung ist nicht verfügbar.",
                )

            focus = self.sync_ub_development_focus_usecase.load(
                workspace_root=self._workspace_root_from_table(table),
                lesson_path=lesson_path,
            )
            steps_text = "\n".join(focus.professional_steps)
            resources_text = "\n".join(focus.usable_resources)

            if field_key == "Professionalisierungsschritte":
                steps_text = value
            else:
                resources_text = value

            saved = self.sync_ub_development_focus_usecase.save(
                workspace_root=self._workspace_root_from_table(table),
                lesson_path=lesson_path,
                professional_steps_text=steps_text,
                usable_resources_text=resources_text,
            )
            if not saved:
                return SaveCellValueResult(
                    proceed=False,
                    error_message=("UB-Synchronisierung fehlgeschlagen: keine verknüpfte UB-Datei für diese Einheit."),
                )
            return SaveCellValueResult(proceed=True, lesson_path=lesson_path)

        self.lesson_edit.set_lesson_field(
            lesson_path,
            field_key,
            value,
            list_entries=list_entries,
        )

        if should_rename_topic and not allow_plan_save_for_rename:
            return SaveCellValueResult(
                proceed=False,
                error_message="Speichern der Planungstabelle abgebrochen.",
            )

        if should_rename_topic:
            rename_result = self.rename_linked_file_for_row.execute(
                table=table,
                row_index=row_index,
                desired_stem=desired_stem,
                allow_rename=allow_rename,
                allow_plan_save=allow_plan_save_for_rename,
            )
            if not rename_result.proceed:
                return SaveCellValueResult(
                    proceed=False,
                    error_message=rename_result.error_message,
                )
            return SaveCellValueResult(
                proceed=True,
                lesson_path=rename_result.target_path or lesson_path,
            )

        return SaveCellValueResult(proceed=True, lesson_path=lesson_path)
