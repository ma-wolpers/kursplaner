from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.paste_lesson_usecase import (
    PasteExecutionPlan,
    PasteLessonUseCase,
    PasteWriteResult,
)


@dataclass(frozen=True)
class LessonTransferFlowWriteRequest:
    """Eingabedaten für den Mehrschritt-Flow "Stunde einfügen"."""

    table: PlanTableData
    row_index: int
    decision: str
    allow_delete: bool
    target_path: Path
    content: str
    source_stem: str


class LessonTransferFlow:
    """Orchestriert den fachlichen Mehrschritt-Flow für Lesson-Transfer/Paste."""

    def __init__(self, paste_lesson: PasteLessonUseCase):
        """Bindet den Paste-Use-Case als fachlichen Transfer-Kern."""
        self._paste_lesson = paste_lesson

    def validate_source(self, copied: Path) -> None:
        """Prüft, ob die kopierte Quelldatei noch verfügbar ist."""
        self._paste_lesson.validate_source(copied)

    def read_source_content(self, source: Path) -> str:
        """Liest den Inhalt einer Stundenquelle für die Zwischenablage."""
        return self._paste_lesson.read_source_content(source)

    def resolve_existing_target_link(self, table: PlanTableData, row_index: int) -> Path | None:
        """Liefert den aktuell verlinkten Zielpfad für Konfliktdialoge."""
        return self._paste_lesson.resolve_existing_target_link(table, row_index)

    def build_execution_plan(self, table: PlanTableData, preferred_stem: str) -> PasteExecutionPlan:
        """Berechnet den konfliktfreien Zielpfad fürs Einfügen."""
        return self._paste_lesson.build_execution_plan(table, preferred_stem)

    def execute_write(self, request: LessonTransferFlowWriteRequest) -> PasteWriteResult:
        """Führt den vollständigen Paste-Write-Flow aus."""
        return self._paste_lesson.execute(
            table=request.table,
            row_index=request.row_index,
            decision=request.decision,
            allow_delete=request.allow_delete,
            target_path=request.target_path,
            content=request.content,
            source_stem=request.source_stem,
        )
