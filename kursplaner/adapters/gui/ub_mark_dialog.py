from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from kursplaner.adapters.gui.dialog_services import messagebox
from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow


@dataclass(frozen=True)
class UbMarkDialogResult:
    """Rückgabedaten des UB-Markierungsdialogs."""

    ub_kinds: tuple[str, ...]
    langentwurf: bool
    beobachtungsschwerpunkt: str
    delete_requested: bool = False


class UbMarkDialog(ScrollablePopupWindow):
    """Popup zur Erfassung der UB-Grunddaten für eine Unterrichtseinheit."""

    def __init__(
        self,
        master,
        *,
        theme_key: str | None = None,
        initial_ub_kinds: tuple[str, ...] = ("Pädagogik",),
        initial_langentwurf: bool = False,
        initial_beobachtungsschwerpunkt: str = "",
        allow_delete: bool = False,
    ):
        super().__init__(
            master,
            title="Unterrichtsbesuch bearbeiten" if allow_delete else "Unterrichtsbesuch markieren",
            geometry="620x380",
            minsize=(540, 320),
            theme_key=theme_key,
        )
        self.result: UbMarkDialogResult | None = None
        self._allow_delete = bool(allow_delete)

        normalized_kinds = {str(item).strip() for item in initial_ub_kinds if str(item).strip()}
        if not normalized_kinds:
            normalized_kinds = {"Pädagogik"}

        self.kind_paedagogik = tk.BooleanVar(value=("Pädagogik" in normalized_kinds))
        self.kind_fach = tk.BooleanVar(value=("Fach" in normalized_kinds))
        self.langentwurf_var = tk.BooleanVar(value=bool(initial_langentwurf))
        self.beobachtung_var = tk.StringVar(value=str(initial_beobachtungsschwerpunkt or "").strip())
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
        if self._allow_delete:
            ttk.Button(button_row, text="UB löschen", command=self._delete).pack(side="left")

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
            delete_requested=False,
        )
        self.destroy()

    def _delete(self) -> None:
        """Bestätigt die explizite Löschaktion für eine bestehende UB-Verknüpfung."""
        if not self._allow_delete:
            return
        confirmed = messagebox.askyesno(
            "Unterrichtsbesuch löschen",
            "Soll der Unterrichtsbesuch entfernt werden?",
            parent=self,
        )
        if not confirmed:
            return
        self.result = UbMarkDialogResult(
            ub_kinds=tuple(),
            langentwurf=False,
            beobachtungsschwerpunkt="",
            delete_requested=True,
        )
        self.destroy()


def ask_mark_unit_as_ub(
    master,
    *,
    theme_key: str | None = None,
    initial_ub_kinds: tuple[str, ...] = ("Pädagogik",),
    initial_langentwurf: bool = False,
    initial_beobachtungsschwerpunkt: str = "",
    allow_delete: bool = False,
) -> UbMarkDialogResult | None:
    """Öffnet den UB-Dialog modal und liefert die Auswahl oder ``None``."""
    dialog = UbMarkDialog(
        master,
        theme_key=theme_key,
        initial_ub_kinds=initial_ub_kinds,
        initial_langentwurf=initial_langentwurf,
        initial_beobachtungsschwerpunkt=initial_beobachtungsschwerpunkt,
        allow_delete=allow_delete,
    )
    dialog.wait_window()
    return dialog.result
