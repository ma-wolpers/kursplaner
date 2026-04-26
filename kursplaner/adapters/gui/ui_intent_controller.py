from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk

from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.adapters.gui.ui_intents import UiIntent


class MainWindowUiIntentController:
    """Kapselt zentrale UI-Intent- und Shortcut-Delegation der Hauptansicht."""

    def __init__(self, app):
        """Speichert den App-Adapter als Delegationsziel für Intents."""
        self.app = app

    def handle_intent(self, intent: str, **payload):
        """Orchestriert View-Intents zentral und delegiert an passende Controller."""
        if ScrollablePopupWindow.has_active_popup() and intent != UiIntent.SHORTCUT_ESCAPE:
            return "break"
        if self._should_block_toolbar_shortcut(intent, payload):
            return None

        if intent == UiIntent.TOOLBAR_NEW:
            self.app.action_controller.open_new_lesson_window()
            return None
        if intent == UiIntent.TOOLBAR_REFRESH:
            self.app.action_controller.refresh_overview()
            return None
        if intent == UiIntent.TOOLBAR_EXPORT_AS:
            self.app.action_controller.export_selected_topic_as_pdf_action()
            return None
        if intent == UiIntent.TOOLBAR_UNDO:
            if self._is_editable_widget(self._resolve_event_widget(payload.get("event"))):
                return None
            self.app.action_controller.undo_history()
            return "break"
        if intent == UiIntent.TOOLBAR_REDO:
            if self._is_editable_widget(self._resolve_event_widget(payload.get("event"))):
                return None
            self.app.action_controller.redo_history()
            return "break"
        if intent == UiIntent.EDIT_UNDO_TO_RECENT_INDEX:
            if self._is_editable_widget(self._resolve_event_widget(payload.get("event"))):
                return None
            recent_index = self.app._to_int(payload.get("recent_index", -1), -1)
            if recent_index >= 0:
                self.app.action_controller.undo_history_to_recent_index(recent_index)
            return "break"
        if intent == UiIntent.TOOLBAR_PLAN:
            self.app.lesson_conversion_controller.convert_selected_to_unterricht()
            return None
        if intent == UiIntent.TOOLBAR_EXTEND_TO_VACATION:
            self.app.action_controller.extend_plan_to_next_vacation()
            return None
        if intent == UiIntent.TOOLBAR_AUSFALL:
            selected_index = self.app._get_single_selected_or_warn()
            if selected_index is None:
                return None
            day_columns = list(getattr(self.app, "day_columns", []))
            if selected_index < 0 or selected_index >= len(day_columns):
                return None
            day = day_columns[selected_index]
            if bool(day.get("is_cancel", False)):
                self.app.action_controller.restore_selected_from_cancel_action()
            else:
                self.app.lesson_conversion_controller.convert_selected_to_ausfall()
            return None
        if intent == UiIntent.TOOLBAR_HOSPITATION:
            self.app.lesson_conversion_controller.convert_selected_to_hospitation()
            return None
        if intent == UiIntent.TOOLBAR_LZK:
            if bool(payload.get("from_shortcut", False)) and self._should_route_lzk_shortcut_to_expected_horizon():
                self.app.action_controller.export_selected_lzk_expected_horizon_action()
                return None
            self.app.lesson_conversion_controller.convert_selected_to_lzk()
            return None
        if intent == UiIntent.TOOLBAR_LZK_EXPECTED_HORIZON:
            self.app.action_controller.export_selected_lzk_expected_horizon_action()
            return None
        if intent == UiIntent.TOOLBAR_COPY:
            self.app.action_controller.copy_selected_lesson()
            return None
        if intent == UiIntent.TOOLBAR_PASTE:
            level = self.app.ui_state.selection_level
            if level == self.app.ui_state.SELECTION_LEVEL_COLUMN:
                self.app.action_controller.paste_copied_lesson()
                return None
            if level == self.app.ui_state.SELECTION_LEVEL_CELL:
                if self._is_editable_widget(self.app.focus_get()):
                    return None
                return self._paste_clipboard_into_selected_cell()
            return None
        if intent == UiIntent.TOOLBAR_FIND:
            self.app.action_controller.link_markdown_for_selected()
            return None
        if intent == UiIntent.TOOLBAR_CLEAR:
            self.app.action_controller.clear_selected_lesson_content()
            return None
        if intent == UiIntent.TOOLBAR_RENAME:
            self.app.action_controller.rename_selected_lesson()
            return None
        if intent == UiIntent.TOOLBAR_SPLIT:
            self.app.action_controller.split_selected_unit_action()
            return None
        if intent == UiIntent.TOOLBAR_MERGE:
            self.app.action_controller.merge_selected_units_action()
            return None
        if intent == UiIntent.TOOLBAR_RESUME:
            self.app.action_controller.restore_selected_from_cancel_action()
            return None
        if intent == UiIntent.TOOLBAR_MOVE_COLUMNS:
            direction = self.app._to_int(payload.get("direction", 0), 0)
            self.app.column_reorder_controller.move_selected_columns(direction)
            return None

        if intent == UiIntent.COURSE_CONFIRM_SELECTION:
            return self.intent_course_confirm_selection(payload.get("event"))
        if intent == UiIntent.COURSE_HOVER_SELECT:
            return self.intent_course_hover_select(payload.get("event"))
        if intent == UiIntent.COURSE_KEYBOARD_NAVIGATION:
            self.app._tree_hover_suspend_until = time.monotonic() + 0.6
            return None
        if intent == UiIntent.COURSE_HOME:
            return self.intent_course_edge(to_end=False)
        if intent == UiIntent.COURSE_END:
            return self.intent_course_edge(to_end=True)

        if intent == UiIntent.GRID_TOGGLE_COLUMN_SELECTION:
            return self.intent_grid_column_click(self.app._to_int(payload.get("day_index", -1), -1))
        if intent == UiIntent.GRID_TOGGLE_ROW_EXPAND:
            return self.intent_toggle_row_expand(str(payload.get("field_key", "")))
        if intent == UiIntent.GRID_COMMIT_CELL:
            field_key = str(payload.get("field_key", ""))
            day_index = self.app._to_int(payload.get("day_index", -1), -1)
            if field_key and day_index >= 0:
                self.app.editor_controller.save_cell(field_key, day_index)
            return None
        if intent == UiIntent.GRID_EDITOR_FOCUS_IN:
            field_key = str(payload.get("field_key", ""))
            day_index = self.app._to_int(payload.get("day_index", -1), -1)
            if field_key and day_index >= 0:
                self.app.ui_state.set_selected_cell(field_key, day_index)
                if self.app.editor_controller.handle_editor_focus_in(field_key, day_index):
                    self.app.ui_state.set_selection_level(self.app.ui_state.SELECTION_LEVEL_CELL)
                    self.app._refresh_grid_content()
                    return "break"
                self.app.ui_state.set_active_editor(field_key, day_index)
            return None
        if intent == UiIntent.GRID_EDITOR_FOCUS_OUT:
            field_key = str(payload.get("field_key", ""))
            day_index = self.app._to_int(payload.get("day_index", -1), -1)
            if field_key and day_index >= 0:
                self.app.ui_state.clear_active_editor_if_matches(field_key, day_index)
                if self.app.ui_state.selected_cell is not None:
                    self.app.ui_state.set_selection_level(self.app.ui_state.SELECTION_LEVEL_CELL)
            return None
        if intent == UiIntent.GRID_ENTER:
            return self.intent_grid_enter()
        if intent == UiIntent.GRID_NAV_UP:
            return self.intent_grid_nav_vertical(-1)
        if intent == UiIntent.GRID_NAV_DOWN:
            return self.intent_grid_nav_vertical(1)
        if intent == UiIntent.GRID_NAV_LEFT:
            return self.intent_grid_nav_horizontal(-1)
        if intent == UiIntent.GRID_NAV_RIGHT:
            return self.intent_grid_nav_horizontal(1)
        if intent == UiIntent.GRID_DELETE_CELL:
            return self.intent_grid_delete_cell(payload.get("event"))
        if intent == UiIntent.GRID_HOME:
            return self.intent_grid_home(payload.get("event"))
        if intent == UiIntent.GRID_END:
            return self.intent_grid_end(payload.get("event"))
        if intent == UiIntent.GRID_CELL_CLICK:
            return self.intent_grid_cell_click(
                field_key=str(payload.get("field_key", "")),
                day_index=self.app._to_int(payload.get("day_index", -1), -1),
            )
        if intent == UiIntent.GRID_DATE_CELL_CLICK:
            return self.intent_grid_date_cell_click(self.app._to_int(payload.get("day_index", -1), -1))
        if intent == UiIntent.GRID_COLUMN_CLICK:
            return self.intent_grid_column_click(self.app._to_int(payload.get("day_index", -1), -1))

        if intent == UiIntent.OPEN_SETTINGS:
            self.app.action_controller.open_settings_window()
            return None
        if intent == UiIntent.REBUILD_LESSON_INDEX:
            self.app.action_controller.rebuild_lesson_index()
            return None
        if intent == UiIntent.SHOW_SHADOW_LESSONS:
            self.app.action_controller.show_shadow_lessons()
            return None
        if intent == UiIntent.CLOSE_DETAIL_VIEW:
            self.app.overview_controller.close_detail_view()
            return None
        if intent == UiIntent.SET_ROW_MODE:
            mode_key = str(payload.get("mode_key", ""))
            manual = bool(payload.get("manual", True))
            self.app._set_row_mode(mode_key, manual=manual)
            return None
        if intent == UiIntent.TOGGLE_AUTO_ROW_MODE:
            self.app._on_toggle_auto_row_mode()
            return None
        if intent == UiIntent.MARK_SELECTED_AS_UB:
            self.app.action_controller.mark_selected_as_ub()
            return None
        if intent == UiIntent.TOGGLE_RESUME_OR_UB:
            self.app.action_controller.toggle_resume_or_mark_ub()
            return None
        if intent == UiIntent.SHOW_UB_ACHIEVEMENTS:
            self.app.action_controller.show_ub_achievements_view()
            return None
        if intent == UiIntent.SHOW_SHORTCUT_OVERVIEW:
            self.app.action_controller.show_shortcut_overview()
            return None
        if intent == UiIntent.OPEN_COLUMN_VISIBILITY_SETTINGS:
            self.app.action_controller.open_column_visibility_settings()
            return None
        if intent == UiIntent.TOGGLE_EXPAND_MODE:
            return self.intent_toggle_expand_mode()

        if intent == UiIntent.SHORTCUT_DETAIL_LEFT:
            return self.intent_detail_left()
        if intent == UiIntent.SHORTCUT_DETAIL_RIGHT:
            return self.intent_detail_right()
        if intent == UiIntent.SHORTCUT_DETAIL_LEFT_ALL:
            return self.intent_detail_left_all()
        if intent == UiIntent.SHORTCUT_DETAIL_RIGHT_ALL:
            return self.intent_detail_right_all()
        if intent == UiIntent.SHORTCUT_ESCAPE:
            return self.intent_escape()
        if intent == UiIntent.SHORTCUT_COMMIT_COLUMN:
            return self.intent_commit_column()
        if intent == UiIntent.SHORTCUT_COMMIT_EDIT:
            return self.intent_commit_edit()
        if intent == UiIntent.SHORTCUT_EXPAND_SELECTED_ROW:
            return self.intent_set_selected_row_expanded(payload.get("event"), expanded=True)
        if intent == UiIntent.SHORTCUT_COLLAPSE_SELECTED_ROW:
            return self.intent_set_selected_row_expanded(payload.get("event"), expanded=False)
        if intent == UiIntent.SHORTCUT_CUT:
            return self.intent_clipboard_shortcut(payload.get("event"), operation="cut")
        if intent == UiIntent.SHORTCUT_COPY:
            return self.intent_clipboard_shortcut(payload.get("event"), operation="copy")
        if intent == UiIntent.SHORTCUT_PASTE:
            return self.intent_clipboard_shortcut(payload.get("event"), operation="paste")
        if intent == UiIntent.GLOBAL_CLICK_COMMIT_CELL:
            return self.intent_global_click_commit_cell(payload.get("event"))

        return None

    def _should_block_toolbar_shortcut(self, intent: str, payload: dict[str, object]) -> bool:
        """Blockt Toolbar-Shortcuts außerhalb des passenden Kontexts."""
        if not bool(payload.get("from_shortcut", False)):
            return False

        if intent in {UiIntent.TOOLBAR_CLEAR, UiIntent.TOOLBAR_COPY, UiIntent.TOOLBAR_PASTE}:
            return self.app.ui_state.selection_level != self.app.ui_state.SELECTION_LEVEL_COLUMN

        if intent == UiIntent.TOOLBAR_LZK:
            if not bool(getattr(self.app, "is_detail_view", False)):
                return True
            visible_actions = set(getattr(self.app.ui_state, "visible_toolbar_actions", set()))
            return not bool({"lzk", "lzk_expected_horizon"} & visible_actions)

        if intent == UiIntent.TOGGLE_RESUME_OR_UB:
            if not bool(getattr(self.app, "is_detail_view", False)):
                return True
            visible_actions = set(getattr(self.app.ui_state, "visible_toolbar_actions", set()))
            return not ({"ausfall", "mark_ub"} & visible_actions)

        action_key_by_intent = {
            UiIntent.TOOLBAR_EXTEND_TO_VACATION: "extend_to_vacation",
            UiIntent.TOOLBAR_EXPORT_AS: "export_as",
            UiIntent.TOOLBAR_PLAN: "plan",
            UiIntent.TOOLBAR_AUSFALL: "ausfall",
            UiIntent.TOOLBAR_HOSPITATION: "hospitation",
            UiIntent.TOOLBAR_LZK: "lzk",
            UiIntent.TOOLBAR_LZK_EXPECTED_HORIZON: "lzk_expected_horizon",
            UiIntent.TOOLBAR_COPY: "copy",
            UiIntent.TOOLBAR_PASTE: "paste",
            UiIntent.TOOLBAR_FIND: "find",
            UiIntent.TOOLBAR_CLEAR: "clear",
            UiIntent.TOOLBAR_RENAME: "rename",
            UiIntent.TOOLBAR_SPLIT: "split",
            UiIntent.TOOLBAR_MERGE: "merge",
            UiIntent.TOOLBAR_RESUME: "resume",
            UiIntent.TOOLBAR_MOVE_COLUMNS: "move_left"
            if self.app._to_int(payload.get("direction", 0), 0) < 0
            else "move_right",
        }

        action_key = action_key_by_intent.get(intent)
        if action_key is None:
            return False

        if intent == UiIntent.TOOLBAR_MOVE_COLUMNS:
            return self.app.ui_state.selection_level != self.app.ui_state.SELECTION_LEVEL_COLUMN

        if not bool(getattr(self.app, "is_detail_view", False)):
            return True
        visible_actions = set(getattr(self.app.ui_state, "visible_toolbar_actions", set()))
        return action_key not in visible_actions

    def _should_route_lzk_shortcut_to_expected_horizon(self) -> bool:
        """Uses shared Ctrl+K shortcut for KH export when convert button is disjointly unavailable."""
        visible_actions = set(getattr(self.app.ui_state, "visible_toolbar_actions", set()))
        if "lzk_expected_horizon" not in visible_actions:
            return False
        if "lzk" in visible_actions:
            return False
        return True

    def intent_course_confirm_selection(self, event):
        if event is not None:
            event_type = getattr(event, "type", None)
            is_mouse_event = event_type in (tk.EventType.ButtonPress, tk.EventType.ButtonRelease)
            if is_mouse_event:
                try:
                    mouse_button = int(getattr(event, "num", 0))
                except (TypeError, ValueError):
                    mouse_button = 0
                if mouse_button == 1:
                    clicked_item = self.app.lesson_tree.identify_row(int(getattr(event, "y", -1)))
                    if not clicked_item:
                        return "break"
                    self.app.lesson_tree.focus(clicked_item)
                    self.app.lesson_tree.selection_set(clicked_item)
        self.app.overview_controller.load_selected_table(event)
        return "break"

    def intent_course_hover_select(self, event):
        if bool(getattr(self.app, "is_detail_view", False)):
            return None
        if time.monotonic() < float(getattr(self.app, "_tree_hover_suspend_until", 0.0)):
            return None
        if event is None:
            return None
        item = self.app.lesson_tree.identify_row(event.y)
        if not item:
            return None
        current = self.app.lesson_tree.focus()
        if current == item:
            return None
        self.app.lesson_tree.focus(item)
        self.app.lesson_tree.selection_set(item)
        return None

    def intent_toggle_row_expand(self, field_key: str):
        if not field_key:
            return None
        current = bool(self.app.row_expanded.get(field_key, False))
        self.app.row_expanded[field_key] = not current
        self._apply_row_layout_change()
        return None

    def intent_toggle_expand_mode(self):
        expand_all = bool(self.app.expand_long_rows_var.get())
        for field_key, _ in self.app.row_defs:
            self.app.row_expanded[field_key] = expand_all
        self._apply_row_layout_change()
        return None

    def intent_detail_left(self):
        if not bool(getattr(self.app, "is_detail_view", False)):
            return None
        if self.app.ui_state.selection_level == self.app.ui_state.SELECTION_LEVEL_CELL:
            moved = self.intent_grid_nav_horizontal(-1)
            return "break" if moved else None
        if self.app.ui_state.selection_level == self.app.ui_state.SELECTION_LEVEL_EDIT:
            return None
        if self.app.ui_state.selection_level != self.app.ui_state.SELECTION_LEVEL_COLUMN:
            return None
        if isinstance(self.app.focus_get(), tk.Text):
            return None
        moved = self.app.selection_controller.move_selection_to_adjacent_occurring(-1)
        return "break" if moved else None

    def intent_detail_right(self):
        if not bool(getattr(self.app, "is_detail_view", False)):
            return None
        if self.app.ui_state.selection_level == self.app.ui_state.SELECTION_LEVEL_CELL:
            moved = self.intent_grid_nav_horizontal(1)
            return "break" if moved else None
        if self.app.ui_state.selection_level == self.app.ui_state.SELECTION_LEVEL_EDIT:
            return None
        if self.app.ui_state.selection_level != self.app.ui_state.SELECTION_LEVEL_COLUMN:
            return None
        if isinstance(self.app.focus_get(), tk.Text):
            return None
        moved = self.app.selection_controller.move_selection_to_adjacent_occurring(1)
        return "break" if moved else None

    def intent_detail_left_all(self):
        if not bool(getattr(self.app, "is_detail_view", False)):
            return None
        if self.app.ui_state.selection_level != self.app.ui_state.SELECTION_LEVEL_COLUMN:
            return None
        moved = self.app.selection_controller.move_selection_to_adjacent(-1)
        return "break" if moved else None

    def intent_detail_right_all(self):
        if not bool(getattr(self.app, "is_detail_view", False)):
            return None
        if self.app.ui_state.selection_level != self.app.ui_state.SELECTION_LEVEL_COLUMN:
            return None
        moved = self.app.selection_controller.move_selection_to_adjacent(1)
        return "break" if moved else None

    def intent_escape(self):
        focused = self.app.focus_get()
        if bool(getattr(self.app, "is_detail_view", False)):
            level = self.app.ui_state.selection_level
            if level == self.app.ui_state.SELECTION_LEVEL_EDIT or isinstance(focused, tk.Text):
                self._leave_edit_mode_to_cell(set_grid_focus=True)
                return "break"
            if level == self.app.ui_state.SELECTION_LEVEL_CELL:
                self.app.selection_controller.clear_selected_cell()
                self.app.ui_state.set_selection_level(self.app.ui_state.SELECTION_LEVEL_COLUMN)
                self.app.grid_canvas.focus_set()
                return "break"
            if level == self.app.ui_state.SELECTION_LEVEL_COLUMN:
                self.app.overview_controller.close_detail_view()
                return "break"
        if isinstance(focused, tk.Text):
            self.app.grid_canvas.focus_set()
            return "break"
        if bool(getattr(self.app, "is_detail_view", False)):
            self.app.overview_controller.close_detail_view()
            return "break"
        return None

    def intent_commit_edit(self):
        if not bool(getattr(self.app, "is_detail_view", False)):
            return None
        if self.app.ui_state.selection_level != self.app.ui_state.SELECTION_LEVEL_EDIT:
            return None
        if not self._leave_edit_mode_to_cell(set_grid_focus=True):
            return "break"
        return "break"

    def intent_commit_column(self):
        if not bool(getattr(self.app, "is_detail_view", False)):
            return None
        if self.app.ui_state.selection_level != self.app.ui_state.SELECTION_LEVEL_COLUMN:
            return None
        if self._is_editable_widget(self.app.focus_get()):
            return None

        selected_index = self.app._get_single_selected_or_warn()
        if selected_index is None:
            return None

        day_columns = list(getattr(self.app, "day_columns", []))
        if selected_index < 0 or selected_index >= len(day_columns):
            return None

        day = day_columns[selected_index]
        if bool(day.get("is_cancel", False)):
            self.app.lesson_conversion_controller.convert_selected_to_ausfall(from_column_shortcut=True)
            return "break"
        if bool(day.get("is_hospitation", False)):
            self.app.lesson_conversion_controller.convert_selected_to_hospitation(from_column_shortcut=True)
            return "break"
        if bool(day.get("is_lzk", False)):
            self.app.lesson_conversion_controller.convert_selected_to_lzk(from_column_shortcut=True)
            return "break"

        self.app.lesson_conversion_controller.convert_selected_to_unterricht(from_column_shortcut=True)
        return "break"

    def intent_grid_enter(self):
        if not bool(getattr(self.app, "is_detail_view", False)):
            return None
        if self.app.ui_state.selection_level == self.app.ui_state.SELECTION_LEVEL_EDIT:
            return None
        focused = self.app.focus_get()
        if isinstance(focused, tk.Text):
            return None

        if self.app.ui_state.selection_level == self.app.ui_state.SELECTION_LEVEL_CELL:
            selected_cell = self.app.ui_state.selected_cell
            if selected_cell is None:
                return None
            widget = self.app.cell_widgets.get((selected_cell.field_key, selected_cell.day_index))
            if widget is None:
                return None
            widget.focus_set()
            widget.mark_set("insert", "end-1c")
            widget.see("insert")
            return "break"

        moved = self.app.selection_controller.select_first_editable_in_selected_column()
        return "break" if moved else None

    def intent_grid_cell_click(self, *, field_key: str, day_index: int):
        if not bool(getattr(self.app, "is_detail_view", False)):
            return None
        if not field_key or not (0 <= day_index < len(self.app.day_columns)):
            return None
        day = self.app.day_columns[day_index]
        if not self.app.row_display_mode_usecase.is_editable(field_key, day):
            return None

        focused = self.app.focus_get()
        active = self.app.ui_state.active_editor
        if (
            active is not None
            and active.field_key == field_key
            and active.day_index == day_index
            and isinstance(focused, tk.Text)
        ):
            return None

        if active is not None:
            if not self._leave_edit_mode_to_cell(set_grid_focus=True):
                return "break"

        selected = self.app.ui_state.selected_cell
        if (
            selected is not None
            and selected.field_key == field_key
            and selected.day_index == day_index
            and self.app.ui_state.selection_level == self.app.ui_state.SELECTION_LEVEL_CELL
        ):
            return self.intent_grid_enter()

        moved = self.app.selection_controller.set_selected_cell(field_key, day_index, ensure_visible=True)
        if not moved:
            return None
        self.app.grid_canvas.focus_set()
        return "break"

    def intent_grid_date_cell_click(self, day_index: int):
        if not bool(getattr(self.app, "is_detail_view", False)):
            return None
        if not (0 <= day_index < len(self.app.day_columns)):
            return None
        if self.app.ui_state.active_editor is not None:
            if not self._leave_edit_mode_to_cell(set_grid_focus=True):
                return "break"
        self.app.selection_controller.set_single_column_selection(day_index, ensure_visible=True)
        self.app.grid_canvas.focus_set()
        return "break"

    def intent_grid_column_click(self, day_index: int):
        if not bool(getattr(self.app, "is_detail_view", False)):
            return None
        if not (0 <= day_index < len(self.app.day_columns)):
            return None
        if self.app.ui_state.active_editor is not None:
            if not self._leave_edit_mode_to_cell(set_grid_focus=True):
                return "break"

        selected = self.app.selection_controller.selected_indices_sorted()
        is_same_selected_column = (
            len(selected) == 1
            and selected[0] == day_index
            and self.app.ui_state.selection_level == self.app.ui_state.SELECTION_LEVEL_COLUMN
        )
        if is_same_selected_column:
            return self.intent_grid_enter()

        self.app.selection_controller.set_single_column_selection(day_index, ensure_visible=True)
        self.app.grid_canvas.focus_set()
        return "break"

    def intent_grid_nav_vertical(self, direction: int):
        if not bool(getattr(self.app, "is_detail_view", False)):
            return None
        if self.app.ui_state.selection_level != self.app.ui_state.SELECTION_LEVEL_CELL:
            return None
        if isinstance(self.app.focus_get(), tk.Text):
            return None
        moved = self.app.selection_controller.move_selected_cell_vertical(direction)
        return "break" if moved else None

    def intent_grid_nav_horizontal(self, direction: int):
        if not bool(getattr(self.app, "is_detail_view", False)):
            return None
        if self.app.ui_state.selection_level != self.app.ui_state.SELECTION_LEVEL_CELL:
            return None
        if isinstance(self.app.focus_get(), tk.Text):
            return None
        moved = self.app.selection_controller.move_selected_cell_horizontal(direction)
        return "break" if moved else None

    def intent_grid_delete_cell(self, event=None):
        if not bool(getattr(self.app, "is_detail_view", False)):
            return None
        if self.app.ui_state.selection_level != self.app.ui_state.SELECTION_LEVEL_CELL:
            return None
        if self._is_editable_widget(self._resolve_event_widget(event)):
            return None
        if self._is_editable_widget(self.app.focus_get()):
            return None
        selected = self.app.ui_state.selected_cell
        if selected is None:
            return None
        day_index = selected.day_index
        field_key = selected.field_key
        if not (0 <= day_index < len(self.app.day_columns)):
            return None
        day = self.app.day_columns[day_index]
        if not self.app.row_display_mode_usecase.is_editable(field_key, day):
            return None
        self.app.editor_controller.apply_value(field_key, day_index, "")
        self.app._collect_day_columns()
        self.app._update_grid_column(day_index)
        self.app._update_selected_lesson_metrics()
        self.app.action_controller.update_action_controls()
        self.app.selection_controller.set_selected_cell(field_key, day_index, ensure_visible=True)
        return "break"

    def intent_grid_home(self, event=None):
        if not bool(getattr(self.app, "is_detail_view", False)):
            return None
        if self._is_editable_widget(self._resolve_event_widget(event)):
            return None
        if self._is_editable_widget(self.app.focus_get()):
            return None
        level = self.app.ui_state.selection_level
        if level == self.app.ui_state.SELECTION_LEVEL_CELL:
            moved = self.app.selection_controller.move_selected_cell_to_edge(to_end=False)
            return "break" if moved else None
        if level == self.app.ui_state.SELECTION_LEVEL_COLUMN:
            moved = self.app.selection_controller.set_edge_column_selection(to_end=False, ensure_visible=True)
            return "break" if moved else None
        return None

    def intent_grid_end(self, event=None):
        if not bool(getattr(self.app, "is_detail_view", False)):
            return None
        if self._is_editable_widget(self._resolve_event_widget(event)):
            return None
        if self._is_editable_widget(self.app.focus_get()):
            return None
        level = self.app.ui_state.selection_level
        if level == self.app.ui_state.SELECTION_LEVEL_CELL:
            moved = self.app.selection_controller.move_selected_cell_to_edge(to_end=True)
            return "break" if moved else None
        if level == self.app.ui_state.SELECTION_LEVEL_COLUMN:
            moved = self.app.selection_controller.set_edge_column_selection(to_end=True, ensure_visible=True)
            return "break" if moved else None
        return None

    def intent_course_edge(self, *, to_end: bool):
        if bool(getattr(self.app, "is_detail_view", False)):
            return None
        items = list(self.app.lesson_tree.get_children())
        if not items:
            return None
        target = items[-1] if to_end else items[0]
        self.app.lesson_tree.focus(target)
        self.app.lesson_tree.selection_set(target)
        self.app.lesson_tree.see(target)
        return "break"

    def intent_clipboard_shortcut(self, event, *, operation: str):
        if not bool(getattr(self.app, "is_detail_view", False)):
            return None
        if operation not in {"cut", "copy", "paste"}:
            return None

        event_widget = self._resolve_event_widget(event)
        if self._is_editable_widget(event_widget):
            return None
        if self._is_editable_widget(self.app.focus_get()):
            return None

        level = self.app.ui_state.selection_level
        if level == self.app.ui_state.SELECTION_LEVEL_COLUMN:
            if operation == "copy":
                self.app.action_controller.copy_selected_lesson()
                return "break"
            if operation == "paste":
                self.app.action_controller.paste_copied_lesson()
                return "break"
            return None

        if level == self.app.ui_state.SELECTION_LEVEL_CELL:
            if operation == "copy":
                return self._copy_selected_cell_to_clipboard()
            if operation == "paste":
                return self._paste_clipboard_into_selected_cell()
            if operation == "cut":
                if self._copy_selected_cell_to_clipboard() != "break":
                    return None
                return self._set_selected_cell_value("")

        return None

    def _copy_selected_cell_to_clipboard(self):
        selected = self.app.ui_state.selected_cell
        if selected is None:
            return None
        cell_widget = self.app.cell_widgets.get((selected.field_key, selected.day_index))
        if cell_widget is None:
            return None
        value = cell_widget.get("1.0", "end-1c")
        try:
            self.app.clipboard_clear()
            self.app.clipboard_append(value)
        except tk.TclError:
            return None
        return "break"

    def _paste_clipboard_into_selected_cell(self):
        clipboard_text = self._get_clipboard_text()
        if clipboard_text is None or not clipboard_text.strip():
            return None
        return self._set_selected_cell_value(clipboard_text)

    def intent_set_selected_row_expanded(self, event, *, expanded: bool):
        if not bool(getattr(self.app, "is_detail_view", False)):
            return None
        if self.app.ui_state.selection_level != self.app.ui_state.SELECTION_LEVEL_CELL:
            return None
        if self._is_editable_widget(self._resolve_event_widget(event)):
            return None
        if self._is_editable_widget(self.app.focus_get()):
            return None

        selected = self.app.ui_state.selected_cell
        if selected is None:
            return None
        field_key = str(selected.field_key or "")
        if not field_key:
            return None

        current = bool(self.app.row_expanded.get(field_key, False))
        target = bool(expanded)
        if current == target:
            return "break"

        self.app.row_expanded[field_key] = target
        self._apply_row_layout_change()
        return "break"

    def _apply_row_layout_change(self) -> None:
        """Wendet Zeilenlayout-Aenderungen atomar an (Rebuild + Sichtbarkeitssync)."""
        self.app._rebuild_grid()
        self._ensure_selected_cell_visible_after_layout_change()

    def _ensure_selected_cell_visible_after_layout_change(self) -> None:
        """Stellt nach Layout-Updates sicher, dass die aktive Zelle im Sichtbereich bleibt."""
        selected = getattr(self.app.ui_state, "selected_cell", None)
        if selected is None:
            return

        field_key = str(getattr(selected, "field_key", "") or "")
        day_index = int(getattr(selected, "day_index", -1))
        if not field_key or day_index < 0:
            return

        cell_widgets = getattr(self.app, "cell_widgets", {})
        if (field_key, day_index) not in cell_widgets:
            return

        selection_controller = getattr(self.app, "selection_controller", None)
        if selection_controller is None:
            return

        selection_controller.ensure_column_visible(day_index)
        selection_controller.ensure_row_visible(field_key, day_index)

    def _get_clipboard_text(self) -> str | None:
        try:
            clipboard_text = self.app.clipboard_get()
        except tk.TclError:
            return None
        if clipboard_text is None:
            return None
        return str(clipboard_text)

    def _set_selected_cell_value(self, value: str):
        selected = self.app.ui_state.selected_cell
        if selected is None:
            return None
        day_index = selected.day_index
        field_key = selected.field_key
        if not (0 <= day_index < len(self.app.day_columns)):
            return None
        day = self.app.day_columns[day_index]
        if not self.app.row_display_mode_usecase.is_editable(field_key, day):
            return None
        self.app.editor_controller.apply_value(field_key, day_index, value)
        self.app._collect_day_columns()
        self.app._update_grid_column(day_index)
        self.app._update_selected_lesson_metrics()
        self.app.action_controller.update_action_controls()
        self.app.selection_controller.set_selected_cell(field_key, day_index, ensure_visible=True)
        return "break"

    def intent_global_click_commit_cell(self, event):
        active_editor = self.app.ui_state.active_editor
        if active_editor is None:
            return None

        focused = self.app.focus_get()
        if focused is None or not isinstance(focused, tk.Text):
            return None

        if event is not None and getattr(event, "widget", None) is focused:
            return None

        self._leave_edit_mode_to_cell(set_grid_focus=False)
        return None

    def _leave_edit_mode_to_cell(self, *, set_grid_focus: bool) -> bool:
        """Beendet die aktive Bearbeitung Esc-äquivalent und kehrt in den Zellmodus zurück."""
        active_editor = self.app.ui_state.active_editor
        if active_editor is None:
            return True
        saved = self.app.editor_controller.save_cell(active_editor.field_key, active_editor.day_index)
        if not saved:
            return False
        self.app.ui_state.clear_active_editor()
        if self.app.ui_state.selected_cell is None:
            self.app.ui_state.set_selected_cell(active_editor.field_key, active_editor.day_index)
        else:
            self.app.ui_state.set_selection_level(self.app.ui_state.SELECTION_LEVEL_CELL)
        if set_grid_focus:
            self.app.grid_canvas.focus_set()
        return True

    def should_handle_global_clipboard_shortcut(self, event, operation: str) -> bool:
        if operation not in {"cut", "copy", "paste"}:
            return False

        if event is not None and (int(getattr(event, "state", 0)) & 0x0008):
            return False

        event_widget = self._resolve_event_widget(event)
        if self._is_editable_widget(event_widget):
            return False

        widget = self.app.focus_get()
        if self._is_editable_widget(widget):
            return False

        level = self.app.ui_state.selection_level
        if level == self.app.ui_state.SELECTION_LEVEL_COLUMN:
            return operation in {"copy", "paste"}
        if level == self.app.ui_state.SELECTION_LEVEL_CELL:
            return operation in {"cut", "copy", "paste"}
        return False

    @staticmethod
    def _resolve_event_widget(event):
        if event is None:
            return None
        return getattr(event, "widget", None)

    @staticmethod
    def _is_editable_widget(widget) -> bool:
        if widget is None:
            return False
        editable_widget_types = (tk.Entry, tk.Text, tk.Spinbox, ttk.Entry, ttk.Combobox)
        return isinstance(widget, editable_widget_types)

    @staticmethod
    def widget_has_text_selection(widget) -> bool:
        try:
            if isinstance(widget, tk.Text):
                return bool(widget.tag_ranges("sel"))
            if hasattr(widget, "selection_present"):
                return bool(widget.selection_present())
            if hasattr(widget, "selection_get"):
                selected = widget.selection_get()
                return bool(str(selected).strip())
        except tk.TclError:
            return False
        return False
