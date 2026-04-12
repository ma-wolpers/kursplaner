from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.convert_to_lzk_usecase import (
    ConvertToLzkDialogContext,
    ConvertToLzkUseCase,
    ConvertToLzkWriteResult,
)


@dataclass(frozen=True)
class LzkLessonFlowWriteRequest:
    """Eingabedaten für den Mehrschritt-Flow "LZK planen"."""

    table: PlanTableData
    row_index: int
    current_content: str
    decision: str
    existing_link: Path | None
    title: str
    default_hours: int
    allow_delete: bool


class LzkLessonFlow:
    """Orchestriert den fachlichen Mehrschritt-Flow für LZK-Planung."""

    def __init__(self, convert_to_lzk: ConvertToLzkUseCase):
        """Bindet den LZK-Use-Case für den mehrschrittigen LZK-Flow."""
        self._convert_to_lzk = convert_to_lzk

    def build_dialog_context(
        self,
        *,
        table: PlanTableData,
        row_index: int,
        current_content: str,
        next_no: int,
        stunden_raw: str,
    ) -> ConvertToLzkDialogContext:
        """Liefert den fachlichen Dialogkontext für den LZK-Flow."""
        return self._convert_to_lzk.build_dialog_context(
            table=table,
            row_index=row_index,
            current_content=current_content,
            next_no=next_no,
            stunden_raw=stunden_raw,
        )

    def execute_write(self, request: LzkLessonFlowWriteRequest) -> ConvertToLzkWriteResult:
        """Führt den vollständigen LZK-Write-Flow aus."""
        return self._convert_to_lzk.execute(
            table=request.table,
            row_index=request.row_index,
            current_content=request.current_content,
            decision=request.decision,
            existing_link=request.existing_link,
            title=request.title,
            default_hours=request.default_hours,
            allow_delete=request.allow_delete,
        )
