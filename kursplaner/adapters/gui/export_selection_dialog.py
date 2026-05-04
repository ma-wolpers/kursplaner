from __future__ import annotations

from dataclasses import dataclass
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets

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

        self.scope_current_sequence_var = ui.BooleanVar(value=True)
        self.layout_var = ui.StringVar(value="sequence_plan")
        self.output_format_var = ui.StringVar(value="pdf")
        self._initial_state = self._current_state()

        self._build_ui()
        self.apply_theme()

    def _build_ui(self) -> None:
        container = widgets.Frame(self.content, padding=14)
        container.pack(fill="both", expand=True)

        scope_frame = widgets.LabelFrame(container, text="Was")
        scope_frame.pack(fill="x", pady=(0, 10))
        widgets.Checkbutton(
            scope_frame,
            text="Aktuelle Sequenz",
            variable=self.scope_current_sequence_var,
            state="disabled",
        ).pack(anchor="w", padx=10, pady=8)

        layout_frame = widgets.LabelFrame(container, text="Wie")
        layout_frame.pack(fill="x", pady=(0, 10))
        widgets.Radiobutton(
            layout_frame,
            text="Sequenzplan",
            value="sequence_plan",
            variable=self.layout_var,
        ).pack(anchor="w", padx=10, pady=(8, 2))
        widgets.Radiobutton(
            layout_frame,
            text="Kompetenzhorizont",
            value="expected_horizon",
            variable=self.layout_var,
        ).pack(anchor="w", padx=10, pady=(0, 8))

        format_frame = widgets.LabelFrame(container, text="Als was")
        format_frame.pack(fill="x")
        widgets.Radiobutton(
            format_frame,
            text="PDF",
            value="pdf",
            variable=self.output_format_var,
        ).pack(anchor="w", padx=10, pady=(8, 2))
        widgets.Radiobutton(
            format_frame,
            text="Markdown",
            value="markdown",
            variable=self.output_format_var,
        ).pack(anchor="w", padx=10, pady=(0, 8))

        button_row = widgets.Frame(container)
        button_row.pack(fill="x", pady=(14, 0))
        widgets.Button(button_row, text="Abbrechen", command=self.destroy).pack(side="right")
        widgets.Button(button_row, text="Export starten", command=self._accept).pack(side="right", padx=(0, 8))

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
