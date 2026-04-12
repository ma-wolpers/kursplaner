from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.ports.repositories import LessonRepository, PlanRepository
from kursplaner.core.usecases.lesson_transfer_usecase import LessonTransferUseCase
from kursplaner.core.usecases.plan_commands_usecase import PlanCommandsUseCase


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
    ) -> Path:
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
        created = self.lesson_transfer.write_pasted_lesson(
            target_path=target_path,
            content=content,
            source_stem=source_stem,
        )
        self.lesson_transfer.relink_row_to_stem(table, row_index, created.stem, preserve_alias=False)
        return created

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

        if isinstance(resolution.delete_link, Path):
            if not allow_delete:
                return PasteWriteResult(
                    proceed=False,
                    shadow_link=resolution.shadow_link,
                    error_message="Löschen wurde nicht bestätigt. Keine Änderung durchgeführt.",
                )
            self.lesson_transfer.delete_lesson_file(resolution.delete_link)

        created = self.apply_paste(
            table=table,
            row_index=row_index,
            target_path=target_path,
            content=content,
            source_stem=source_stem,
        )
        self.plan_repo.save_plan_table(table)

        return PasteWriteResult(
            proceed=True,
            created_path=created,
            shadow_link=resolution.shadow_link,
        )
