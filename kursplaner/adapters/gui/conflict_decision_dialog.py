from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import widgets

from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.core.ports.repositories import ConflictContext, ConflictKind, ConflictResolution


class ConflictDecisionDialog(ScrollablePopupWindow):
    """Modaler Entscheidungs-Dialog fuer Fehler/Konflikte waehrend eines Bulk-Vorgangs.

    Fehler ("Operation technisch nicht sicher moeglich") bieten Nochmal
    versuchen/Ueberspringen/Zurueckrollen; Warnungen ("Operation moeglich,
    aber Abweichung erkannt") zusaetzlich Trotzdem durchfuehren.
    """

    def __init__(self, master, *, context: ConflictContext, theme_key: str | None = None) -> None:
        """Baut den Dialog fuer den gegebenen Fehler-/Konfliktkontext auf."""
        super().__init__(
            master,
            title="Fehler" if context.kind is ConflictKind.ERROR else "Konflikt",
            geometry="480x260",
            minsize=(440, 220),
            theme_key=theme_key,
        )
        self.result: ConflictResolution = ConflictResolution.SKIP
        self._build_ui(context)
        self.apply_theme()

    def _build_ui(self, context: ConflictContext) -> None:
        container = widgets.Frame(self.content, padding=14)
        container.pack(fill="both", expand=True)

        widgets.Label(container, text=context.title, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        widgets.Label(container, text=context.message, wraplength=430, justify="left").pack(
            anchor="w", pady=(8, 14), fill="x"
        )

        button_row = widgets.Frame(container)
        button_row.pack(fill="x", side="bottom")

        widgets.Button(
            button_row, text="Nochmal versuchen", command=lambda: self._choose(ConflictResolution.RETRY)
        ).pack(side="left")
        widgets.Button(
            button_row, text="Überspringen", command=lambda: self._choose(ConflictResolution.SKIP)
        ).pack(side="left", padx=(8, 0))
        if context.kind is ConflictKind.WARNING:
            widgets.Button(
                button_row, text="Trotzdem durchführen", command=lambda: self._choose(ConflictResolution.PROCEED)
            ).pack(side="left", padx=(8, 0))
        widgets.Button(
            button_row,
            text="Gesamten Vorgang zurückrollen",
            command=lambda: self._choose(ConflictResolution.ROLLBACK),
        ).pack(side="right")

    def _choose(self, resolution: ConflictResolution) -> None:
        self.result = resolution
        self.destroy()


def ask_conflict_decision(master, *, context: ConflictContext, theme_key: str | None = None) -> ConflictResolution:
    """Öffnet den Entscheidungs-Dialog modal und liefert die getroffene Wahl."""
    dialog = ConflictDecisionDialog(master, context=context, theme_key=theme_key)
    dialog.wait_window()
    return dialog.result
