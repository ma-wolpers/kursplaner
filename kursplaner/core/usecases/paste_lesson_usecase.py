from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.unterrichtsbesuch_policy import (
    UB_YAML_KEY_EINHEIT,
    build_ub_stem,
)
from kursplaner.core.domain.wiki_links import build_wiki_link, strip_wiki_link
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.ports.repositories import LessonRepository, PlanRepository, UbRepository
from kursplaner.core.usecases.lesson_transfer_usecase import LessonTransferUseCase
from kursplaner.core.usecases.plan_commands_usecase import PlanCommandsUseCase
from kursplaner.core.usecases.ub_markdown_sections import parse_list_section, parse_reflection
from kursplaner.core.usecases.ub_overview_builder import build_ub_overview_markdown


@dataclass(frozen=True)
class PasteConflictResolution:
    """Beschreibt die Konfliktauflösung für Paste Conflict Resolution.

    Die Instanz hält Benutzerentscheidung und optionale Zielzeile für den Konfliktfall.
    """

    proceed: bool
    error_message: str | None = None
    shadow_link: Path | None = None
    delete_link: Path | None = None


@dataclass(frozen=True)
class PasteExecutionPlan:
    """Beschreibt den Ausführungsplan für Paste Execution Plan.

    Die Instanz hält vorberechnete Schritte und Zielwerte für eine nachgelagerte Aktion.
    """

    target_path: Path
    relink_stem: str


@dataclass(frozen=True)
class PasteWriteResult:
    """Ergebnis eines vollständigen Paste-Write-Flows."""

    proceed: bool
    created_path: Path | None = None
    shadow_link: Path | None = None
    ub_path: Path | None = None
    overview_path: Path | None = None
    deleted_target_path: Path | None = None
    deleted_target_ub_path: Path | None = None
    deleted_target_overview_path: Path | None = None
    error_message: str | None = None


class PasteLessonUseCase:
    """Orchestriert den fachlichen Ablauf für Paste Lesson Use-Case.

    Die Klasse bündelt Anwendungslogik zwischen Domain-Regeln und Port-basiertem I/O.
    """

    def __init__(
        self,
        lesson_repo: LessonRepository,
        plan_repo: PlanRepository,
        plan_commands: PlanCommandsUseCase,
        lesson_transfer: LessonTransferUseCase,
        ub_repo: UbRepository,
    ):
        """Initialisiert den Einfügeablauf für kopierte Stunden.

        Args:
            lesson_repo: Repository für Links und Stunden-YAML.
            plan_repo: Repository zum Persistieren der Planung.
            plan_commands: Planoperationen für Konfliktverschiebungen.
            lesson_transfer: Dateioperationen für Kopieren/Relinken.
        """
        self.lesson_repo = lesson_repo
        self.plan_repo = plan_repo
        self.plan_commands = plan_commands
        self.lesson_transfer = lesson_transfer
        self.ub_repo = ub_repo

    @staticmethod
    def _workspace_root_from_markdown(path: Path) -> Path:
        """Leitet den Workspace-Stamm robust aus einem Projektpfad ab."""
        resolved = path.expanduser().resolve()
        for parent in (resolved, *resolved.parents):
            if parent.name == "7thCloud":
                return parent
        return resolved.anchor and Path(resolved.anchor) or resolved.parent

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

    def _copy_linked_ub_for_created_lesson(
        self,
        *,
        table: PlanTableData,
        row_index: int,
        created_path: Path,
    ) -> tuple[Path | None, Path | None]:
        """Kopiert eine verknüpfte UB-Datei auf neues Datum/Einheit und aktualisiert die Verknüpfung."""
        lesson = self.lesson_repo.load_lesson_yaml(created_path)
        lesson_data = lesson.data if isinstance(lesson.data, dict) else {}
        source_ub_stem = strip_wiki_link(str(lesson_data.get("Unterrichtsbesuch", "")).strip())
        if not source_ub_stem:
            return None, None

        workspace_root = self._workspace_root_from_markdown(table.markdown_path)
        source_ub_path = self.ub_repo.ensure_ub_root(workspace_root) / f"{source_ub_stem}.md"
        if not source_ub_path.exists() or not source_ub_path.is_file():
            lesson_data["Unterrichtsbesuch"] = ""
            lesson.data = lesson_data
            self.lesson_repo.save_lesson_yaml(lesson)
            return None, None

        ub_yaml, ub_body = self.ub_repo.load_ub_markdown(source_ub_path)
        date_idx = {name.lower(): idx for idx, name in enumerate(table.headers)}.get("datum")
        date_text = ""
        if isinstance(date_idx, int) and date_idx < len(table.rows[row_index]):
            date_text = str(table.rows[row_index][date_idx]).strip()

        unit_title = self._unit_title_from_lesson_stem(created_path)
        desired_stem = build_ub_stem(date_text, unit_title)
        target_ub_path = self.ub_repo.unique_ub_markdown_path(workspace_root, desired_stem)

        ub_yaml = dict(ub_yaml)
        ub_yaml[UB_YAML_KEY_EINHEIT] = build_wiki_link(created_path.stem)

        self.ub_repo.save_ub_markdown(
            target_ub_path,
            ub_yaml,
            reflection_text=parse_reflection(ub_body),
            professional_steps=parse_list_section(ub_body, "Professionalisierungsschritte"),
            usable_resources=parse_list_section(ub_body, "Nutzbare Ressourcen"),
        )

        lesson_data["Unterrichtsbesuch"] = build_wiki_link(target_ub_path.stem)
        lesson.data = lesson_data
        self.lesson_repo.save_lesson_yaml(lesson)

        overview_markdown = build_ub_overview_markdown(self.ub_repo, workspace_root)
        overview_path = self.ub_repo.save_ub_overview(workspace_root, overview_markdown)
        return target_ub_path, overview_path

    def _cleanup_deleted_target_with_ub(
        self,
        *,
        table: PlanTableData,
        lesson_path: Path,
    ) -> tuple[Path | None, Path | None]:
        """Löscht bei Ziel-Delete optional die verknüpfte UB-Datei und synchronisiert die Übersicht."""
        if not lesson_path.exists() or not lesson_path.is_file():
            return None, None

        lesson = self.lesson_repo.load_lesson_yaml(lesson_path)
        lesson_data = lesson.data if isinstance(lesson.data, dict) else {}
        ub_stem = strip_wiki_link(str(lesson_data.get("Unterrichtsbesuch", "")).strip())
        if not ub_stem:
            return None, None

        workspace_root = self._workspace_root_from_markdown(table.markdown_path)
        ub_path = self.ub_repo.ensure_ub_root(workspace_root) / f"{ub_stem}.md"
        if ub_path.exists() and ub_path.is_file():
            self.ub_repo.delete_ub_markdown(ub_path)

        overview_markdown = build_ub_overview_markdown(self.ub_repo, workspace_root)
        overview_path = self.ub_repo.save_ub_overview(workspace_root, overview_markdown)
        return ub_path, overview_path

    @staticmethod
    def validate_source(copied: Path) -> None:
        """Prüft, ob die kopierte Quelldatei noch verfügbar ist.

        Args:
            copied: Pfad zur zuvor kopierten Stunden-Datei.
        """
        if not copied.exists() or not copied.is_file():
            raise RuntimeError(f"Kopierte Datei fehlt:\n{copied}")

    def read_source_content(self, source: Path) -> str:
        """Liest den Inhalt einer kopierten Stunde für die Zwischenablage."""
        return self.lesson_transfer.read_lesson_content(source)

    def resolve_existing_target_link(self, table: PlanTableData, row_index: int) -> Path | None:
        """Liefert den aktuell verlinkten Zielpfad für den Paste-Konfliktdialog."""
        target_link = self.lesson_repo.resolve_row_link_path(table, row_index)
        if isinstance(target_link, Path) and target_link.exists() and target_link.is_file():
            return target_link
        return None

    def resolve_conflict(
        self,
        table: PlanTableData,
        row_index: int,
        decision: str,
    ) -> PasteConflictResolution:
        """Löst Zielkonflikte beim Einfügen in eine bereits belegte Zeile auf.

        Args:
            table: Planungstabelle.
            row_index: Zielzeile für den Einfügevorgang.
            decision: Benutzerentscheidung (cancel/move/shadow/delete).

        Returns:
            Aufgelöste Konfliktstrategie für den weiteren Ablauf.
        """
        target_link = self.lesson_repo.resolve_row_link_path(table, row_index)
        if not (isinstance(target_link, Path) and target_link.exists() and target_link.is_file()):
            return PasteConflictResolution(proceed=True)

        normalized = (decision or "cancel").strip().lower()
        if normalized == "cancel":
            return PasteConflictResolution(proceed=False)

        if normalized == "move":
            shifted = self.plan_commands.shift_existing_lessons_forward(table, start_row_index=row_index)
            if not shifted:
                return PasteConflictResolution(
                    proceed=False,
                    error_message=(
                        "Verschieben würde das Tabellenende überschreiten. "
                        "Bestehende Stunde wurde als Schattenstunde markiert."
                    ),
                    shadow_link=target_link,
                )
            return PasteConflictResolution(proceed=True)

        if normalized == "shadow":
            return PasteConflictResolution(proceed=True, shadow_link=target_link)

        if normalized == "delete":
            return PasteConflictResolution(proceed=True, delete_link=target_link)

        raise RuntimeError(f"Unbekannte Konfliktentscheidung: {decision}")

    def build_execution_plan(self, table: PlanTableData, preferred_stem: str) -> PasteExecutionPlan:
        """Berechnet den konkreten Zielpfad und den neuen Link-Stem fürs Einfügen.

        Args:
            table: Planungstabelle.
            preferred_stem: Wunsch-Stem für die neue Datei.

        Returns:
            Ausführungsplan mit konfliktfreiem Zielpfad.
        """
        stunden_dir = self.lesson_transfer.lesson_dir_for_table(table)
        candidate = self.lesson_transfer.next_unique_stem_path(stunden_dir, preferred_stem)
        return PasteExecutionPlan(target_path=candidate, relink_stem=candidate.stem)

    def apply_paste(
        self,
        table: PlanTableData,
        row_index: int,
        target_path: Path,
        content: str,
        source_stem: str,
        ub_copy_mode: str,
    ) -> tuple[Path, Path | None, Path | None]:
        """Schreibt die kopierte Stunde und verlinkt die Zielzeile auf den neuen Stem.

        Args:
            table: Planungstabelle.
            row_index: Zielzeile.
            target_path: Zielpfad der einzufügenden Datei.
            content: Inhalt der kopierten Quellstunde.
            source_stem: Ursprünglicher Stem der Quelle.

        Returns:
            Pfad der neu angelegten Stunden-Datei.
        """
        normalized_ub_mode = (ub_copy_mode or "none").strip().lower()
        created = self.lesson_transfer.write_pasted_lesson(
            target_path=target_path,
            content=content,
            source_stem=source_stem,
            clear_ub_link=normalized_ub_mode != "copy",
        )
        self.lesson_transfer.relink_row_to_stem(table, row_index, created.stem, preserve_alias=False)

        if normalized_ub_mode == "copy":
            ub_path, overview_path = self._copy_linked_ub_for_created_lesson(
                table=table,
                row_index=row_index,
                created_path=created,
            )
            return created, ub_path, overview_path

        return created, None, None

    def execute(
        self,
        *,
        table: PlanTableData,
        row_index: int,
        decision: str,
        allow_delete: bool,
        target_path: Path,
        content: str,
        source_stem: str,
        ub_copy_mode: str = "none",
    ) -> PasteWriteResult:
        """Führt den vollständigen Paste-Write-Flow als eine Transaktion aus."""
        resolution = self.resolve_conflict(
            table=table,
            row_index=row_index,
            decision=decision,
        )

        if not resolution.proceed:
            return PasteWriteResult(
                proceed=False,
                shadow_link=resolution.shadow_link,
                error_message=resolution.error_message,
            )

        deleted_target_path: Path | None = None
        deleted_target_ub_path: Path | None = None
        deleted_target_overview_path: Path | None = None

        if isinstance(resolution.delete_link, Path):
            if not allow_delete:
                return PasteWriteResult(
                    proceed=False,
                    shadow_link=resolution.shadow_link,
                    error_message="Löschen wurde nicht bestätigt. Keine Änderung durchgeführt.",
                )
            deleted_target_path = resolution.delete_link
            deleted_target_ub_path, deleted_target_overview_path = self._cleanup_deleted_target_with_ub(
                table=table,
                lesson_path=resolution.delete_link,
            )
            self.lesson_transfer.delete_lesson_file(resolution.delete_link)

        created, ub_path, overview_path = self.apply_paste(
            table=table,
            row_index=row_index,
            target_path=target_path,
            content=content,
            source_stem=source_stem,
            ub_copy_mode=ub_copy_mode,
        )
        self.plan_repo.save_plan_table(table)

        return PasteWriteResult(
            proceed=True,
            created_path=created,
            shadow_link=resolution.shadow_link,
            ub_path=ub_path,
            overview_path=overview_path,
            deleted_target_path=deleted_target_path,
            deleted_target_ub_path=deleted_target_ub_path,
            deleted_target_overview_path=deleted_target_overview_path,
        )
