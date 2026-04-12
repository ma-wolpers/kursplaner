from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.lesson_context_query_usecase import LessonContextQueryUseCase
from kursplaner.core.usecases.merge_selected_units_usecase import MergeSelectedUnitsUseCase
from kursplaner.core.usecases.move_selected_columns_usecase import MoveSelectedColumnsUseCase


@dataclass(frozen=True)
class ActionButtonState:
    """Berechneter Aktivierungszustand der Kontext-Aktionsbuttons."""

    can_plan: bool
    can_extend_to_vacation: bool
    can_lzk: bool
    can_ausfall: bool
    can_hospitation: bool
    can_mark_ub: bool
    can_resume: bool
    can_split: bool
    can_merge: bool
    can_move_left: bool
    can_move_right: bool
    can_clear: bool
    can_find: bool
    can_copy: bool
    can_paste: bool
    can_export_topic_pdf: bool
    can_export_lzk_expected_horizon: bool


class ActionButtonStateUseCase:
    """Berechnet fachliche Button-Aktivierbarkeit unabhängig von GUI-Widgets."""

    def __init__(
        self,
        lesson_context_query: LessonContextQueryUseCase,
        merge_selected_units: MergeSelectedUnitsUseCase,
        move_selected_columns: MoveSelectedColumnsUseCase,
    ):
        """Bindet abhängige Use Cases zur Zustandsberechnung der Aktionsbuttons."""
        self.lesson_context_query = lesson_context_query
        self.merge_selected_units = merge_selected_units
        self.move_selected_columns = move_selected_columns

    @staticmethod
    def _to_int(value: object, default: int = -1) -> int:
        """Konvertiert heterogene Werte robust zu `int` mit Fallback."""
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            text = value.strip()
            if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
                return int(text)
        return default

    @staticmethod
    def _selected_index(selected_day_indices: set[int], day_columns: list[dict[str, object]]) -> int | None:
        """Liefert den Index bei genau einer gültigen Selektion, sonst `None`."""
        selected = sorted(idx for idx in selected_day_indices if 0 <= idx < len(day_columns))
        if len(selected) != 1:
            return None
        return selected[0]

    def compute(
        self,
        *,
        selected_day_indices: set[int],
        day_columns: list[dict[str, object]],
        current_table: PlanTableData | None,
        clipboard_path: Path | None,
        is_detail_view: bool = True,
    ) -> ActionButtonState:
        """Liefert den vollständigen Aktivierungszustand für Kontextaktionen."""
        selected = self._selected_index(selected_day_indices, day_columns)
        selected_day = day_columns[selected] if selected is not None else None
        row_index = self._to_int(selected_day.get("row_index", -1), -1) if isinstance(selected_day, dict) else -1
        link = selected_day.get("link") if isinstance(selected_day, dict) else None

        has_selection = selected_day is not None
        has_link = isinstance(link, Path) and link.exists() and link.is_file()
        is_cancel = bool(selected_day.get("is_cancel", False)) if isinstance(selected_day, dict) else False
        is_lzk = bool(selected_day.get("is_lzk", False)) if isinstance(selected_day, dict) else False
        is_hospitation = bool(selected_day.get("is_hospitation", False)) if isinstance(selected_day, dict) else False
        can_act_on_lesson = has_selection and not is_cancel

        can_split = can_act_on_lesson and self.lesson_context_query.selected_row_hours(current_table, row_index) > 1
        can_merge = (
            can_act_on_lesson
            and current_table is not None
            and row_index >= 0
            and self.merge_selected_units.can_merge(current_table, row_index)
        )
        can_copy = can_act_on_lesson and has_link

        can_move_left = False
        can_move_right = False
        if can_act_on_lesson and selected is not None:
            can_move_left = self.move_selected_columns.find_swap_partner(day_columns, selected, -1) is not None
            can_move_right = self.move_selected_columns.find_swap_partner(day_columns, selected, 1) is not None

        can_paste = False
        if (
            can_act_on_lesson
            and isinstance(clipboard_path, Path)
            and clipboard_path.exists()
            and clipboard_path.is_file()
        ):
            if not has_link:
                can_paste = True
            elif isinstance(link, Path):
                can_paste = link.resolve() != clipboard_path.resolve()

        if not is_detail_view:
            return ActionButtonState(
                can_plan=False,
                can_extend_to_vacation=False,
                can_lzk=False,
                can_ausfall=False,
                can_hospitation=False,
                can_mark_ub=False,
                can_resume=False,
                can_split=False,
                can_merge=False,
                can_move_left=False,
                can_move_right=False,
                can_clear=False,
                can_find=False,
                can_copy=False,
                can_paste=False,
                can_export_topic_pdf=False,
                can_export_lzk_expected_horizon=False,
            )

        return ActionButtonState(
            can_plan=can_act_on_lesson and not has_link,
            can_extend_to_vacation=current_table is not None and len(current_table.rows) > 0,
            can_lzk=can_act_on_lesson and not is_lzk,
            can_ausfall=has_selection,
            can_hospitation=can_act_on_lesson and not is_hospitation,
            can_mark_ub=can_act_on_lesson and has_link,
            can_resume=has_selection and is_cancel,
            can_split=can_split,
            can_merge=can_merge,
            can_move_left=can_move_left,
            can_move_right=can_move_right,
            can_clear=can_act_on_lesson,
            can_find=can_act_on_lesson,
            can_copy=can_copy,
            can_paste=can_paste,
            can_export_topic_pdf=can_act_on_lesson and has_link,
            can_export_lzk_expected_horizon=can_act_on_lesson and has_link and is_lzk,
        )
