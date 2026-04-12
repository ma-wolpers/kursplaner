from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk

from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow


@dataclass(frozen=True)
class UbMarkDialogResult:
    """Rückgabedaten des UB-Markierungsdialogs."""

    ub_kinds: tuple[str, ...]
    langentwurf: bool
    beobachtungsschwerpunkt: str


class UbMarkDialog(ScrollablePopupWindow):
    """Popup zur Erfassung der UB-Grunddaten für eine Unterrichtseinheit."""

    def __init__(self, master, *, theme_key: str | None = None):
        super().__init__(
            master,
            title="Unterrichtsbesuch markieren",
            geometry="620x380",
            minsize=(540, 320),
            theme_key=theme_key,
        )
        self.result: UbMarkDialogResult | None = None

        self.kind_paedagogik = tk.BooleanVar(value=True)
        self.kind_fach = tk.BooleanVar(value=False)
        self.langentwurf_var = tk.BooleanVar(value=False)
        self.beobachtung_var = tk.StringVar(value="")
        self._initial_state = self._current_state()

        self._build_ui()
        self.apply_theme()

    def _build_ui(self) -> None:
        container = ttk.Frame(self.content, padding=14)
        container.pack(fill="both", expand=True)

        ttk.Label(
            container,
            text="Welche Art von Unterrichtsbesuch ist das?",
        ).pack(anchor="w")

        kind_frame = ttk.Frame(container)
        kind_frame.pack(fill="x", pady=(4, 10))
        ttk.Checkbutton(kind_frame, text="Pädagogik", variable=self.kind_paedagogik).pack(anchor="w")
        ttk.Checkbutton(kind_frame, text="Fach", variable=self.kind_fach).pack(anchor="w")

        ttk.Checkbutton(
            container,
            text="Langentwurf",
            variable=self.langentwurf_var,
        ).pack(anchor="w", pady=(0, 10))

        ttk.Label(container, text="Beobachtungsschwerpunkt").pack(anchor="w")
        focus_entry = ttk.Entry(container, textvariable=self.beobachtung_var)
        focus_entry.pack(fill="x", pady=(4, 12))

        button_row = ttk.Frame(container)
        button_row.pack(fill="x", pady=(6, 0))
        ttk.Button(button_row, text="Abbrechen", command=self.destroy).pack(side="right")
        ttk.Button(button_row, text="Übernehmen", command=self._accept).pack(side="right", padx=(0, 8))

        self.after_idle(focus_entry.focus_set)

    def _current_state(self) -> tuple[bool, bool, bool, str]:
        return (
            bool(self.kind_paedagogik.get()),
            bool(self.kind_fach.get()),
            bool(self.langentwurf_var.get()),
            self.beobachtung_var.get().strip(),
        )

    def _requires_close_confirmation(self) -> bool:
        if self.result is not None:
            return False
        return self._current_state() != self._initial_state

    def _close_confirmation_title(self) -> str:
        return "UB-Markierung verwerfen?"

    def _close_confirmation_message(self) -> str:
        return "Die Eingaben zur UB-Markierung wurden noch nicht übernommen. Wirklich schließen?"

    def _accept(self) -> None:
        kinds: list[str] = []
        if self.kind_paedagogik.get():
            kinds.append("Pädagogik")
        if self.kind_fach.get():
            kinds.append("Fach")

        if not kinds:
            messagebox.showerror(
                "Unterrichtsbesuch markieren",
                "Bitte mindestens eine UB-Art auswählen.",
                parent=self,
            )
            return

        self.result = UbMarkDialogResult(
            ub_kinds=tuple(kinds),
            langentwurf=bool(self.langentwurf_var.get()),
            beobachtungsschwerpunkt=self.beobachtung_var.get().strip(),
        )
        self.destroy()


def ask_mark_unit_as_ub(master, *, theme_key: str | None = None) -> UbMarkDialogResult | None:
    """Öffnet den UB-Dialog modal und liefert die Auswahl oder ``None``."""
    dialog = UbMarkDialog(master, theme_key=theme_key)
    dialog.wait_window()
    return dialog.result
