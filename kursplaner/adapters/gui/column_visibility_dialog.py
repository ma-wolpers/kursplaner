from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.core.usecases.column_visibility_projection_usecase import ColumnVisibilitySettings


@dataclass(frozen=True)
class ColumnVisibilityDialogResult:
    """Gibt die im Dialog bestätigten Sichtbarkeits-Einstellungen zurück."""

    settings: ColumnVisibilitySettings


class ColumnVisibilityDialog(ScrollablePopupWindow):
    """Modaler Dialog zum Verstecken und Andeuten von Spaltenarten."""

    _KINDS: tuple[tuple[str, str], ...] = (
        ("Unterricht", "unterricht"),
        ("LZK", "lzk"),
        ("Ausfall", "ausfall"),
        ("Hospitation", "hospitation"),
        ("Leere Spalte", "leer"),
    )

    def __init__(self, master, *, current: ColumnVisibilitySettings, theme_key: str | None = None):
        super().__init__(
            master,
            title="Spaltenarten",
            geometry="600x430",
            minsize=(560, 380),
            theme_key=theme_key,
        )
        self.result: ColumnVisibilityDialogResult | None = None

        self._hide_vars: dict[str, tk.BooleanVar] = {}
        self._hint_vars: dict[str, tk.BooleanVar] = {}
        self._grid_widgets: dict[tuple[int, int], ttk.Checkbutton] = {}

        self._build_ui(current)
        self.apply_theme()
        self.after_idle(self._focus_first_toggle)

    def _build_ui(self, current: ColumnVisibilitySettings) -> None:
        frame = ttk.Frame(self.content, padding=14)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text=(
                "Lege fest, welche Spaltenarten angezeigt werden.\n"
                "Für ausgeblendete Arten kann optional ein dünner Marker eingeblendet werden."
            ),
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        grid = ttk.Frame(frame)
        grid.pack(fill="x", expand=False)
        ttk.Label(grid, text="Spaltenart", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(grid, text="Verstecken", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w", padx=(20, 0))
        ttk.Label(grid, text="Marker anzeigen", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=2, sticky="w", padx=(20, 0)
        )

        for row_index, (label, key) in enumerate(self._KINDS, start=1):
            hide_var = tk.BooleanVar(value=bool(getattr(current, f"hide_{key}")))
            hint_var = tk.BooleanVar(value=bool(getattr(current, f"hint_{key}")))
            self._hide_vars[key] = hide_var
            self._hint_vars[key] = hint_var

            ttk.Label(grid, text=label).grid(row=row_index, column=0, sticky="w", pady=(4, 0))

            hide_toggle = ttk.Checkbutton(grid, variable=hide_var)
            hide_toggle.grid(row=row_index, column=1, sticky="w", padx=(20, 0), pady=(4, 0))
            self._register_nav_widget(hide_toggle, row=row_index, col=1)

            hint_toggle = ttk.Checkbutton(grid, variable=hint_var)
            hint_toggle.grid(row=row_index, column=2, sticky="w", padx=(20, 0), pady=(4, 0))
            self._register_nav_widget(hint_toggle, row=row_index, col=2)

            def _sync_hint_state(*_args, key_name: str = key):
                if not self._hide_vars[key_name].get():
                    self._hint_vars[key_name].set(False)

            hide_var.trace_add("write", _sync_hint_state)
            _sync_hint_state()

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=12)

        button_row = ttk.Frame(frame)
        button_row.pack(fill="x")
        ttk.Button(button_row, text="Übernehmen", command=self._accept).pack(side="right")
        ttk.Button(button_row, text="Abbrechen", command=self.destroy).pack(side="right", padx=(0, 8))

    def _register_nav_widget(self, widget: ttk.Checkbutton, *, row: int, col: int) -> None:
        self._grid_widgets[(row, col)] = widget
        widget.bind("<Up>", lambda event, r=row, c=col: self._move_focus(event, r, c, -1, 0), add="+")
        widget.bind("<Down>", lambda event, r=row, c=col: self._move_focus(event, r, c, 1, 0), add="+")
        widget.bind("<Left>", lambda event, r=row, c=col: self._move_focus(event, r, c, 0, -1), add="+")
        widget.bind("<Right>", lambda event, r=row, c=col: self._move_focus(event, r, c, 0, 1), add="+")
        widget.bind("<space>", lambda _event, w=widget: self._toggle_widget(w), add="+")

    @staticmethod
    def _toggle_widget(widget: ttk.Checkbutton) -> str:
        widget.invoke()
        return "break"

    def _move_focus(self, _event, row: int, col: int, d_row: int, d_col: int) -> str:
        next_row = row
        next_col = col

        while True:
            next_row += d_row
            next_col += d_col
            if next_row < 1 or next_row > len(self._KINDS):
                return "break"
            if next_col < 1 or next_col > 2:
                return "break"
            target = self._grid_widgets.get((next_row, next_col))
            if target is not None:
                target.focus_set()
                return "break"

    def _focus_first_toggle(self) -> None:
        first = self._grid_widgets.get((1, 1))
        if first is not None and first.winfo_exists():
            first.focus_set()

    def _accept(self) -> None:
        settings = ColumnVisibilitySettings(
            hide_unterricht=bool(self._hide_vars["unterricht"].get()),
            hide_lzk=bool(self._hide_vars["lzk"].get()),
            hide_ausfall=bool(self._hide_vars["ausfall"].get()),
            hide_hospitation=bool(self._hide_vars["hospitation"].get()),
            hide_leer=bool(self._hide_vars["leer"].get()),
            hint_unterricht=bool(self._hide_vars["unterricht"].get() and self._hint_vars["unterricht"].get()),
            hint_lzk=bool(self._hide_vars["lzk"].get() and self._hint_vars["lzk"].get()),
            hint_ausfall=bool(self._hide_vars["ausfall"].get() and self._hint_vars["ausfall"].get()),
            hint_hospitation=bool(self._hide_vars["hospitation"].get() and self._hint_vars["hospitation"].get()),
            hint_leer=bool(self._hide_vars["leer"].get() and self._hint_vars["leer"].get()),
        )
        self.result = ColumnVisibilityDialogResult(settings=settings)
        self.destroy()


def ask_column_visibility(
    master, *, current: ColumnVisibilitySettings, theme_key: str | None = None
) -> ColumnVisibilitySettings | None:
    """Öffnet den Spaltenarten-Dialog modal und gibt bestätigte Settings zurück."""
    dialog = ColumnVisibilityDialog(master, current=current, theme_key=theme_key)
    dialog.wait_window()
    if dialog.result is None:
        return None
    return dialog.result.settings
