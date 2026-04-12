from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow


@dataclass(frozen=True)
class ExportSelectionResult:
    """Rückgabewerte des Exportdialogs."""

    scope: str
    layout: str
    output_format: str


class ExportSelectionDialog(ScrollablePopupWindow):
    """Dialog zur Auswahl von Exportinhalt, Darstellung und Ausgabeformat."""

    def __init__(self, master, *, theme_key: str | None = None):
        super().__init__(
            master,
            title="Exportieren als...",
            geometry="520x360",
            minsize=(500, 320),
            theme_key=theme_key,
        )
        self.result: ExportSelectionResult | None = None

        self.scope_current_sequence_var = tk.BooleanVar(value=True)
        self.layout_var = tk.StringVar(value="sequence_plan")
        self.output_format_var = tk.StringVar(value="pdf")
        self._initial_state = self._current_state()

        self._build_ui()
        self.apply_theme()

    def _build_ui(self) -> None:
        container = ttk.Frame(self.content, padding=14)
        container.pack(fill="both", expand=True)

        scope_frame = ttk.LabelFrame(container, text="Was")
        scope_frame.pack(fill="x", pady=(0, 10))
        ttk.Checkbutton(
            scope_frame,
            text="Aktuelle Sequenz",
            variable=self.scope_current_sequence_var,
            state="disabled",
        ).pack(anchor="w", padx=10, pady=8)

        layout_frame = ttk.LabelFrame(container, text="Wie")
        layout_frame.pack(fill="x", pady=(0, 10))
        ttk.Radiobutton(
            layout_frame,
            text="Sequenzplan",
            value="sequence_plan",
            variable=self.layout_var,
        ).pack(anchor="w", padx=10, pady=(8, 2))
        ttk.Radiobutton(
            layout_frame,
            text="Kompetenzhorizont",
            value="expected_horizon",
            variable=self.layout_var,
        ).pack(anchor="w", padx=10, pady=(0, 8))

        format_frame = ttk.LabelFrame(container, text="Als was")
        format_frame.pack(fill="x")
        ttk.Radiobutton(
            format_frame,
            text="PDF",
            value="pdf",
            variable=self.output_format_var,
        ).pack(anchor="w", padx=10, pady=(8, 2))
        ttk.Radiobutton(
            format_frame,
            text="Markdown",
            value="markdown",
            variable=self.output_format_var,
        ).pack(anchor="w", padx=10, pady=(0, 8))

        button_row = ttk.Frame(container)
        button_row.pack(fill="x", pady=(14, 0))
        ttk.Button(button_row, text="Abbrechen", command=self.destroy).pack(side="right")
        ttk.Button(button_row, text="Export starten", command=self._accept).pack(side="right", padx=(0, 8))

    def _current_state(self) -> tuple[bool, str, str]:
        return (
            bool(self.scope_current_sequence_var.get()),
            self.layout_var.get().strip(),
            self.output_format_var.get().strip(),
        )

    def _requires_close_confirmation(self) -> bool:
        if self.result is not None:
            return False
        return self._current_state() != self._initial_state

    def _close_confirmation_title(self) -> str:
        return "Exportauswahl verwerfen?"

    def _close_confirmation_message(self) -> str:
        return "Die Exportauswahl wurde noch nicht übernommen. Wirklich schließen?"

    def _accept(self) -> None:
        self.result = ExportSelectionResult(
            scope="current_sequence",
            layout=self.layout_var.get().strip(),
            output_format=self.output_format_var.get().strip(),
        )
        self.destroy()


def ask_export_selection(master, *, theme_key: str | None = None) -> ExportSelectionResult | None:
    """Öffnet den Exportdialog modal und liefert die Auswahl oder ``None``."""
    dialog = ExportSelectionDialog(master, theme_key=theme_key)
    dialog.wait_window()
    return dialog.result
