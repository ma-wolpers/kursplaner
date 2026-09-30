"""Toolbar layout, course views and theme application of the main window (ScreenBuilder mixin).

Split out of screen_builder.py (file-size rule); method bodies unchanged."""

from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.theming import theme_canvas

from kursplaner.adapters.gui.toolbar_viewmodel import TOOLBAR_SEPARATOR_SLOTS, TOOLBAR_SLOT_MIN_WIDTH
from kursplaner.adapters.gui.ui_theme import (
    apply_window_theme,
    configure_ttk_theme,
)


class ScreenToolbarMixin:
    """Toolbar layout, course views and theme application of the main window (ScreenBuilder mixin)."""

    def refresh_course_overview_toolbar(self) -> None:
        """Synchronisiert Toggle-Beschriftung der Kursübersichts-Toolbar."""
        button = getattr(self.app, "course_overview_toggle_button", None)
        if button is None:
            return
        show_former = bool(getattr(self.app, "show_former_courses", False))
        button.configure(text="Ehemalige ausblenden" if show_former else "Ehemalige anzeigen")

    @staticmethod
    def _slot_width(slot_key: str) -> int:
        return int(TOOLBAR_SLOT_MIN_WIDTH.get(slot_key, 56)) + 2

    def _split_group_by_width(self, group: list[str], max_width: int) -> list[list[str]]:
        parts: list[list[str]] = []
        current: list[str] = []
        current_width = 0
        for slot_key in group:
            slot_width = self._slot_width(slot_key)
            if current and (current_width + slot_width) > max_width:
                parts.append(current)
                current = [slot_key]
                current_width = slot_width
            else:
                current.append(slot_key)
                current_width += slot_width
        if current:
            parts.append(current)
        return parts

    def _build_toolbar_rows(self, max_width: int) -> list[list[str]]:
        groups: list[list[str]] = [
            [
                "new",
                "refresh",
                "extend_to_vacation",
                "sep_primary",
                "undo",
                "redo",
                "sep_extend",
            ],
            ["plan", "ausfall", "hospitation", "lzk", "lzk_expected_horizon", "mark_ub", "sep_secondary"],
            [
                "copy",
                "paste",
                "find",
                "clear",
                "rename",
                "move_left",
                "move_right",
                "export_as",
            ],
        ]

        rows: list[list[str]] = [[]]
        row_width = 0

        for group in groups:
            group_width = sum(self._slot_width(item) for item in group)
            parts = [group] if group_width <= max_width else self._split_group_by_width(group, max_width)

            for part in parts:
                part_width = sum(self._slot_width(item) for item in part)
                if rows[-1] and (row_width + part_width) > max_width:
                    rows.append(list(part))
                    row_width = part_width
                else:
                    rows[-1].extend(part)
                    row_width += part_width

        cleaned_rows: list[list[str]] = []
        for row in rows:
            if not row:
                continue
            compact = list(row)
            while compact and compact[0] in TOOLBAR_SEPARATOR_SLOTS:
                compact.pop(0)
            while compact and compact[-1] in TOOLBAR_SEPARATOR_SLOTS:
                compact.pop()
            if compact:
                cleaned_rows.append(compact)

        return cleaned_rows

    def _layout_toolbar_slots(self):
        toolbar = getattr(self.app, "toolbar_frame", None)
        slots = getattr(self.app, "toolbar_slots", None)
        if toolbar is None or not isinstance(slots, dict):
            return

        available_width = max(int(toolbar.winfo_width()) - 8, 260)
        rows = self._build_toolbar_rows(available_width)

        for slot in slots.values():
            slot.grid_forget()

        for row_idx, row in enumerate(rows):
            for col_idx, slot_key in enumerate(row):
                slot = slots.get(slot_key)
                if slot is None:
                    continue
                slot.grid(row=row_idx, column=col_idx, sticky="w", padx=(0, 2), pady=(0 if row_idx == 0 else 2, 0))

    def _on_toolbar_configure(self, _event=None):
        toolbar = getattr(self.app, "toolbar_frame", None)
        if toolbar is None:
            return
        width = int(toolbar.winfo_width())
        if width == self._last_toolbar_wrap_width:
            return
        self._last_toolbar_wrap_width = width
        self._layout_toolbar_slots()

    def show_course_overview(self):
        """Zeigt nur die Kursübersicht und blendet die Detailansicht aus."""
        pane = self.app.main_paned
        panes = set(str(item) for item in pane.panes())
        detail = str(self.app.detail_panel)
        course = str(self.app.course_panel)
        if detail in panes:
            pane.forget(self.app.detail_panel)
        panes = set(str(item) for item in pane.panes())
        if course not in panes:
            pane.add(self.app.course_panel, weight=1)
        self.app.is_detail_view = False
        self.refresh_course_overview_toolbar()
        self.app.overview_controller.ensure_course_selected(prefer_first=True)
        self.app.after_idle(self.app.lesson_tree.focus_set)

    def show_course_detail(self):
        """Zeigt nur die Detailansicht und blendet die Kursliste aus."""
        pane = self.app.main_paned
        panes = set(str(item) for item in pane.panes())
        course = str(self.app.course_panel)
        detail = str(self.app.detail_panel)
        if course in panes:
            pane.forget(self.app.course_panel)
        panes = set(str(item) for item in pane.panes())
        if detail not in panes:
            pane.add(self.app.detail_panel, weight=1)
        self.app.is_detail_view = True
        self.app.after_idle(self.app.grid_canvas.focus_set)

    def _apply_theme(self):
        """Wendet das ausgewählte Theme auf Fenster und Grid-Canvas an."""
        theme_key = self.app.theme_var.get()
        apply_window_theme(self.app, theme_key)
        configure_ttk_theme(self.app, theme_key)
        styler = getattr(self.app, "toolbar_icon_styler", None)
        if styler is not None:
            styler.apply_state_overrides()
        theme_canvas(self.app.fixed_canvas)
        self.app.fixed_canvas.configure(highlightthickness=0)
        theme_canvas(self.app.grid_canvas)
        self.app.grid_canvas.configure(highlightthickness=0)
