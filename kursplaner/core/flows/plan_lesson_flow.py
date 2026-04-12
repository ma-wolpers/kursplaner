from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.plan_regular_lesson_usecase import (
    PlanRegularLessonUseCase,
    PlanRegularLessonWriteResult,
    RegularLessonDialogContext,
)


@dataclass(frozen=True)
class PlanLessonFlowWriteRequest:
    """Eingabedaten für den Mehrschritt-Flow "Einheit planen"."""

    table: PlanTableData
    row_index: int
    title: str
    topic: str
    stunden_raw: str
    oberthema_input: str
    stundenziel_input: str
    was_lzk: bool
    content_before: str
    kompetenzen_refs: list[str]
    inhalte_refs: list[str]
    methodik_refs: list[str]
    allow_create_link: bool
    allow_yaml_save: bool
    allow_sections_save: bool
    allow_rename: bool
    allow_plan_save: bool


class PlanLessonFlow:
    """Orchestriert den fachlichen Mehrschritt-Flow für regulären Unterricht."""

    def __init__(self, plan_regular_lesson: PlanRegularLessonUseCase):
        """Bindet den Use Case für reguläre Unterrichtsplanung."""
        self._plan_regular_lesson = plan_regular_lesson

    def build_dialog_context(
        self,
        *,
        table: PlanTableData,
        day: dict[str, object],
        unterricht_dir: Path,
    ) -> RegularLessonDialogContext:
        """Liefert den fachlichen Dialogkontext für den UI-Builder."""
        return self._plan_regular_lesson.build_dialog_context(
            table=table,
            day=day,
            unterricht_dir=unterricht_dir,
        )

    def execute_write(self, request: PlanLessonFlowWriteRequest) -> PlanRegularLessonWriteResult:
        """Führt den vollständigen Write-Flow für "Einheit planen" aus."""
        return self._plan_regular_lesson.execute_write(
            table=request.table,
            row_index=request.row_index,
            title=request.title,
            topic=request.topic,
            stunden_raw=request.stunden_raw,
            oberthema_input=request.oberthema_input,
            stundenziel_input=request.stundenziel_input,
            was_lzk=request.was_lzk,
            content_before=request.content_before,
            kompetenzen_refs=request.kompetenzen_refs,
            inhalte_refs=request.inhalte_refs,
            methodik_refs=request.methodik_refs,
            allow_create_link=request.allow_create_link,
            allow_yaml_save=request.allow_yaml_save,
            allow_sections_save=request.allow_sections_save,
            allow_rename=request.allow_rename,
            allow_plan_save=request.allow_plan_save,
        )
