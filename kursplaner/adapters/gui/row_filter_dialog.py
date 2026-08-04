from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets

from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.core.usecases.row_display_mode_usecase import RowDisplayModeUseCase, RowFilterSettings

_ALL_MODES: frozenset[str] = frozenset({"U", "L", "A", "H"})


class RowFilterDialog(ScrollablePopupWindow):
    """Modaler Dialog zum Ein-/Ausblenden von Zeilenfeldern in Einheitskarten.

    Die Feldliste wird dynamisch aus ``RowDisplayModeUseCase.all_fields_ordered()``
    abgeleitet — keine eigene statische Tabelle.  Visuelle Trenner gliedern
    COMMON-Felder (alle Modi) von typspezifischen Feldern und trennen
    Feldgruppen ohne Modus-Überlappung voneinander.
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
                daraus vorbelegt (versteckte Felder = nicht angehakt).
            theme_key: Optionaler Theme-Name; ``None`` übernimmt das Parent-Theme.
        """
        super().__init__(
            master,
            title="Zeilenfelder",
            geometry="540x560",
            minsize=(480, 400),
            theme_key=theme_key,
        )
        self.result: RowFilterSettings | None = None
        self._vars: dict[str, ui.BooleanVar] = {}
        self._grid_widgets: dict[tuple[int, int], widgets.Checkbutton] = {}
        self._build_ui(current)
        self.apply_theme()
        self.after_idle(self._focus_first_toggle)

    def _build_ui(self, current: RowFilterSettings) -> None:
        """Baut das Formular mit Feldliste, Modi-Spalte und Anzeigen-Checkboxen auf."""
        use_case = RowDisplayModeUseCase()
        fields = use_case.all_fields_ordered()

        frame = widgets.Frame(self.content, padding=14)
        frame.pack(fill="both", expand=True)

        widgets.Label(
            frame,
            text="Lege fest, welche Zeilenfelder in den Einheitskarten angezeigt werden.",
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        grid = widgets.Frame(frame)
        grid.pack(fill="x", expand=False)
        grid.columnconfigure(0, weight=1)

        widgets.Label(grid, text="Zeilenfeld", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        widgets.Label(grid, text="Modi", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=1, sticky="w", padx=(16, 0)
        )
        widgets.Label(grid, text="Anzeigen", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=2, sticky="w", padx=(16, 0)
        )

        grid_row = 1
        prev_modes: frozenset[str] | None = None

        for field_key, label, modes_str in fields:
            cur_modes = frozenset(modes_str.split())

            if prev_modes is not None:
                out_of_common = prev_modes == _ALL_MODES and cur_modes != _ALL_MODES
                new_group = (
                    cur_modes != _ALL_MODES
                    and prev_modes != _ALL_MODES
                    and not (cur_modes & prev_modes)
                )
                if out_of_common or new_group:
                    widgets.Separator(grid, orient="horizontal").grid(
                        row=grid_row, column=0, columnspan=3, sticky="ew", pady=(4, 4)
                    )
                    grid_row += 1

            var = ui.BooleanVar(value=field_key not in current.hidden_fields)
            self._vars[field_key] = var

            widgets.Label(grid, text=label).grid(
                row=grid_row, column=0, sticky="w", pady=(2, 0)
            )
            widgets.Label(grid, text=modes_str).grid(
                row=grid_row, column=1, sticky="w", padx=(16, 0), pady=(2, 0)
            )

            toggle = widgets.Checkbutton(grid, variable=var)
            toggle.grid(row=grid_row, column=2, sticky="w", padx=(16, 0), pady=(2, 0))
            self._register_nav_widget(toggle, row=grid_row)

            prev_modes = cur_modes
            grid_row += 1

        widgets.Separator(frame, orient="horizontal").pack(fill="x", pady=12)

        button_row = widgets.Frame(frame)
        button_row.pack(fill="x")
        widgets.Button(button_row, text="Übernehmen", command=self._accept).pack(side="right")
        widgets.Button(button_row, text="Abbrechen", command=self.destroy).pack(
            side="right", padx=(0, 8)
        )

    def _register_nav_widget(self, widget: widgets.Checkbutton, *, row: int) -> None:
        """Registriert eine Checkbox für Up/Down-Tastaturnavigation.

        Separatoren werden nicht registriert und damit automatisch übersprungen.
        """
        self._grid_widgets[(row, 1)] = widget
        widget.bind("<Up>", lambda event, r=row: self._move_focus(event, r, -1), add="+")
        widget.bind("<Down>", lambda event, r=row: self._move_focus(event, r, 1), add="+")
        widget.bind("<space>", lambda _event, w=widget: self._toggle_widget(w), add="+")

    @staticmethod
    def _toggle_widget(widget: widgets.Checkbutton) -> str:
        """Schaltet den Zustand einer Checkbox um und stoppt Event-Weiterleitung."""
        widget.invoke()
        return "break"

    def _move_focus(self, _event, row: int, direction: int) -> str:
        """Bewegt den Fokus zur nächsten registrierten Checkbox in der angegebenen Richtung."""
        rows = sorted(r for r, _c in self._grid_widgets)
        if row not in rows:
            return "break"
        pos = rows.index(row)
        next_pos = pos + direction
        if 0 <= next_pos < len(rows):
            target = self._grid_widgets.get((rows[next_pos], 1))
            if target is not None:
                target.focus_set()
        return "break"

    def _focus_first_toggle(self) -> None:
        """Setzt den Fokus beim Öffnen auf die erste Checkbox."""
        if not self._grid_widgets:
            return
        first_row = min(r for r, _c in self._grid_widgets)
        first = self._grid_widgets.get((first_row, 1))
        if first is not None and first.winfo_exists():
            first.focus_set()

    def _accept(self) -> None:
        """Speichert das Ergebnis und schließt den Dialog."""
        hidden = frozenset(k for k, v in self._vars.items() if not v.get())
        self.result = RowFilterSettings(hidden_fields=hidden)
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
