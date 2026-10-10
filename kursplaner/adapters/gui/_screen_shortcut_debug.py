"""Shortcut runtime debug dialog of the main window (ScreenBuilder mixin).

Split out of screen_builder.py (file-size rule); method bodies unchanged."""

from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets  # noqa: E402
from bw_gui.widgets import Switch  # noqa: E402

from bw_libs.ui_contract.keybinding import (  # noqa: E402
    UI_MODE_DIALOG,
    UI_MODE_EDITOR,
    UI_MODE_GLOBAL,
    UI_MODE_OFFLINE,
    UI_MODE_PREVIEW,
)


class ScreenShortcutDebugMixin:
    """Shortcut runtime debug dialog of the main window (ScreenBuilder mixin)."""

    def _toggle_shortcut_runtime_offline(self) -> None:
        """Toggle offline simulation for runtime shortcut diagnostics."""

        self.app.shortcut_debug_offline = not bool(getattr(self.app, "shortcut_debug_offline", False))
        tk_var = getattr(self.app, "shortcut_runtime_debug_offline_var", None)
        if tk_var is not None:
            tk_var.set(bool(self.app.shortcut_debug_offline))
        self._refresh_shortcut_runtime_debug_dialog()

    def _open_shortcut_runtime_debug_dialog(self) -> None:
        """Open compact tabular runtime shortcut diagnostics dialog."""

        existing = getattr(self.app, "shortcut_runtime_debug_window", None)
        if existing is not None and int(existing.winfo_exists()):
            self._refresh_shortcut_runtime_debug_dialog()
            existing.deiconify()
            existing.lift()
            existing.focus_force()
            return

        window = ui.Toplevel(self.app)
        window.title("Shortcut Runtime Debug")
        window.geometry("980x520")
        window.minsize(820, 420)
        self._track_popup_window(window, policy_id="dialog.non_blocking")

        self.app.shortcut_runtime_debug_context_var = ui.StringVar(master=window, value="")
        self.app.shortcut_runtime_debug_summary_var = ui.StringVar(master=window, value="")
        self.app.shortcut_runtime_debug_offline_var = ui.BooleanVar(
            master=window,
            value=bool(getattr(self.app, "shortcut_debug_offline", False)),
        )

        toolbar = widgets.Frame(window, padding=(10, 8))
        toolbar.pack(fill="x")
        widgets.Label(toolbar, textvariable=self.app.shortcut_runtime_debug_context_var, style="Toolbar.TLabel").pack(
            side="left",
            fill="x",
            expand=True,
        )
        Switch(
            toolbar,
            text="Offline simulieren",
            variable=self.app.shortcut_runtime_debug_offline_var,
            on_change=lambda _offline: self._on_shortcut_runtime_offline_var_changed(),
        ).pack(side="left", padx=(12, 0))
        widgets.Button(toolbar, text="Aktualisieren", command=self._refresh_shortcut_runtime_debug_dialog).pack(
            side="left", padx=(8, 0)
        )

        body = widgets.Frame(window, padding=(10, 0, 10, 8))
        body.pack(fill="both", expand=True)
        columns = ("mode", "key", "binding", "status", "reason")
        table = widgets.Treeview(body, columns=columns, show="headings")
        table.heading("mode", text="Mode")
        table.heading("key", text="Key")
        table.heading("binding", text="Binding")
        table.heading("status", text="Status")
        table.heading("reason", text="Reason")
        table.column("mode", width=100, anchor="center", stretch=False)
        table.column("key", width=130, anchor="center", stretch=False)
        table.column("binding", width=300, anchor="w", stretch=True)
        table.column("status", width=90, anchor="center", stretch=False)
        table.column("reason", width=180, anchor="w", stretch=True)
        table.pack(side="left", fill="both", expand=True)
        y_scroll = widgets.Scrollbar(body, orient="vertical", command=table.yview)
        y_scroll.pack(side="right", fill="y")
        table.configure(yscrollcommand=y_scroll.set)

        widgets.Label(window, textvariable=self.app.shortcut_runtime_debug_summary_var, style="Toolbar.TLabel").pack(
            fill="x",
            padx=10,
            pady=(0, 8),
        )

        self.app.shortcut_runtime_debug_window = window
        self.app.shortcut_runtime_debug_table = table
        window.protocol("WM_DELETE_WINDOW", self._close_shortcut_runtime_debug_dialog)
        self._refresh_shortcut_runtime_debug_dialog()

    def _close_shortcut_runtime_debug_dialog(self) -> None:
        """Destroy runtime debug dialog and clear references."""

        window = getattr(self.app, "shortcut_runtime_debug_window", None)
        if window is not None and int(window.winfo_exists()):
            self._popup_registry.close_popup(str(window))
            self._tracked_popup_ids.discard(str(window))
            window.destroy()
        self.app.shortcut_runtime_debug_window = None
        self.app.shortcut_runtime_debug_table = None
        self.app.shortcut_runtime_debug_context_var = None
        self.app.shortcut_runtime_debug_summary_var = None
        self.app.shortcut_runtime_debug_offline_var = None

    def _on_shortcut_runtime_offline_var_changed(self) -> None:
        """Sync offline flag from the dialog switch and refresh diagnostics."""

        tk_var = getattr(self.app, "shortcut_runtime_debug_offline_var", None)
        if tk_var is not None:
            self.app.shortcut_debug_offline = bool(tk_var.get())
        self._refresh_shortcut_runtime_debug_dialog()

    def _refresh_shortcut_runtime_debug_dialog(self) -> None:
        """Refresh rows and summary in runtime shortcut debug dialog."""

        table = getattr(self.app, "shortcut_runtime_debug_table", None)
        if table is None:
            return

        context = self._build_runtime_context()
        context_var = getattr(self.app, "shortcut_runtime_debug_context_var", None)
        if context_var is not None:
            context_var.set(
                f"mode={context.active_mode} | offline={context.offline} | dialog={context.dialog_open} | text-focus={context.text_input_focused}"
            )

        for item_id in table.get_children(""):
            table.delete(item_id)

        active_count = 0
        disabled_count = 0
        for mode in (UI_MODE_GLOBAL, UI_MODE_EDITOR, UI_MODE_PREVIEW, UI_MODE_DIALOG, UI_MODE_OFFLINE):
            for definition in self._runtime_shortcuts.all():
                if mode not in definition.modes and UI_MODE_GLOBAL not in definition.modes:
                    continue
                can_execute, reason = self._runtime_shortcuts.evaluate_runtime(
                    definition,
                    context,
                    active_mode_override=mode,
                )
                status = "active" if can_execute else "disabled"
                if can_execute:
                    active_count += 1
                else:
                    disabled_count += 1
                table.insert(
                    "",
                    "end",
                    values=(
                        mode,
                        str(definition.primary_key),
                        definition.binding_id,
                        status,
                        "" if can_execute else reason,
                    ),
                )

        total = active_count + disabled_count
        summary_var = getattr(self.app, "shortcut_runtime_debug_summary_var", None)
        if summary_var is not None:
            summary_var.set(
                " | ".join(
                    [
                        f"Bindings: {total} total",
                        f"{active_count} active",
                        f"{disabled_count} disabled",
                        self._summarize_laufkern_reachability(context=context),
                        self.app._summarize_laufkern_completion(),
                    ]
                )
            )
