from __future__ import annotations

from tkinter import ttk

from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.adapters.gui.shortcut_guide import ShortcutGuideEntry


class ShortcutOverviewDialog(ScrollablePopupWindow):
    """Zeigt alle Strg-Shortcuts inklusive Merkregeln in einer kompakten Tabelle."""

    def __init__(self, master, *, entries: tuple[ShortcutGuideEntry, ...], theme_key: str | None):
        super().__init__(
            master,
            title="Shortcut-Übersicht",
            geometry="1180x560",
            minsize=(920, 360),
            theme_key=theme_key,
        )
        self._entries = tuple(entry for entry in entries if entry.is_ctrl_shortcut)
        self._build_content()

    def _build_content(self) -> None:
        root = ttk.Frame(self.content, padding=12)
        root.pack(fill="both", expand=True)

        ttk.Label(
            root,
            text=(
                "Alle Strg-Shortcuts der Hauptansicht mit Kurzbegründung. "
                "Merkregel = Buchstabenanker, Didaktik = Einsatzgedanke."
            ),
        ).pack(fill="x", pady=(0, 8))

        columns = ("shortcut", "action", "mnemonic", "didactic_hint")
        table_frame = ttk.Frame(root)
        table_frame.pack(fill="both", expand=True)

        table = ttk.Treeview(table_frame, columns=columns, show="headings")
        table.heading("shortcut", text="Shortcut")
        table.heading("action", text="Funktion")
        table.heading("mnemonic", text="Merkregel")
        table.heading("didactic_hint", text="Didaktischer Zusatz")

        table.column("shortcut", width=150, anchor="center", stretch=False)
        table.column("action", width=250, anchor="w", stretch=False)
        table.column("mnemonic", width=240, anchor="w", stretch=False)
        table.column("didactic_hint", width=520, anchor="w", stretch=True)

        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=y_scroll.set)

        table.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        for entry in self._entries:
            table.insert(
                "",
                "end",
                values=(
                    entry.display_shortcut,
                    entry.action_label,
                    entry.mnemonic,
                    entry.didactic_hint,
                ),
            )

        actions = ttk.Frame(root)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Schließen", command=self.destroy).pack(side="right")
