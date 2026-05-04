from __future__ import annotations

from datetime import datetime

from kursplaner.adapters.gui.dialog_services import messagebox
from kursplaner.adapters.gui.ui_theme import get_theme


class MainWindowSelectionController:
    """Kapselt Spaltenselektion und Header-Statusdarstellung."""

    def __init__(self, app):
        """Speichert die App-Referenz für Selektion und Header-Updates."""
        self.app = app

    def toggle_column_selection(self, day_index: int):
        """Schaltet die Selektion einer Tages-Spalte um und aktualisiert Header/UI-Status."""
        if day_index in self.app.selected_day_indices:
            self.app.selected_day_indices = set()
            self.clear_selected_cell()
            self.app.ui_state.set_selection_level(self.app.ui_state.SELECTION_LEVEL_COLUMN)
        else:
            self.app.selected_day_indices = {day_index}
            self.clear_selected_cell()
            self.app.ui_state.set_selection_level(self.app.ui_state.SELECTION_LEVEL_COLUMN)
        self.update_selected_column_label()
        self.app._update_row_mode_from_selection()
        self.refresh_header_styles()
        self.app._refresh_grid_content()
        self.app.action_controller.update_action_controls()

    def set_single_column_selection(self, day_index: int, *, ensure_visible: bool = False):
        """Setzt genau eine selektierte Spalte und optional den horizontalen Viewport darauf."""
        if not (0 <= day_index < len(self.app.day_columns)):
            return
        self.app.selected_day_indices = {day_index}
        self.clear_selected_cell()
        self.app.ui_state.set_selection_level(self.app.ui_state.SELECTION_LEVEL_COLUMN)
        self.update_selected_column_label()
        self.app._update_row_mode_from_selection()
        self.refresh_header_styles()
        self.app._refresh_grid_content()
        self.app.action_controller.update_action_controls()
        if ensure_visible:
            self.ensure_column_visible(day_index)

    def clear_selected_cell(self):
        """Entfernt die aktuelle Zellmarkierung und aktualisiert das Grid-Styling."""
        if self.app.ui_state.selected_cell is None:
            return
        self.app.ui_state.clear_selected_cell()
        self.app._refresh_grid_content()

    def set_selected_cell(self, field_key: str, day_index: int, *, ensure_visible: bool = False) -> bool:
        """Markiert eine editierbare Zelle als aktive Navigationszelle."""
        if not (0 <= day_index < len(self.app.day_columns)):
            return False
        day = self.app.day_columns[day_index]
        if not self.app.row_display_mode_usecase.is_editable(field_key, day):
            return False
        self.app.selected_day_indices = {day_index}
        self.app.ui_state.set_selected_cell(field_key, day_index)
        self.update_selected_column_label()
        self.app._update_row_mode_from_selection()
        self.refresh_header_styles()
        self.app._refresh_grid_content()
        self.app.action_controller.update_action_controls()
        if ensure_visible:
            self.ensure_column_visible(day_index)
            self.ensure_row_visible(field_key, day_index)
        return True

    def select_first_editable_in_selected_column(self) -> bool:
        """Markiert die erste editierbare Zelle der aktuell ausgewählten Spalte."""
        selected = self.selected_indices_sorted()
        if len(selected) != 1:
            return False
        day_index = selected[0]
        for field_key, _label in self.app.row_defs:
            if self.app.row_display_mode_usecase.is_editable(field_key, self.app.day_columns[day_index]):
                return self.set_selected_cell(field_key, day_index, ensure_visible=True)
        return False

    def move_selected_cell_vertical(self, direction: int) -> bool:
        """Navigiert innerhalb der aktuellen Spalte zur nächsten editierbaren Zelle."""
        if direction not in (-1, 1):
            return False
        selected_cell = self.app.ui_state.selected_cell
        if selected_cell is None:
            return False
        day_index = selected_cell.day_index
        field_order = [field_key for field_key, _ in self.app.row_defs]
        if selected_cell.field_key not in field_order:
            return False
        current_pos = field_order.index(selected_cell.field_key)
        probe = current_pos + direction
        while 0 <= probe < len(field_order):
            candidate = field_order[probe]
            if self.app.row_display_mode_usecase.is_editable(candidate, self.app.day_columns[day_index]):
                return self.set_selected_cell(candidate, day_index, ensure_visible=True)
            probe += direction
        return False

    def move_selected_cell_horizontal(self, direction: int) -> bool:
        """Navigiert horizontal im gleichen Feld zur nächsten passenden Spalte."""
        if direction not in (-1, 1):
            return False
        selected_cell = self.app.ui_state.selected_cell
        if selected_cell is None:
            return False

        probe = selected_cell.day_index + direction
        while 0 <= probe < len(self.app.day_columns):
            day = self.app.day_columns[probe]
            if self.app.row_display_mode_usecase.is_editable(selected_cell.field_key, day):
                return self.set_selected_cell(selected_cell.field_key, probe, ensure_visible=True)
            probe += direction
        return False

    def move_selected_cell_to_edge(self, *, to_end: bool) -> bool:
        """Springt in der aktuellen Spalte zur ersten oder letzten editierbaren Zelle."""
        selected_cell = self.app.ui_state.selected_cell
        if selected_cell is None:
            return False
        day_index = selected_cell.day_index
        field_order = [field_key for field_key, _ in self.app.row_defs]
        ordered = list(reversed(field_order)) if to_end else field_order
        for field_key in ordered:
            if self.app.row_display_mode_usecase.is_editable(field_key, self.app.day_columns[day_index]):
                return self.set_selected_cell(field_key, day_index, ensure_visible=True)
        return False

    def set_edge_column_selection(self, *, to_end: bool, ensure_visible: bool = True) -> bool:
        """Setzt die Spaltenauswahl auf die erste oder letzte vorhandene Spalte."""
        if not self.app.day_columns:
            return False
        target = len(self.app.day_columns) - 1 if to_end else 0
        self.set_single_column_selection(target, ensure_visible=ensure_visible)
        return True

    def move_selection_to_adjacent(self, direction: int) -> bool:
        """Navigiert ohne Skip-Regeln zur direkten Nachbarspalte."""
        if direction not in (-1, 1):
            return False
        if not self.app.day_columns:
            return False
        selected = self.selected_indices_sorted()
        if selected:
            start_index = selected[-1] if direction > 0 else selected[0]
        else:
            start_index = self.app.overview_controller._next_lesson_column_index()
            if start_index is None:
                return False
        target = start_index + direction
        if not (0 <= target < len(self.app.day_columns)):
            return False
        self.set_single_column_selection(target, ensure_visible=True)
        return True

    def ensure_column_visible(self, day_index: int):
        """Scrollt die Grid-Ansicht so, dass die Zielspalte sicher im Sichtbereich liegt."""
        if not (0 <= day_index < len(self.app.day_columns)):
            return

        self.app.grid_canvas.update_idletasks()
        bbox = self.app.grid_canvas.bbox(self.app.grid_window)
        if bbox is None:
            return

        full_width = max(1, bbox[2] - bbox[0])
        viewport_width = max(1, int(self.app.grid_canvas.winfo_width()))
        x_positions = getattr(self.app, "day_column_x_positions", {})
        column_start = int(x_positions.get(day_index, day_index * self.app.day_column_width))
        column_end = column_start + self.app.day_column_width

        x_start, x_end = self.app.grid_canvas.xview()
        visible_start = x_start * full_width
        visible_end = x_end * full_width

        target_start = x_start
        if column_start < visible_start:
            target_start = column_start / float(full_width)
        elif column_end > visible_end:
            target_start = (column_end - viewport_width) / float(full_width)

        max_start = max(0.0, 1.0 - (viewport_width / float(full_width)))
        self.app.grid_canvas.xview_moveto(min(max(target_start, 0.0), max_start))

    def ensure_row_visible(self, field_key: str, day_index: int):
        """Scrollt vertikal so, dass die aktive Zelle im sichtbaren Grid-Bereich bleibt."""
        cell_widgets = getattr(self.app, "cell_widgets", {})
        cell_widget = cell_widgets.get((field_key, day_index))
        if cell_widget is None:
            return

        self.app.grid_canvas.update_idletasks()
        bbox = self.app.grid_canvas.bbox(self.app.grid_window)
        if bbox is None:
            return

        full_height = max(1, bbox[3] - bbox[1])
        viewport_height = max(1, int(self.app.grid_canvas.winfo_height()))

        row_start = int(cell_widget.winfo_y())
        row_height = max(1, int(cell_widget.winfo_height()))
        row_end = row_start + row_height

        y_start, y_end = self.app.viewport_sync.yview_range()
        visible_start = y_start * full_height
        visible_end = y_end * full_height

        target_start = y_start
        if row_start < visible_start:
            target_start = row_start / float(full_height)
        elif row_end > visible_end:
            target_start = (row_end - viewport_height) / float(full_height)

        self.app.viewport_sync.yview_moveto(target_start)

    def _is_occurring_column(self, day: dict[str, object]) -> bool:
        """Prüft, ob eine Spalte als stattfindende Einheit navigierbar ist."""
        return not bool(day.get("is_cancel", False))

    def move_selection_to_adjacent_occurring(self, direction: int) -> bool:
        """Navigiert mit +/-1 zur nächsten stattfindenden Einheit und fokussiert sie."""
        if direction not in (-1, 1):
            return False
        if not self.app.day_columns:
            return False

        selected = self.selected_indices_sorted()
        if selected:
            start_index = selected[-1] if direction > 0 else selected[0]
        else:
            start_index = self.app.overview_controller._next_lesson_column_index()
            if start_index is None:
                return False

        probe = start_index + direction
        while 0 <= probe < len(self.app.day_columns):
            if self._is_occurring_column(self.app.day_columns[probe]):
                self.set_single_column_selection(probe, ensure_visible=True)
                return True
            probe += direction
        return False

    def update_selected_column_label(self):
        """Aktualisiert die Statusanzeige der aktuell selektierten Spalte."""
        if len(self.app.selected_day_indices) != 1:
            self.app.selected_column_var.set("Ausgewählte Spalte: keine")
            return
        idx = next(iter(self.app.selected_day_indices))
        if not (0 <= idx < len(self.app.day_columns)):
            self.app.selected_column_var.set("Ausgewählte Spalte: keine")
            return
        datum = self._format_short_date(str(self.app.day_columns[idx].get("datum", "")).strip()) or "?"
        self.app.selected_column_var.set(f"Ausgewählte Spalte: {datum}")

    @staticmethod
    def _format_short_date(raw_date: str) -> str:
        """Formatiert Datumswerte als `Mi 18.02.` mit Fallback auf Rohtext."""
        text = str(raw_date).strip()
        if not text:
            return ""
        parsed = None
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y", "%d.%m.%Y", "%d.%m.%y"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            return text
        weekday_map = {0: "Mo", 1: "Di", 2: "Mi", 3: "Do", 4: "Fr", 5: "Sa", 6: "So"}
        weekday = weekday_map.get(parsed.weekday(), "")
        return f"{weekday} {parsed.day:02d}.{parsed.month:02d}.".strip()

    def refresh_header_styles(self):
        """Wendet selektions-/zustandsabhängige Header-Farben auf alle Spalten an."""
        theme = get_theme(self.app.theme_var.get())
        selected_bg = str(
            theme.get(
                "selection_bg",
                theme.get(
                    "accent",
                    theme.get("accent_hover", theme.get("accent_soft", theme.get("bg_panel", theme["bg_main"]))),
                ),
            )
        )
        selected_fg = str(theme.get("selection_fg", theme.get("fg_on_accent", theme.get("fg_primary", "#000000"))))
        for day_index, label in self.app.header_labels.items():
            if day_index >= len(self.app.day_columns):
                continue
            day = self.app.day_columns[day_index]
            is_selected = day_index in self.app.selected_day_indices
            is_cancel = bool(day.get("is_cancel"))
            is_unresolved_link = bool(day.get("is_unresolved_link"))
            is_hospitation = bool(day.get("is_hospitation"))
            is_lzk = bool(day.get("is_lzk"))
            if is_cancel:
                base_bg = str(
                    theme.get("column_ausfall_bg", theme.get("warning_soft", theme.get("border", theme["bg_main"])))
                )
            elif is_hospitation:
                base_bg = str(
                    theme.get(
                        "column_hospitation_bg",
                        theme.get(
                            "hospitation_soft", theme.get("accent_soft", theme.get("bg_panel", theme["bg_main"]))
                        ),
                    )
                )
            elif is_unresolved_link:
                base_bg = str(
                    theme.get("warning_soft", theme.get("accent_soft", theme.get("bg_panel", theme["bg_main"])))
                )
            elif is_lzk:
                base_bg = str(
                    theme.get(
                        "column_lzk_bg",
                        theme.get("success_soft", theme.get("accent_soft", theme.get("bg_panel", theme["bg_main"]))),
                    )
                )
            else:
                base_bg = str(theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"])))
            base_fg = str(theme.get("fg_muted") if is_cancel else theme.get("fg_primary"))
            if is_selected:
                label.configure(
                    bg=selected_bg,
                    fg=selected_fg,
                    borderwidth=2,
                    relief="raised",
                )
            else:
                label.configure(bg=base_bg, fg=base_fg, borderwidth=1, relief="solid")

    def selected_indices_sorted(self) -> list[int]:
        """Liefert gültige selektierte Spaltenindizes in stabiler Reihenfolge."""
        return sorted(idx for idx in self.app.selected_day_indices if 0 <= idx < len(self.app.day_columns))

    def collect_selected_or_warn(self) -> list[int]:
        """Gibt selektierte Indizes zurück oder zeigt einen Hinweis bei leerer Auswahl."""
        selected = self.selected_indices_sorted()
        if not selected:
            messagebox.showinfo("Keine Auswahl", "Bitte zuerst eine oder mehrere Spalten auswählen.", parent=self.app)
        return selected

    def get_single_selected_or_warn(self) -> int | None:
        """Liefert genau einen Selektionsindex oder zeigt einen UI-Hinweis."""
        selected = self.selected_indices_sorted()
        if len(selected) != 1:
            messagebox.showinfo(
                "Bitte genau eine Spalte auswählen",
                "Diese Aktion ist nur mit genau einer ausgewählten Spalte möglich.",
                parent=self.app,
            )
            return None
        return selected[0]
