from __future__ import annotations

import pathlib

from kursplaner.adapters.gui.dialog_services import messagebox


class MainWindowColumnReorderController:
    """Owns day-column reordering actions for the main window."""

    def __init__(self, app):
        self.app = app
        deps = getattr(app, "gui_dependencies", None)
        if deps is None:
            raise RuntimeError("GUI Dependencies not available on app")
        self._tracked_write_uc = deps.tracked_write_usecase
        self._move_selected_columns_uc = deps.move_selected_columns

    def find_swap_partner(self, start_index: int, direction: int) -> int | None:
        return self._move_selected_columns_uc.find_swap_partner(self.app.day_columns, start_index, direction)

    @staticmethod
    def _has_ub_link(day: dict[str, object]) -> bool:
        yaml_data = day.get("yaml")
        if not isinstance(yaml_data, dict):
            return False
        return bool(str(yaml_data.get("Unterrichtsbesuch", "")).strip())

    def _requires_ub_confirmation(self, selected_index: int, partner_index: int) -> bool:
        if not (0 <= selected_index < len(self.app.day_columns)):
            return False
        if not (0 <= partner_index < len(self.app.day_columns)):
            return False
        selected_day = self.app.day_columns[selected_index]
        partner_day = self.app.day_columns[partner_index]
        return self._has_ub_link(selected_day) or self._has_ub_link(partner_day)

    def _confirm_ub_sensitive_move(self) -> bool:
        return bool(
            messagebox.askyesno(
                "Einheiten verschieben",
                "Mindestens eine der beiden Einheiten ist als Unterrichtsbesuch verknüpft.\n"
                "Beim Verschieben werden die UB-Referenzen und datumsbezogenen Verknüpfungen mit angepasst.\n\n"
                "Soll der Tausch trotzdem durchgeführt werden?",
                parent=self.app,
                default="no",
                icon="warning",
            )
        )

    def _run_tracked_write(
        self,
        *,
        label: str,
        action,
        extra_before: list[pathlib.Path] | None = None,
        extra_after: list[pathlib.Path] | None = None,
        extra_after_from_result=None,
    ):
        if self.app.current_table is None:
            return action()
        return self._tracked_write_uc.run_tracked_action(
            label=label,
            action=action,
            table=self.app.current_table,
            day_columns=self.app.day_columns,
            selected_day_indices=self.app.selected_day_indices,
            extra_before=extra_before,
            extra_after=extra_after,
            extra_after_from_result=extra_after_from_result,
        )

    def _refresh_after_write(self, *, selected_index: int | None = None) -> None:
        self.app._collect_day_columns()
        if isinstance(selected_index, int) and 0 <= selected_index < len(self.app.day_columns):
            self.app.selected_day_indices = {selected_index}
            self.app._update_selected_column_label()
        self.app._refresh_grid_content()
        self.app._update_selected_lesson_metrics()
        self.app.action_controller.update_action_controls()

    def move_selected_columns(self, direction: int):
        if self.app.current_table is None:
            return
        selected_index = self.app._get_single_selected_or_warn()
        if selected_index is None:
            return

        move_plan = self._move_selected_columns_uc.build_move_plan(
            self.app.day_columns,
            selected_index,
            direction,
        )
        if move_plan is None:
            return

        if self._requires_ub_confirmation(selected_index, move_plan.partner_index):
            if not self._confirm_ub_sensitive_move():
                return

        result = self._run_tracked_write(
            label="Einheiten verschieben",
            action=lambda: self._move_selected_columns_uc.execute(
                self.app.current_table,
                move_plan.row_a,
                move_plan.row_b,
            ),
        )
        if hasattr(result, "proceed") and not bool(getattr(result, "proceed", True)):
            messagebox.showerror(
                "Einheiten verschieben",
                getattr(result, "error_message", None) or "Verschieben fehlgeschlagen.",
                parent=self.app,
            )
            self._refresh_after_write(selected_index=selected_index)
            return

        self._refresh_after_write(selected_index=move_plan.partner_index)
