from __future__ import annotations

from dataclasses import dataclass
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.contracts import EventResult
from bw_gui.runtime import WindowShortcutBinder, ui, widgets

from kursplaner.adapters.gui.local_keys import CTRL_ENTER, bind_keys
from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow


@dataclass(frozen=True)
class LzkColumnDialogResult:
    title_override: str


class LzkColumnDialog(ScrollablePopupWindow):
    """MVP popup for LZK confirmation from column shortcut."""

    def __init__(self, master, *, date_label: str, suggested_title: str, theme_key: str | None = None):
        super().__init__(
            master,
            title="LZK bestätigen",
            geometry="680x300",
            minsize=(560, 240),
            theme_key=theme_key,
        )
        self.result: LzkColumnDialogResult | None = None

        root = widgets.Frame(self.content, padding=16)
        root.pack(fill="both", expand=True)

        widgets.Label(root, text=f"Spalte: {date_label}", justify="left").pack(anchor="w")
        widgets.Label(
            root,
            text=(
                "Neues LZK-Fenster (MVP).\n"
                "Optional kann bereits ein Titel gesetzt werden.\n"
                "Strg+Enter übernimmt, Esc verwirft."
            ),
            justify="left",
        ).pack(anchor="w", pady=(8, 10))

        widgets.Label(root, text="Titel (optional)").pack(anchor="w")
        self.title_entry = widgets.Entry(root)
        self.title_entry.pack(fill="x", pady=(4, 0))

        hint = widgets.Label(root, text=f"Vorschlag: {suggested_title}", justify="left")
        hint.pack(anchor="w", pady=(6, 0))

        buttons = widgets.Frame(root)
        buttons.pack(fill="x", pady=(14, 0))
        widgets.Button(buttons, text="Übernehmen", command=self._accept).pack(side="left")
        widgets.Button(buttons, text="Abbrechen", command=self.destroy).pack(side="right")

        # Strg+Enter (auch Ziffernblock) uebernimmt -- im ganzen Dialog, auch im Titelfeld.
        bind_keys(WindowShortcutBinder(self), ((CTRL_ENTER, "accept", self._on_ctrl_enter_accept),), prefix="lzk_column")

        self.apply_theme()

    def _on_ctrl_enter_accept(self, _event=None) -> EventResult:
        self._accept()
        return EventResult.HANDLED

    def _accept(self):
        self.result = LzkColumnDialogResult(title_override=self.title_entry.get().strip())
        self.destroy()


def ask_lzk_column_dialog(
    parent,
    *,
    date_label: str,
    suggested_title: str,
    theme_key: str | None = None,
) -> LzkColumnDialogResult | None:
    dialog = LzkColumnDialog(
        master=parent,
        date_label=date_label,
        suggested_title=suggested_title,
        theme_key=theme_key,
    )
    dialog.grab_set()
    try:
        dialog.wait_visibility()
        dialog.lift()
        dialog.focus_force()
        dialog.title_entry.focus_set()
    except ui.TclError:
        pass
    dialog.wait_window()
    return dialog.result
