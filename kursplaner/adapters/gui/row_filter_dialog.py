from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets

from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.core.usecases.row_display_mode_usecase import RowDisplayModeUseCase, RowFilterSettings

_MODE_COLUMN_HEADERS = {
    RowDisplayModeUseCase.MODE_UNTERRICHT: "U",
    RowDisplayModeUseCase.MODE_LZK: "L",
    RowDisplayModeUseCase.MODE_AUSFALL: "A",
    RowDisplayModeUseCase.MODE_HOSPITATION: "H",
}


class RowFilterDialog(ScrollablePopupWindow):
    """Modaler Dialog zum Konfigurieren der Zeilenfeld-Sichtbarkeit je Anzeige-Modus.

    Die Feldliste wird dynamisch aus ``RowDisplayModeUseCase.all_fields_ordered()``
    abgeleitet — keine eigene statische Tabelle. Pro Feld gibt es vier Checkboxen
    (Unterricht/LZK/Ausfall/Hospitation), mit denen sich die Sichtbarkeit je Modus
    frei wählen lässt — auch abweichend von der fest hinterlegten Standardzuordnung.
    """

    def __init__(
        self,
        master,
        *,
        current: RowFilterSettings,
        theme_key: str | None = None,
    ) -> None:
        """Initialisiert den Dialog und baut die UI auf.

        Args:
            master: Elternfenster für den modalen Dialog.
            current: Aktuell aktive ``RowFilterSettings``; Checkboxen werden
                daraus vorbelegt (fehlende Felder → Standard-Moduszugehörigkeit).
            theme_key: Optionaler Theme-Name; ``None`` übernimmt das Parent-Theme.
        """
        super().__init__(
            master,
            title="Zeilenfelder",
            geometry="620x580",
            minsize=(560, 400),
            theme_key=theme_key,
        )
        self.result: RowFilterSettings | None = None
        self._use_case = RowDisplayModeUseCase()
        self._mode_order = [mode_def.key for mode_def in self._use_case.available_modes()]
        self._vars: dict[tuple[str, str], ui.BooleanVar] = {}
        self._grid_widgets: dict[tuple[int, int], widgets.Checkbutton] = {}
        self._build_ui(current)
        self.apply_theme()
        self.after_idle(self._focus_first_toggle)

    def _build_ui(self, current: RowFilterSettings) -> None:
        """Baut das Formular mit Feldliste und je vier Modus-Checkboxen pro Feld auf."""
        fields = self._use_case.all_fields_ordered()

        frame = widgets.Frame(self.content, padding=14)
        frame.pack(fill="both", expand=True)

        widgets.Label(
            frame,
            text=(
                "Lege pro Zeilenfeld fest, in welchen Anzeige-Modi es angezeigt wird "
                "(U = Unterricht, L = LZK, A = Ausfall, H = Hospitation)."
            ),
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        grid = widgets.Frame(frame)
        grid.pack(fill="x", expand=False)
        grid.columnconfigure(0, weight=1)

        widgets.Label(grid, text="Zeilenfeld", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        for col_index, mode_key in enumerate(self._mode_order):
            widgets.Label(grid, text=_MODE_COLUMN_HEADERS[mode_key], font=("Segoe UI", 9, "bold")).grid(
                row=0, column=col_index + 1, sticky="w", padx=(16, 0)
            )

        grid_row = 1
        prev_default_modes: frozenset[str] | None = None

        for field_key, label, _default_modes_str in fields:
            default_modes = self._use_case.default_modes_for_field(field_key)

            if prev_default_modes is not None and default_modes != prev_default_modes:
                widgets.Separator(grid, orient="horizontal").grid(
                    row=grid_row, column=0, columnspan=len(self._mode_order) + 1, sticky="ew", pady=(4, 4)
                )
                grid_row += 1

            widgets.Label(grid, text=label).grid(row=grid_row, column=0, sticky="w", pady=(2, 0))

            active_modes = self._use_case.effective_modes_for_field(field_key, current)
            for col_index, mode_key in enumerate(self._mode_order):
                var = ui.BooleanVar(value=mode_key in active_modes)
                self._vars[(field_key, mode_key)] = var
                toggle = widgets.Checkbutton(grid, variable=var)
                toggle.grid(row=grid_row, column=col_index + 1, sticky="w", padx=(16, 0), pady=(2, 0))
                self._register_nav_widget(toggle, row=grid_row, col=col_index)

            prev_default_modes = default_modes
            grid_row += 1

        widgets.Separator(frame, orient="horizontal").pack(fill="x", pady=12)

        button_row = widgets.Frame(frame)
        button_row.pack(fill="x")
        widgets.Button(button_row, text="Übernehmen", command=self._accept).pack(side="right")
        widgets.Button(button_row, text="Abbrechen", command=self.destroy).pack(
            side="right", padx=(0, 8)
        )

    def _register_nav_widget(self, widget: widgets.Checkbutton, *, row: int, col: int) -> None:
        """Registriert eine Checkbox für Pfeiltasten-Navigation in beide Richtungen."""
        self._grid_widgets[(row, col)] = widget
        widget.bind("<Up>", lambda event, r=row, c=col: self._move_focus(event, r, c, -1, 0), add="+")
        widget.bind("<Down>", lambda event, r=row, c=col: self._move_focus(event, r, c, 1, 0), add="+")
        widget.bind("<Left>", lambda event, r=row, c=col: self._move_focus(event, r, c, 0, -1), add="+")
        widget.bind("<Right>", lambda event, r=row, c=col: self._move_focus(event, r, c, 0, 1), add="+")
        widget.bind("<space>", lambda _event, w=widget: self._toggle_widget(w), add="+")

    @staticmethod
    def _toggle_widget(widget: widgets.Checkbutton) -> str:
        """Schaltet den Zustand einer Checkbox um und stoppt Event-Weiterleitung."""
        widget.invoke()
        return "break"

    def _move_focus(self, _event, row: int, col: int, row_step: int, col_step: int) -> str:
        """Bewegt den Fokus zur nächsten registrierten Checkbox in der angegebenen Richtung."""
        rows = sorted({r for r, _c in self._grid_widgets})
        if row not in rows:
            return "break"
        if row_step:
            pos = rows.index(row)
            next_pos = pos + row_step
            if 0 <= next_pos < len(rows):
                target = self._grid_widgets.get((rows[next_pos], col))
                if target is not None:
                    target.focus_set()
        elif col_step:
            next_col = col + col_step
            if 0 <= next_col < len(self._mode_order):
                target = self._grid_widgets.get((row, next_col))
                if target is not None:
                    target.focus_set()
        return "break"

    def _focus_first_toggle(self) -> None:
        """Setzt den Fokus beim Öffnen auf die erste Checkbox."""
        if not self._grid_widgets:
            return
        first_row = min(r for r, _c in self._grid_widgets)
        first = self._grid_widgets.get((first_row, 0))
        if first is not None and first.winfo_exists():
            first.focus_set()

    def _accept(self) -> None:
        """Speichert das Ergebnis und schließt den Dialog."""
        fields = {field_key for field_key, _mode_key in self._vars}
        overrides: dict[str, frozenset[str]] = {}
        for field_key in fields:
            selected = frozenset(
                mode_key
                for mode_key in self._mode_order
                if self._vars[(field_key, mode_key)].get()
            )
            if selected != self._use_case.default_modes_for_field(field_key):
                overrides[field_key] = selected
        self.result = RowFilterSettings(field_mode_overrides=overrides)
        self.destroy()


def ask_row_filter(
    master,
    *,
    current: RowFilterSettings,
    theme_key: str | None = None,
) -> RowFilterSettings | None:
    """Öffnet den Zeilenfelder-Dialog modal und gibt bestätigte Settings zurück.

    Args:
        master: Elternfenster.
        current: Aktuell aktive ``RowFilterSettings``.
        theme_key: Optionaler Theme-Name.

    Returns:
        Die neuen ``RowFilterSettings`` wenn der Nutzer „Übernehmen" geklickt hat,
        sonst ``None``.
    """
    dialog = RowFilterDialog(master, current=current, theme_key=theme_key)
    dialog.wait_window()
    return dialog.result
