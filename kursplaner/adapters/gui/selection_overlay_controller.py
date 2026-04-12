from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


class SelectionOverlayController:
    """Manage a reusable dropdown overlay for field-bound option picking.

    The controller keeps overlay state independent from dialog layout code and
    centralizes keyboard/mouse selection behavior for all supported fields.
    """

    def __init__(
        self,
        owner: tk.Toplevel,
        *,
        get_items: Callable[[str], list[str]],
        on_pick: Callable[[str, str], None],
        is_heading: Callable[[str], bool],
    ):
        self.owner = owner
        self.get_items = get_items
        self.on_pick = on_pick
        self.is_heading = is_heading

        self.active_field: str | None = None
        self.active_anchor: tk.Misc | None = None
        self.items: list[str] = []

        self.overlay = tk.Toplevel(owner)
        self.overlay.withdraw()
        self.overlay.overrideredirect(True)
        self.overlay.transient(owner)

        frame = ttk.Frame(self.overlay, padding=4)
        frame.pack(fill="both", expand=True)

        self.listbox = tk.Listbox(frame, selectmode="browse", exportselection=False, height=10)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.listbox.yview)
        scroll.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scroll.set)

        self.listbox.bind("<Return>", self._pick_current)
        self.listbox.bind("<space>", self._pick_current)
        self.listbox.bind("<Double-Button-1>", self._pick_current)
        self.listbox.bind("<ButtonRelease-1>", self._pick_current)

    @property
    def is_open(self) -> bool:
        """Return whether the overlay window is currently visible."""
        if not self._overlay_exists():
            return False
        return bool(self.overlay.winfo_ismapped())

    def open(self, field: str, anchor: tk.Misc) -> None:
        """Open overlay under the anchor widget and show options for a field."""
        self.active_field = field
        self.active_anchor = anchor
        self.refresh()
        self.owner.update_idletasks()
        x = anchor.winfo_rootx()
        y = anchor.winfo_rooty() + anchor.winfo_height() + 2
        width = max(300, anchor.winfo_width())
        self.overlay.geometry(f"{width}x220+{x}+{y}")
        self.overlay.deiconify()
        self.overlay.lift()

    def refresh(self) -> None:
        """Reload listbox items from the field-specific item provider."""
        if self.active_field is None:
            return
        self.items = self.get_items(self.active_field)
        self.listbox.delete(0, tk.END)
        for item in self.items:
            self.listbox.insert(tk.END, item)
        if self.items:
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(0)
            self.listbox.activate(0)
            self.listbox.see(0)

    def close(self) -> None:
        """Hide overlay and clear active field/anchor state."""
        if self._overlay_exists():
            self.overlay.withdraw()
        self.active_field = None
        self.active_anchor = None
        self.items = []

    def _overlay_exists(self) -> bool:
        """Return True when the underlying Tk window still exists."""
        try:
            return bool(self.overlay.winfo_exists())
        except tk.TclError:
            return False

    def move(self, delta: int) -> None:
        """Move listbox selection by delta and keep target row visible."""
        size = self.listbox.size()
        if size <= 0:
            return
        current = self.listbox.curselection()
        idx = current[0] if current else 0
        idx = max(0, min(size - 1, idx + delta))
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(idx)
        self.listbox.activate(idx)
        self.listbox.see(idx)

    def select_current(self) -> None:
        """Emit selected non-heading value for the current field."""
        if self.active_field is None:
            return
        current = self.listbox.curselection()
        if not current:
            return
        idx = current[0]
        if not (0 <= idx < len(self.items)):
            return
        value = self.items[idx].strip()
        if not value or self.is_heading(value):
            return
        self.on_pick(self.active_field, value)

    def should_keep_open_for_widget(self, widget: tk.Misc | None) -> bool:
        """Return True if widget is part of overlay/anchor interaction area."""
        if widget is None:
            return False
        return self._is_descendant(widget, self.overlay) or self._is_descendant(widget, self.active_anchor)

    @staticmethod
    def _is_descendant(widget: tk.Misc | None, parent: tk.Misc | None) -> bool:
        """Return True when widget is parent itself or a recursive child."""
        if widget is None or parent is None:
            return False
        current = widget
        while current is not None:
            if current == parent:
                return True
            current = getattr(current, "master", None)
        return False

    def _pick_current(self, _event):
        """Handle mouse/keyboard activation from the listbox."""
        self.select_current()
        return "break"
