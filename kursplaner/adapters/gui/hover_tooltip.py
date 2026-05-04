from __future__ import annotations

import tkinter as tk


class HoverTooltip:
    """Einfache Hover-Hilfe für Tk-Widgets."""

    _active_owner: "HoverTooltip | None" = None

    def __init__(self, widget: tk.Widget, text: str):
        self.widget = widget
        self.text = text.strip()
        self._tip: tk.Toplevel | None = None
        self._widgets: list[tk.Widget] = []

        if not self.text:
            return

        self.bind_widget(widget)

    def bind_widget(self, widget: tk.Widget):
        """Registriert zusätzliche Widget-Zonen für denselben Tooltip."""
        if widget in self._widgets:
            return
        self._widgets.append(widget)
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _show(self, _event=None):
        if self._tip is not None:
            return

        active = HoverTooltip._active_owner
        if active is not None and active is not self:
            active._hide()

        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8

        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            tip,
            text=self.text,
            justify="left",
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=5,
            wraplength=420,
            bg="#FFFFE1",
            fg="#222222",
        )
        label.pack()
        self._tip = tip
        HoverTooltip._active_owner = self

    def _hide(self, _event=None):
        if self._tip is None:
            return
        self._tip.destroy()
        self._tip = None
        if HoverTooltip._active_owner is self:
            HoverTooltip._active_owner = None


# Pilot bridge: use shared tooltip implementation via stable local import path.
try:
    from bw_libs.shared_gui_core import ensure_bw_gui_on_path as _ensure_bw_gui_on_path

    _ensure_bw_gui_on_path()

    from bw_gui.widgets.hover_tooltip import HoverTooltip as HoverTooltip  # type: ignore[assignment]
except ModuleNotFoundError:
    # Keep local fallback implementation when shared core is unavailable.
    pass
