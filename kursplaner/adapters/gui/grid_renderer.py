from __future__ import annotations

import tkinter as tk
from datetime import datetime
from pathlib import Path

from kursplaner.adapters.gui.help_catalog import LESSON_BUILDER_HELP
from kursplaner.adapters.gui.hover_tooltip import HoverTooltip
from kursplaner.adapters.gui.ui_intents import UiIntent
from kursplaner.adapters.gui.ui_theme import get_theme


class GridRenderer:
    """Render-Komponente für die tabellarische Planansicht.

    Verantwortet ausschließlich visuelle Aufbereitung und Grid-Interaktion,
    keine Persistenz- oder Fachentscheidungslogik.
    """

    def __init__(self, app):
        """Speichert die App-Referenz als Render- und Event-Kontext."""
        self.app = app
        self._field_help_tooltips: list[HoverTooltip] = []
        self._marker_widgets: list[tk.Canvas] = []
        self._marker_kinds_by_widget: dict[int, tuple[str, ...]] = {}
        self._marker_column_width = 12

    @staticmethod
    def _marker_color_for_kind(theme: dict[str, str], kind: str) -> str:
        """Liefert Markerfarbe passend zur ausgeblendeten Spaltenart."""
        normalized = str(kind).strip().lower()
        if normalized == "ausfall":
            return str(theme.get("column_ausfall_bg", theme.get("warning_soft", theme.get("border", "#999999"))))
        if normalized == "lzk":
            return str(
                theme.get(
                    "column_lzk_bg",
                    theme.get("success_soft", theme.get("accent_soft", theme.get("border", "#999999"))),
                )
            )
        if normalized == "hospitation":
            return str(
                theme.get(
                    "column_hospitation_bg",
                    theme.get("hospitation_soft", theme.get("accent_soft", theme.get("border", "#999999"))),
                )
            )
        return str(theme.get("panel_strong", theme.get("border", "#999999")))

    def _draw_marker_canvas(self, marker: tk.Canvas, kinds: tuple[str, ...], theme: dict[str, str]) -> None:
        """Zeichnet farbige Marker-Segmente je ausgeblendeter Spaltenart."""
        marker.delete("all")
        marker.configure(bg=str(theme.get("bg_panel", theme.get("bg_main", "#ffffff"))), highlightthickness=0)
        marker_width = max(1, int(marker.winfo_width()))
        marker_height = max(1, int(marker.winfo_height()))
        normalized = tuple(str(kind).strip() for kind in kinds if str(kind).strip())
        if not normalized:
            return

        segment_width = max(1, marker_width // len(normalized))
        x0 = 0
        for index, kind in enumerate(normalized):
            x1 = marker_width if index == (len(normalized) - 1) else min(marker_width, x0 + segment_width)
            marker.create_rectangle(
                x0,
                0,
                x1,
                marker_height,
                fill=self._marker_color_for_kind(theme, kind),
                outline="",
            )
            x0 = x1

    def _display_layout_items(self) -> list[dict[str, object]]:
        """Liefert die Darstellungsreihenfolge aus sichtbaren Tagen und Marker-Lücken."""
        items: list[dict[str, object]] = []
        for day_index, day in enumerate(self.app.day_columns):
            hidden_before = day.get("hidden_kinds_before", ()) if isinstance(day, dict) else ()
            if isinstance(hidden_before, (tuple, list)) and hidden_before:
                items.append({"type": "marker", "kinds": tuple(str(kind) for kind in hidden_before)})
            items.append({"type": "day", "day_index": day_index})
        return items

    def _field_help_text(self, field_key: str) -> str:
        if field_key == "Stundenziel":
            return LESSON_BUILDER_HELP.get("stundenziel", "")
        if field_key == "Teilziele":
            return LESSON_BUILDER_HELP.get("teilziele", "")
        return ""

    def _header_visual_state(self, day_index: int) -> tuple[str, str, str]:
        """Liefert Header-Text und Basisfarben für eine Tages-Spalte."""
        theme = get_theme(self.app.theme_var.get())
        if day_index >= len(self.app.day_columns):
            return "", theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"])), theme["fg_primary"]

        day = self.app.day_columns[day_index]
        is_cancel = bool(day.get("is_cancel"))
        is_unresolved_link = bool(day.get("is_unresolved_link"))
        is_lzk = bool(day.get("is_lzk"))
        is_hospitation = bool(day.get("is_hospitation"))
        date_text = self._format_header_date(str(day.get("datum", "")))
        if is_cancel:
            return (
                date_text,
                theme.get("column_ausfall_bg", theme.get("warning_soft", theme["border"])),
                theme["fg_muted"],
            )
        if is_hospitation:
            return (
                date_text,
                theme.get(
                    "column_hospitation_bg",
                    theme.get("hospitation_soft", theme.get("accent_soft", theme.get("bg_panel", theme["bg_main"]))),
                ),
                theme["fg_primary"],
            )
        if is_lzk:
            return (
                date_text,
                theme.get(
                    "column_lzk_bg",
                    theme.get("success_soft", theme.get("accent_soft", theme.get("bg_panel", theme["bg_main"]))),
                ),
                theme["fg_primary"],
            )
        if is_unresolved_link:
            return (
                f"{date_text} ⚠",
                theme.get("warning_soft", theme.get("accent_soft", theme.get("bg_panel", theme["bg_main"]))),
                theme["fg_primary"],
            )
        return (
            date_text,
            theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"])),
            theme["fg_primary"],
        )

    @staticmethod
    def _format_header_date(raw_date: str) -> str:
        """Formatiert Datumswerte als `Mi 18.02.`; bei Parsing-Fehlern bleibt der Originalwert."""
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

    def _row_index_for_field(self, field_key: str) -> int | None:
        """Liefert die Grid-Zeile für ein fachliches Feld."""
        label = self.app.row_labels.get(field_key)
        if label is None:
            return None
        info = label.grid_info()
        row_value = info.get("row")
        try:
            return int(row_value)
        except (TypeError, ValueError):
            return None

    def _visible_row_defs(self) -> list[tuple[str, str]]:
        """Liefert nur Zeilen, die mindestens in einer Spalte sichtbar sind."""
        visible: list[tuple[str, str]] = []
        for field_key, label_text in self.app.row_defs:
            if any(self._field_is_visible_for_day(field_key, day) for day in self.app.day_columns):
                visible.append((field_key, label_text))
        return visible

    def _grid_structure_matches_state(self) -> bool:
        """Prüft, ob vorhandene Widgets zur aktuellen fachlichen Sichtbarkeit passen."""
        if len(self.app.header_labels) != len(self.app.day_columns):
            return False

        expected_row_defs = self._visible_row_defs()
        expected_fields = [field_key for field_key, _ in expected_row_defs]
        actual_fields = list(self.app.row_labels.keys())
        if actual_fields != expected_fields:
            return False

        for field_key in expected_fields:
            for day_index, day in enumerate(self.app.day_columns):
                expected_visible = self._field_is_visible_for_day(field_key, day)
                actual_visible = (field_key, day_index) in self.app.cell_widgets
                if expected_visible != actual_visible:
                    return False

        return True

    def _row_layout(self, field_key: str) -> tuple[int, bool, bool, str]:
        """Berechnet Hoehe und Labeltext einer Feldzeile."""
        label_text = next((text for key, text in self.app.row_defs if key == field_key), field_key)
        row_values = [self.app._field_value(day, field_key) for day in self.app.day_columns]
        max_visual_lines = max([self.app._estimate_visual_lines(value) for value in row_values], default=1)
        expanded_height = max(2, max_visual_lines)
        collapsible = expanded_height > self.app.collapsed_row_lines
        expanded = bool(self.app.row_expanded.get(field_key, self.app.expand_long_rows_var.get()))
        self.app.row_expanded[field_key] = expanded

        row_height = expanded_height if expanded else self.app.collapsed_row_lines
        if collapsible:
            icon = "▾" if expanded else "▸"
            label_text = f"{icon} {label_text}"
        return row_height, collapsible, expanded, label_text

    @staticmethod
    def _is_linked_day(day: dict[str, object]) -> bool:
        """Prüft, ob eine Spalte auf eine existierende Einheitsdatei verlinkt ist."""
        link_obj = day.get("link") if isinstance(day, dict) else None
        return isinstance(link_obj, Path) and link_obj.exists() and link_obj.is_file()

    def _field_is_visible_for_day(self, field_key: str, day: dict[str, object]) -> bool:
        """Bestimmt, ob ein Feld für eine Spalte als Widget aufgebaut werden soll."""
        if not self._is_linked_day(day):
            return field_key in {"inhalt", "stunden"}
        return self.app.row_display_mode_usecase.field_is_relevant_for_day(field_key, day)

    def _apply_cell_state(
        self,
        widget: tk.Text,
        *,
        text: str,
        editable: bool,
        canceled: bool,
        unresolved_link: bool,
        row_height: int,
        is_lzk: bool,
        is_hospitation: bool,
        lzk_masked: bool,
        italic: bool,
    ) -> None:
        """Schreibt Inhalt/Stil einer existierenden Zelle ohne Widget-Neubau."""
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(height=max(self.app.collapsed_row_lines, row_height))
        if italic:
            widget.configure(font=("Consolas", self.app.preview_font_size, "italic"))
        else:
            widget.configure(font=self.app.preview_font)

        theme = get_theme(self.app.theme_var.get())
        if canceled:
            widget.configure(
                bg=theme.get("column_ausfall_bg", theme.get("warning_soft", theme.get("border", theme["bg_main"]))),
                fg=theme.get("fg_muted", theme["fg_primary"]),
                insertbackground=theme.get("fg_muted", theme["fg_primary"]),
                state="disabled",
            )
            return
        if unresolved_link:
            widget.configure(
                bg=theme.get("warning_soft", theme.get("accent_soft", theme.get("bg_panel", theme["bg_main"]))),
                fg=theme.get("fg_primary", theme["fg_primary"]),
                insertbackground=theme.get("fg_primary", theme["fg_primary"]),
            )
            return
        if lzk_masked:
            widget.configure(
                bg=theme.get(
                    "column_lzk_bg",
                    theme.get("success_soft", theme.get("accent_soft", theme.get("bg_panel", theme["bg_main"]))),
                ),
                fg=theme.get("fg_muted", theme["fg_primary"]),
                insertbackground=theme.get("fg_muted", theme["fg_primary"]),
                state="disabled",
            )
            return
        if is_hospitation:
            widget.configure(
                bg=theme.get(
                    "column_hospitation_bg",
                    theme.get("hospitation_soft", theme.get("accent_soft", theme.get("bg_panel", theme["bg_main"]))),
                ),
                fg=theme.get("fg_primary", theme["fg_primary"]),
                insertbackground=theme.get("fg_primary", theme["fg_primary"]),
            )
            return
        if is_lzk:
            widget.configure(
                bg=theme.get("column_lzk_bg", theme.get("success_soft", theme.get("accent_soft", theme["bg_surface"]))),
                fg=theme.get("fg_primary", theme["fg_primary"]),
                insertbackground=theme.get("fg_primary", theme["fg_primary"]),
            )
            return
        if editable:
            widget.configure(
                bg=theme["bg_surface"],
                fg=theme["fg_primary"],
                insertbackground=theme["fg_primary"],
            )
            return
        widget.configure(
            bg=theme.get("bg_panel", theme["bg_main"]),
            fg=theme.get("fg_muted", theme["fg_primary"]),
            insertbackground=theme.get("fg_muted", theme["fg_primary"]),
            state="disabled",
        )

    def _apply_cell_selection_style(self, widget: tk.Text, *, field_key: str, day_index: int) -> None:
        """Hebt die aktuell ausgewählte Navigationszelle sichtbar hervor."""
        selected = self.app.ui_state.selected_cell
        is_selected = selected is not None and selected.field_key == field_key and selected.day_index == day_index
        theme = get_theme(self.app.theme_var.get())
        if is_selected:
            highlight = str(theme.get("selection_bg", theme.get("accent", "#4A90E2")))
            widget.configure(
                borderwidth=2,
                highlightthickness=2,
                highlightbackground=highlight,
                highlightcolor=highlight,
                relief="solid",
            )
            return
        neutral = str(theme.get("border", theme.get("panel_strong", theme["bg_main"])))
        widget.configure(
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=neutral,
            highlightcolor=neutral,
            relief="solid",
        )

    def _create_text_cell(
        self,
        parent: tk.Widget,
        text: str,
        editable: bool,
        canceled: bool,
        unresolved_link: bool,
        height_lines: int,
        *,
        is_lzk: bool = False,
        is_hospitation: bool = False,
        lzk_masked: bool = False,
        italic: bool = False,
    ) -> tk.Text:
        """Erzeugt ein Text-Widget für eine Grid-Zelle mit zustandsabhängiger Darstellung."""
        width_chars = max(14, self.app.day_column_width // 9)
        cell_font = ("Consolas", self.app.preview_font_size, "italic") if italic else self.app.preview_font
        widget = tk.Text(
            parent,
            wrap="word",
            width=width_chars,
            height=max(self.app.collapsed_row_lines, height_lines),
            font=cell_font,
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=2,
            undo=True,
        )
        widget.insert("1.0", text)

        theme = get_theme(self.app.theme_var.get())
        if canceled:
            widget.configure(
                bg=theme.get("column_ausfall_bg", theme.get("warning_soft", theme.get("border", theme["bg_main"]))),
                fg=theme.get("fg_muted", theme["fg_primary"]),
                insertbackground=theme.get("fg_muted", theme["fg_primary"]),
                state="disabled",
            )
        elif unresolved_link:
            widget.configure(
                bg=theme.get("warning_soft", theme.get("accent_soft", theme.get("bg_panel", theme["bg_main"]))),
                fg=theme.get("fg_primary", theme["fg_primary"]),
                insertbackground=theme.get("fg_primary", theme["fg_primary"]),
            )
        elif lzk_masked:
            widget.configure(
                bg=theme.get(
                    "column_lzk_bg",
                    theme.get("success_soft", theme.get("accent_soft", theme.get("bg_panel", theme["bg_main"]))),
                ),
                fg=theme.get("fg_muted", theme["fg_primary"]),
                insertbackground=theme.get("fg_muted", theme["fg_primary"]),
                state="disabled",
            )
        elif is_hospitation:
            widget.configure(
                bg=theme.get(
                    "column_hospitation_bg",
                    theme.get("hospitation_soft", theme.get("accent_soft", theme.get("bg_panel", theme["bg_main"]))),
                ),
                fg=theme.get("fg_primary", theme["fg_primary"]),
                insertbackground=theme.get("fg_primary", theme["fg_primary"]),
            )
        elif is_lzk:
            widget.configure(
                bg=theme.get("column_lzk_bg", theme.get("success_soft", theme.get("accent_soft", theme["bg_surface"]))),
                fg=theme.get("fg_primary", theme["fg_primary"]),
                insertbackground=theme.get("fg_primary", theme["fg_primary"]),
            )
        elif editable:
            widget.configure(
                bg=theme["bg_surface"],
                fg=theme["fg_primary"],
                insertbackground=theme["fg_primary"],
            )
        else:
            widget.configure(
                bg=theme.get("bg_panel", theme["bg_main"]),
                fg=theme.get("fg_muted", theme["fg_primary"]),
                insertbackground=theme.get("fg_muted", theme["fg_primary"]),
                state="disabled",
            )

        widget.bind("<MouseWheel>", self.app._on_grid_mousewheel)
        self._apply_cell_selection_style(widget, field_key="", day_index=-1)
        return widget

    def _rebuild_grid(self):
        """Baut den gesamten Grid-Inhalt aus dem aktuellen UI-Zustand neu auf."""
        self.app._is_rebuilding_grid = True
        self._field_help_tooltips.clear()
        self.app.ui_state.clear_active_editor()
        self.app.cell_widgets = {}
        self.app.header_labels = {}
        self.app.row_labels = {}
        self.app.corner_label = None
        self._marker_widgets = []
        self._marker_kinds_by_widget = {}
        layout_items = self._display_layout_items()
        self.app.day_column_x_positions = {}
        row_pixel_heights: dict[int, int] = {}

        for child in self.app.fixed_inner.winfo_children():
            child.destroy()
        for child in self.app.fixed_header_frame.winfo_children():
            child.destroy()
        for child in self.app.header_inner.winfo_children():
            child.destroy()
        for child in self.app.grid_inner.winfo_children():
            child.destroy()

        theme = get_theme(self.app.theme_var.get())

        self.app.fixed_inner.grid_columnconfigure(0, weight=0, minsize=220)
        x_cursor = 0
        grid_col = 0
        day_grid_columns: dict[int, int] = {}
        for item in layout_items:
            if item.get("type") == "marker":
                self.app.header_inner.grid_columnconfigure(grid_col, weight=0, minsize=self._marker_column_width)
                self.app.grid_inner.grid_columnconfigure(grid_col, weight=0, minsize=self._marker_column_width)
                x_cursor += self._marker_column_width
                grid_col += 1
                continue
            day_index_obj = item.get("day_index", -1)
            day_index = day_index_obj if isinstance(day_index_obj, int) else -1
            if day_index < 0:
                continue
            self.app.header_inner.grid_columnconfigure(grid_col, weight=0, minsize=self.app.day_column_width)
            self.app.grid_inner.grid_columnconfigure(grid_col, weight=0, minsize=self.app.day_column_width)
            self.app.day_column_x_positions[day_index] = x_cursor
            day_grid_columns[day_index] = grid_col
            x_cursor += self.app.day_column_width
            grid_col += 1

        corner = tk.Label(
            self.app.fixed_header_frame,
            text="Datum",
            anchor="w",
            font=("Segoe UI", 9, "bold"),
            bg=theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"])),
            fg=theme["fg_primary"],
            padx=8,
            pady=6,
            relief="solid",
            borderwidth=1,
        )
        corner.pack(fill="both", expand=True)
        self.app.corner_label = corner

        for grid_col, item in enumerate(layout_items):
            if item.get("type") == "marker":
                kinds = item.get("kinds", ())
                kinds_tuple = tuple(str(kind) for kind in kinds) if isinstance(kinds, (tuple, list)) else ()
                marker = tk.Canvas(
                    self.app.header_inner,
                    width=self._marker_column_width,
                    height=1,
                    highlightthickness=0,
                    borderwidth=0,
                )
                marker.grid(row=0, column=grid_col, sticky="nsew")
                marker.bind(
                    "<Configure>",
                    lambda _event, widget=marker, mk=kinds_tuple: self._draw_marker_canvas(widget, mk, theme),
                )
                self._marker_kinds_by_widget[int(marker.winfo_id())] = kinds_tuple
                self._draw_marker_canvas(marker, kinds_tuple, theme)
                self._marker_widgets.append(marker)
                continue

            day_index_obj = item.get("day_index", -1)
            day_index = day_index_obj if isinstance(day_index_obj, int) else -1
            if day_index < 0:
                continue
            header_text, header_bg, header_fg = self._header_visual_state(day_index)

            header = tk.Label(
                self.app.header_inner,
                text=header_text,
                anchor="center",
                font=("Segoe UI", 9, "bold"),
                bg=header_bg,
                fg=header_fg,
                padx=6,
                pady=6,
                relief="solid",
                borderwidth=1,
            )
            header.grid(row=0, column=grid_col, sticky="nsew")
            header.bind(
                "<Button-1>",
                lambda _e, di=day_index: self.app._handle_ui_intent(UiIntent.GRID_COLUMN_CLICK, day_index=di),
            )
            self.app.header_labels[day_index] = header

        row_idx = 0
        for field_key, label_text in self._visible_row_defs():
            row_values = [self.app._field_value(day, field_key) for day in self.app.day_columns]
            row_height, collapsible, _expanded, field_label_text = self._row_layout(field_key)

            field_label = tk.Label(
                self.app.fixed_inner,
                text=field_label_text,
                anchor="w",
                justify="left",
                font=("Segoe UI", 9, "bold"),
                bg=theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"])),
                fg=theme["fg_primary"],
                padx=8,
                pady=3,
                relief="solid",
                borderwidth=1,
                cursor="hand2" if collapsible else "",
            )
            field_label.grid(row=row_idx, column=0, sticky="nsew")
            if collapsible:
                field_label.bind(
                    "<Button-1>",
                    lambda _e, fk=field_key: self.app._handle_ui_intent(UiIntent.GRID_TOGGLE_ROW_EXPAND, field_key=fk),
                )
            self.app.row_labels[field_key] = field_label
            help_text = self._field_help_text(field_key)
            if help_text:
                self._field_help_tooltips.append(HoverTooltip(field_label, help_text))
            row_pixel_heights[row_idx] = max(row_pixel_heights.get(row_idx, 0), int(field_label.winfo_reqheight()))

            for day_index, day in enumerate(self.app.day_columns):
                if not self._field_is_visible_for_day(field_key, day):
                    continue
                is_cancel = bool(day.get("is_cancel", False))
                is_unresolved_link = bool(day.get("is_unresolved_link", False))
                is_lzk = bool(day.get("is_lzk", False))
                is_hospitation = bool(day.get("is_hospitation", False))
                editable = self.app.row_display_mode_usecase.is_editable(field_key, day)
                canceled_visual = is_cancel and field_key != "Vertretungsmaterial"

                value = row_values[day_index] if day_index < len(row_values) else ""
                cell = self._create_text_cell(
                    self.app.grid_inner,
                    value,
                    editable=editable,
                    canceled=canceled_visual,
                    unresolved_link=is_unresolved_link,
                    height_lines=row_height,
                    is_lzk=is_lzk,
                    is_hospitation=is_hospitation,
                    lzk_masked=False,
                    italic=(field_key == "Kompetenzhorizont" and is_lzk),
                )
                grid_column = day_grid_columns.get(day_index, day_index)
                cell.grid(row=row_idx, column=grid_column, sticky="nsew")
                self._apply_cell_selection_style(cell, field_key=field_key, day_index=day_index)
                if help_text:
                    self._field_help_tooltips.append(HoverTooltip(cell, help_text))

                if editable:
                    cell.bind(
                        "<Button-1>",
                        lambda _event, fk=field_key, di=day_index: self.app._handle_ui_intent(
                            UiIntent.GRID_CELL_CLICK,
                            field_key=fk,
                            day_index=di,
                        ),
                    )
                    cell.bind(
                        "<FocusIn>",
                        lambda _event, fk=field_key, di=day_index: self.app._handle_ui_intent(
                            UiIntent.GRID_EDITOR_FOCUS_IN,
                            field_key=fk,
                            day_index=di,
                        ),
                    )
                    cell.bind(
                        "<FocusOut>",
                        lambda _event, fk=field_key, di=day_index: self.app._handle_ui_intent(
                            UiIntent.GRID_COMMIT_CELL,
                            field_key=fk,
                            day_index=di,
                        ),
                    )
                    cell.bind(
                        "<FocusOut>",
                        lambda _event, fk=field_key, di=day_index: self.app._handle_ui_intent(
                            UiIntent.GRID_EDITOR_FOCUS_OUT,
                            field_key=fk,
                            day_index=di,
                        ),
                        add="+",
                    )
                else:
                    cell.bind(
                        "<Button-1>",
                        lambda _event, di=day_index: self.app._handle_ui_intent(
                            UiIntent.GRID_DATE_CELL_CLICK,
                            day_index=di,
                        ),
                    )

                self.app.cell_widgets[(field_key, day_index)] = cell
                row_pixel_heights[row_idx] = max(row_pixel_heights.get(row_idx, 0), int(cell.winfo_reqheight()))

            row_idx += 1

        for row_idx, pixel_height in row_pixel_heights.items():
            if pixel_height <= 0:
                continue
            self.app.fixed_inner.grid_rowconfigure(row_idx, minsize=pixel_height)
            self.app.grid_inner.grid_rowconfigure(row_idx, minsize=pixel_height)

        self.app._is_rebuilding_grid = False
        selected = self.app.ui_state.selected_cell
        if selected is not None and (selected.field_key, selected.day_index) not in self.app.cell_widgets:
            self.app.ui_state.clear_selected_cell()
            if self.app.ui_state.selection_level == self.app.ui_state.SELECTION_LEVEL_CELL:
                self.app.ui_state.set_selection_level(self.app.ui_state.SELECTION_LEVEL_COLUMN)
        self.app._refresh_header_styles()
        self.app._on_grid_inner_configure()
        self.app.action_controller.update_action_controls()

    def update_header(self, day_index: int):
        """Aktualisiert Text/Basisfarbe eines existierenden Tages-Headers."""
        label = self.app.header_labels.get(day_index)
        if label is None:
            return
        text, bg, fg = self._header_visual_state(day_index)
        label.configure(text=text, bg=bg, fg=fg)

    def update_cell(self, field_key: str, day_index: int, *, sync_row_style: bool = True):
        """Aktualisiert eine einzelne Grid-Zelle im bestehenden Widget-Baum."""
        cell = self.app.cell_widgets.get((field_key, day_index))
        if cell is None or day_index >= len(self.app.day_columns):
            return

        row_height, _collapsible, _expanded, _label_text = self._row_layout(field_key)
        day = self.app.day_columns[day_index]
        editable = self.app.row_display_mode_usecase.is_editable(field_key, day)
        canceled_visual = bool(day.get("is_cancel", False)) and field_key != "Vertretungsmaterial"
        value = self.app._field_value(day, field_key)
        self._apply_cell_state(
            cell,
            text=value,
            editable=editable,
            canceled=canceled_visual,
            unresolved_link=bool(day.get("is_unresolved_link", False)),
            row_height=row_height,
            is_lzk=bool(day.get("is_lzk", False)),
            is_hospitation=bool(day.get("is_hospitation", False)),
            lzk_masked=False,
            italic=(field_key == "Kompetenzhorizont" and bool(day.get("is_lzk", False))),
        )
        self._apply_cell_selection_style(cell, field_key=field_key, day_index=day_index)
        if sync_row_style:
            self.update_row_style(field_key)

    def update_row_style(self, field_key: str):
        """Aktualisiert Label, Hoehe und Zellstile einer Feldzeile."""
        row_idx = self._row_index_for_field(field_key)
        if row_idx is None:
            return
        label = self.app.row_labels.get(field_key)
        if label is None:
            return

        theme = get_theme(self.app.theme_var.get())
        row_height, collapsible, _expanded, label_text = self._row_layout(field_key)
        label.configure(
            text=label_text,
            cursor="hand2" if collapsible else "",
            bg=theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"])),
            fg=theme["fg_primary"],
        )
        if collapsible:
            label.bind(
                "<Button-1>",
                lambda _e, fk=field_key: self.app._handle_ui_intent(UiIntent.GRID_TOGGLE_ROW_EXPAND, field_key=fk),
            )
        else:
            label.unbind("<Button-1>")

        self.app.fixed_inner.grid_rowconfigure(row_idx, minsize=0)
        self.app.grid_inner.grid_rowconfigure(row_idx, minsize=0)
        max_height = int(label.winfo_reqheight())
        for day_index in range(len(self.app.day_columns)):
            cell = self.app.cell_widgets.get((field_key, day_index))
            if cell is None:
                continue
            self.update_cell(field_key, day_index, sync_row_style=False)
            max_height = max(max_height, int(cell.winfo_reqheight()))

        self.app.fixed_inner.grid_rowconfigure(row_idx, minsize=max_height)
        self.app.grid_inner.grid_rowconfigure(row_idx, minsize=max_height)

    def update_column(self, day_index: int):
        """Aktualisiert Header und alle Feldzellen einer Tages-Spalte."""
        self.update_header(day_index)
        for field_key, _label in self.app.row_defs:
            self.update_row_style(field_key)
        self.app._refresh_header_styles()
        self.app._on_grid_inner_configure()

    def refresh_grid_content(self):
        """Aktualisiert den kompletten Grid-Inhalt ohne Widget-Neuaufbau."""
        if self.app._is_rebuilding_grid:
            return
        if not self.app.header_labels or not self.app.cell_widgets:
            self._rebuild_grid()
            return
        if not self._grid_structure_matches_state():
            self._rebuild_grid()
            return

        for day_index in range(len(self.app.day_columns)):
            self.update_header(day_index)
        for field_key, _label in self.app.row_defs:
            self.update_row_style(field_key)
        self.app._refresh_header_styles()
        self.app._on_grid_inner_configure()
        self.app.action_controller.update_action_controls()

    def _apply_grid_theme(self):
        """Wendet Theme-Änderungen per Patch-Update auf das bestehende Grid an."""
        if self.app._is_rebuilding_grid:
            return
        theme = get_theme(self.app.theme_var.get())
        if self.app.corner_label is not None:
            self.app.corner_label.configure(
                bg=theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"])),
                fg=theme["fg_primary"],
            )
        for widget in self._marker_widgets:
            widget.configure(bg=str(theme.get("bg_panel", theme.get("bg_main", "#ffffff"))))
            marker_kinds = self._marker_kinds_by_widget.get(int(widget.winfo_id()), ())
            self._draw_marker_canvas(widget, marker_kinds, theme)
        self.refresh_grid_content()

    def _on_grid_inner_configure(self, _event=None):
        """Synchronisiert die Scrollregion mit der aktuellen Grid-Größe."""
        self.app.header_canvas.configure(scrollregion=self.app.header_canvas.bbox("all"))
        self.app.fixed_canvas.configure(scrollregion=self.app.fixed_canvas.bbox("all"))
        self.app.grid_canvas.configure(scrollregion=self.app.grid_canvas.bbox("all"))

        header_canvas_width = max(1, self.app.header_canvas.winfo_width())
        header_canvas_height = max(1, self.app.header_canvas.winfo_height())
        fixed_canvas_height = max(1, self.app.fixed_canvas.winfo_height())
        grid_canvas_height = max(1, self.app.grid_canvas.winfo_height())

        self.app.header_canvas.itemconfigure(
            self.app.header_window,
            width=max(header_canvas_width, self.app.header_inner.winfo_reqwidth()),
            height=max(header_canvas_height, self.app.header_inner.winfo_reqheight()),
        )
        header_row_height = max(
            self.app.header_inner.winfo_reqheight(),
            int(self.app.corner_label.winfo_reqheight()) if self.app.corner_label else 0,
        )
        if header_row_height > 0:
            self.app.header_canvas.configure(height=header_row_height)
            self.app.fixed_header_frame.configure(height=header_row_height)

        self.app.fixed_canvas.itemconfigure(
            self.app.fixed_window,
            width=220,
            height=max(fixed_canvas_height, self.app.fixed_inner.winfo_reqheight()),
        )
        self.app.grid_canvas.itemconfigure(
            self.app.grid_window,
            height=max(grid_canvas_height, self.app.grid_inner.winfo_reqheight()),
        )
        self.app.viewport_sync.clamp_current_view()

    def _on_canvas_configure(self, _event=None):
        """Hält die Grid-Fensterhöhe bei Canvas-Resize konsistent."""
        self.app.header_canvas.itemconfigure(
            self.app.header_window,
            width=max(self.app.header_canvas.winfo_width(), self.app.header_inner.winfo_reqwidth()),
            height=max(self.app.header_canvas.winfo_height(), self.app.header_inner.winfo_reqheight()),
        )
        self.app.fixed_canvas.itemconfigure(
            self.app.fixed_window,
            width=220,
            height=max(self.app.fixed_canvas.winfo_height(), self.app.fixed_inner.winfo_reqheight()),
        )
        self.app.grid_canvas.itemconfigure(
            self.app.grid_window,
            height=max(self.app.grid_canvas.winfo_height(), self.app.grid_inner.winfo_reqheight()),
        )
        self._on_grid_inner_configure()

    def _on_vertical_scroll(self, *args):
        """Scrollt fixe und inhaltliche Grid-Spalte synchron in Y-Richtung."""
        self.app.viewport_sync.yview(*args)

    def _on_horizontal_scroll(self, *args):
        """Scrollt Kopfzeile und Grid-Inhalt synchron in X-Richtung."""
        self.app.header_canvas.xview(*args)
        self.app.grid_canvas.xview(*args)

    def _on_grid_mousewheel(self, event):
        """Behandelt Scroll- und Zoom-Interaktion im Grid (Ctrl+Wheel = Spaltenbreite)."""
        ctrl_pressed = bool(event.state & 0x0004)
        shift_pressed = bool(event.state & 0x0001)

        if ctrl_pressed:
            step = 20 if event.delta > 0 else -20
            self.app.day_column_width = max(
                self.app.min_day_column_width,
                min(self.app.max_day_column_width, self.app.day_column_width + step),
            )
            self._rebuild_grid()
            return "break"

        units = -1 if event.delta > 0 else 1
        if shift_pressed:
            self._on_horizontal_scroll("scroll", units, "units")
        else:
            self.app.viewport_sync.yview_scroll(units, "units")
        return "break"
