from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets
try:
    from bw_gui.menu import CustomMenuBar as SharedCustomMenuBar
    from bw_gui.menu import MenuDefinition as SharedMenuDefinition
    from bw_gui.menu import MenuItem as SharedMenuItem
except ModuleNotFoundError:
    SharedCustomMenuBar = None
    SharedMenuDefinition = None
    SharedMenuItem = None

try:
    from bw_gui.shortcuts import compose_hover_text_for_intent as compose_shared_hover_text_for_intent
except ModuleNotFoundError:
    compose_shared_hover_text_for_intent = None


from bw_libs.ui_contract.keybinding import (
    UI_MODE_DIALOG,
    UI_MODE_EDITOR,
    UI_MODE_GLOBAL,
    UI_MODE_OFFLINE,
    UI_MODE_PREVIEW,
    KeyBindingDefinition,
    KeybindingRegistry,
    KeybindingRuntimeContext,
)
from bw_libs.ui_contract.popup import POPUP_KIND_MODAL, POPUP_KIND_NON_MODAL, PopupPolicy, PopupPolicyRegistry
from kursplaner.adapters.gui.help_catalog import MAIN_WINDOW_HELP
from kursplaner.adapters.gui.hover_tooltip import HoverTooltip
from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.adapters.gui.shortcut_guide import load_shortcut_guide_entries
from kursplaner.adapters.gui.toolbar_viewmodel import (
    TOOLBAR_ACTIONS,
    TOOLBAR_SEPARATOR_SLOTS,
    TOOLBAR_SLOT_MIN_WIDTH,
    TOOLBAR_SLOT_ORDER,
)
from kursplaner.adapters.gui.ui_intents import UiIntent
from kursplaner.adapters.gui.ui_theme import (
    THEMES,
    THEME_ORDER,
    apply_window_theme,
    configure_ttk_theme,
    get_theme,
    populate_theme_menu,
)


class ScreenBuilder:
    """Baut die visuellen UI-Strukturen der Hauptansicht.

    Enthält ausschließlich Layout-, Menü- und Theme-Aufbau ohne Fachlogik.
    """

    def __init__(self, app):
        """Initialisiert den Builder mit Zugriff auf den Hauptfenster-Adapter."""
        self.app = app
        self._last_toolbar_wrap_width = -1
        self._runtime_shortcuts = KeybindingRegistry()
        self._popup_registry = PopupPolicyRegistry()
        self._popup_registry.register_policy(PopupPolicy(policy_id="dialog.modal", kind=POPUP_KIND_MODAL))
        self._popup_registry.register_policy(
            PopupPolicy(
                policy_id="dialog.non_blocking",
                kind=POPUP_KIND_NON_MODAL,
                trap_focus=False,
                affects_mode=False,
            )
        )
        self._tracked_popup_ids: set[str] = set()
        self.app.shortcut_debug_offline = False
        self.app.shortcut_runtime_debug_window = None
        self.app.shortcut_runtime_debug_table = None
        self.app.shortcut_runtime_debug_context_var = None
        self.app.shortcut_runtime_debug_summary_var = None
        self.app.shortcut_runtime_debug_offline_var = None
        self._shared_menu_bar = None
        self._intent_help_tooltips: list[tuple[HoverTooltip, str, str]] = []

    def _apply_toolbar_icons(self):
        styler = getattr(self.app, "toolbar_icon_styler", None)
        if styler is None:
            return
        styler.apply(self.app.theme_var.get())

    def build_ui(self):
        """Erzeugt Widgets und verbindet UI-Events mit Adapter-Delegationspunkten."""
        root = widgets.Frame(self.app, padding=16)
        root.pack(fill="both", expand=True)
        self._ensure_tooltip_store()
        self.app.action_buttons = {}
        self.app.action_help_tooltips = {}
        self.app.toolbar_slots = {}
        self.app.toolbar_separators = {}

        self._build_menu()

        top = widgets.Frame(root)
        top.pack(fill="x", pady=(0, 10))

        base_label = widgets.Label(top, text="Kursordner")
        base_label.pack(side="left")
        base_entry = widgets.Entry(top, textvariable=self.app.base_dir_var)
        base_entry.pack(side="left", fill="x", expand=True, padx=(8, 8))
        base_button = widgets.Button(top, text="Ordner wählen…", command=self.app._pick_base_dir)
        base_button.pack(side="left")
        self._add_help(base_label, MAIN_WINDOW_HELP["course_dir"])
        self._add_help(base_entry, MAIN_WINDOW_HELP["course_dir"])
        self._add_help(base_button, MAIN_WINDOW_HELP["course_dir"])

        toolbar = widgets.Frame(root, style="Toolbar.TFrame")
        toolbar.pack(fill="x", pady=(0, 2))
        self.app.toolbar_frame = toolbar
        for slot_key in TOOLBAR_SLOT_ORDER:
            slot = widgets.Frame(toolbar, style="Toolbar.TFrame")
            min_width = int(TOOLBAR_SLOT_MIN_WIDTH.get(slot_key, 56))
            slot.configure(width=min_width)
            # Keep width hints, but let slot height follow button requested size.
            # Slot placement is managed by _layout_toolbar_slots via grid (no pack in this container).
            slot.pack_propagate(True)
            self.app.toolbar_slots[slot_key] = slot
            if slot_key in TOOLBAR_SEPARATOR_SLOTS:
                separator = widgets.Separator(slot, orient="vertical")
                separator.pack(fill="y", padx=8)
                self.app.toolbar_separators[slot_key] = separator

        for spec in TOOLBAR_ACTIONS:
            slot = self.app.toolbar_slots[spec.slot_key]
            button_kwargs = {
                "text": spec.text,
                "command": lambda intent=spec.intent, payload=spec.payload: self._emit_intent(intent, **dict(payload)),
                "style": spec.style,
            }
            if spec.width is not None:
                button_kwargs["width"] = spec.width
            button = widgets.Button(slot, **button_kwargs)
            button.pack(side="left", padx=spec.padx)
            self.app.action_buttons[spec.key] = button
            if spec.help_key is not None:
                tooltip = self._add_help(button, MAIN_WINDOW_HELP.get(spec.help_key, ""), intent=spec.intent)
                if tooltip is not None:
                    self.app.action_help_tooltips[spec.key] = tooltip

        widgets.Label(root, textvariable=self.app.count_var, style="Toolbar.TLabel").pack(anchor="e", pady=(0, 8))
        self._layout_toolbar_slots()
        toolbar.bind("<Configure>", self._on_toolbar_configure)
        self._apply_toolbar_icons()

        paned = widgets.Panedwindow(root, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = widgets.Frame(paned)
        right = widgets.Frame(paned)
        paned.add(left, weight=1)
        paned.add(right, weight=3)
        self.app.main_paned = paned
        self.app.course_panel = left
        self.app.detail_panel = right

        overview_columns = ("name", "next_topic", "remaining_hours", "next_lzk", "next_ub")
        tree_frame = widgets.Frame(left)
        tree_frame.pack(fill="both", expand=True)

        self.app.lesson_tree = widgets.Treeview(tree_frame, columns=overview_columns, show="headings")
        self.app.lesson_tree.heading("name", text="Kurs")
        self.app.lesson_tree.heading("next_topic", text="Nächstes Thema")
        self.app.lesson_tree.heading("remaining_hours", text="Reststunden")
        self.app.lesson_tree.heading("next_lzk", text="Nächste LZK")
        self.app.lesson_tree.heading("next_ub", text="Nächster UB")
        self.app.lesson_tree.column("name", width=220, anchor="w")
        self.app.lesson_tree.column("next_topic", width=280, anchor="w")
        self.app.lesson_tree.column("remaining_hours", width=90, anchor="center")
        self.app.lesson_tree.column("next_lzk", width=110, anchor="center")
        self.app.lesson_tree.column("next_ub", width=130, anchor="center")

        tree_scroll = widgets.Scrollbar(tree_frame, orient="vertical", command=self.app.lesson_tree.yview)
        self.app.lesson_tree.configure(yscrollcommand=tree_scroll.set)

        self.app.lesson_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self._add_help(self.app.lesson_tree, MAIN_WINDOW_HELP["lesson_tree"])

        self.app.lesson_tree.bind("<Return>", self._on_tree_confirm_selection)
        self.app.lesson_tree.bind("<KP_Enter>", self._on_tree_confirm_selection)
        self.app.lesson_tree.bind("<Double-1>", self._on_tree_confirm_selection)
        self.app.lesson_tree.bind("<ButtonRelease-1>", self._on_tree_confirm_selection)
        self.app.lesson_tree.bind("<Motion>", self._on_tree_hover_select)
        self.app.lesson_tree.bind("<Up>", self._on_tree_keyboard_navigation, add="+")
        self.app.lesson_tree.bind("<Down>", self._on_tree_keyboard_navigation, add="+")

        header = widgets.Frame(right)
        header.pack(fill="x", pady=(0, 6))
        preview_label = widgets.Label(header, textvariable=self.app.preview_title_var)
        preview_label.pack(side="left")
        close_button = widgets.Button(
            header,
            text="Zur Kursliste",
            command=lambda: self._emit_intent(UiIntent.CLOSE_DETAIL_VIEW),
            style="Action.Utility.TButton",
        )
        close_button.pack(side="right")
        selected_column_label = widgets.Label(header, textvariable=self.app.selected_column_var)
        selected_column_label.pack(side="right")
        self._add_help(preview_label, MAIN_WINDOW_HELP.get("detail_navigation", ""))
        self._add_help(close_button, MAIN_WINDOW_HELP.get("detail_navigation", ""))
        self._add_help(selected_column_label, MAIN_WINDOW_HELP.get("detail_navigation", ""))

        mode_bar = widgets.Frame(right)
        mode_bar.pack(fill="x", pady=(0, 6))
        widgets.Label(mode_bar, text="Ansicht:").pack(side="left")
        for mode_key, label in (
            ("unterricht", "Unterricht"),
            ("lzk", "LZK"),
            ("ausfall", "Ausfall"),
            ("hospitation", "Hospitation"),
        ):
            mode_style_map = {
                "unterricht": "Action.View.Unterricht.TButton",
                "lzk": "Action.View.Lzk.TButton",
                "ausfall": "Action.View.Ausfall.TButton",
                "hospitation": "Action.View.Hospitation.TButton",
            }
            btn = widgets.Button(
                mode_bar,
                text=label,
                command=lambda key=mode_key: self._emit_intent(UiIntent.SET_ROW_MODE, mode_key=key, manual=True),
                style=mode_style_map.get(mode_key, "Action.Utility.TButton"),
            )
            btn.pack(side="left", padx=(6, 0))
            self.app.row_mode_buttons[mode_key] = btn
            self.app.row_mode_labels[mode_key] = label
            self._add_help(btn, MAIN_WINDOW_HELP.get(f"mode_{mode_key}", ""))

        auto_mode_check = widgets.Checkbutton(
            mode_bar,
            text="Auto je Spalte",
            variable=self.app.auto_row_mode_var,
            command=lambda: self._emit_intent(UiIntent.TOGGLE_AUTO_ROW_MODE),
        )
        auto_mode_check.pack(side="left", padx=(12, 0))
        self._add_help(auto_mode_check, MAIN_WINDOW_HELP["mode_auto"])

        column_visibility_button = widgets.Button(
            mode_bar,
            text="Spaltenarten…",
            command=lambda: self._emit_intent(UiIntent.OPEN_COLUMN_VISIBILITY_SETTINGS),
            style="Action.Utility.TButton",
        )
        column_visibility_button.pack(side="left", padx=(12, 0))
        self.app.action_buttons["column_visibility"] = column_visibility_button
        tooltip = self._add_help(
            column_visibility_button,
            MAIN_WINDOW_HELP.get("column_visibility", ""),
            intent=UiIntent.OPEN_COLUMN_VISIBILITY_SETTINGS,
        )
        if tooltip is not None:
            self.app.action_help_tooltips["column_visibility"] = tooltip
        self.app._refresh_row_mode_button_styles()

        editor_frame = widgets.Frame(right)
        editor_frame.pack(fill="both", expand=True)

        self.app.fixed_header_frame = ui.Frame(editor_frame, highlightthickness=0, width=220)
        self.app.fixed_header_frame.grid(row=0, column=0, sticky="nsew")

        self.app.header_canvas = ui.Canvas(editor_frame, highlightthickness=0, height=1)
        self.app.header_canvas.grid(row=0, column=1, sticky="nsew")

        self.app.fixed_canvas = ui.Canvas(editor_frame, highlightthickness=0, width=220)
        self.app.fixed_canvas.grid(row=1, column=0, sticky="nsew")

        self.app.grid_canvas = ui.Canvas(editor_frame, highlightthickness=0)
        self.app.grid_canvas.grid(row=1, column=1, sticky="nsew")

        def _on_grid_xscroll(first: float, last: float):
            x_scroll.set(first, last)
            self.app.header_canvas.xview_moveto(first)

        y_scroll = widgets.Scrollbar(editor_frame, orient="vertical", command=self.app._on_vertical_scroll)
        x_scroll = widgets.Scrollbar(editor_frame, orient="horizontal", command=self.app._on_horizontal_scroll)
        self.app.grid_canvas.configure(yscrollcommand=y_scroll.set, xscrollcommand=_on_grid_xscroll)
        y_scroll.grid(row=1, column=2, sticky="ns")
        x_scroll.grid(row=2, column=1, sticky="ew")

        editor_frame.rowconfigure(0, weight=0)
        editor_frame.rowconfigure(1, weight=1)
        editor_frame.columnconfigure(0, weight=0)
        editor_frame.columnconfigure(1, weight=1)

        self.app.header_inner = widgets.Frame(self.app.header_canvas)
        self.app.header_window = self.app.header_canvas.create_window((0, 0), window=self.app.header_inner, anchor="nw")
        self.app.fixed_inner = widgets.Frame(self.app.fixed_canvas)
        self.app.fixed_window = self.app.fixed_canvas.create_window((0, 0), window=self.app.fixed_inner, anchor="nw")
        self.app.grid_inner = widgets.Frame(self.app.grid_canvas)
        self.app.grid_window = self.app.grid_canvas.create_window((0, 0), window=self.app.grid_inner, anchor="nw")

        self.app.header_inner.bind("<Configure>", self.app._on_grid_inner_configure)
        self.app.fixed_inner.bind("<Configure>", self.app._on_grid_inner_configure)
        self.app.grid_inner.bind("<Configure>", self.app._on_grid_inner_configure)
        self.app.header_canvas.bind("<Configure>", self.app._on_canvas_configure)
        self.app.fixed_canvas.bind("<Configure>", self.app._on_canvas_configure)
        self.app.grid_canvas.bind("<Configure>", self.app._on_canvas_configure)
        self.app.header_canvas.bind("<MouseWheel>", self.app._on_grid_mousewheel)
        self.app.fixed_canvas.bind("<MouseWheel>", self.app._on_grid_mousewheel)
        self.app.grid_canvas.bind("<MouseWheel>", self.app._on_grid_mousewheel)

        self.show_course_overview()

    @staticmethod
    def _slot_width(slot_key: str) -> int:
        return int(TOOLBAR_SLOT_MIN_WIDTH.get(slot_key, 56)) + 2

    def _split_group_by_width(self, group: list[str], max_width: int) -> list[list[str]]:
        parts: list[list[str]] = []
        current: list[str] = []
        current_width = 0
        for slot_key in group:
            slot_width = self._slot_width(slot_key)
            if current and (current_width + slot_width) > max_width:
                parts.append(current)
                current = [slot_key]
                current_width = slot_width
            else:
                current.append(slot_key)
                current_width += slot_width
        if current:
            parts.append(current)
        return parts

    def _build_toolbar_rows(self, max_width: int) -> list[list[str]]:
        groups: list[list[str]] = [
            [
                "new",
                "refresh",
                "extend_to_vacation",
                "sep_primary",
                "undo",
                "redo",
                "sep_extend",
            ],
            ["plan", "ausfall", "hospitation", "lzk", "lzk_expected_horizon", "mark_ub", "sep_secondary"],
            [
                "copy",
                "paste",
                "find",
                "clear",
                "rename",
                "split",
                "merge",
                "move_left",
                "move_right",
                "export_as",
            ],
        ]

        rows: list[list[str]] = [[]]
        row_width = 0

        for group in groups:
            group_width = sum(self._slot_width(item) for item in group)
            parts = [group] if group_width <= max_width else self._split_group_by_width(group, max_width)

            for part in parts:
                part_width = sum(self._slot_width(item) for item in part)
                if rows[-1] and (row_width + part_width) > max_width:
                    rows.append(list(part))
                    row_width = part_width
                else:
                    rows[-1].extend(part)
                    row_width += part_width

        cleaned_rows: list[list[str]] = []
        for row in rows:
            if not row:
                continue
            compact = list(row)
            while compact and compact[0] in TOOLBAR_SEPARATOR_SLOTS:
                compact.pop(0)
            while compact and compact[-1] in TOOLBAR_SEPARATOR_SLOTS:
                compact.pop()
            if compact:
                cleaned_rows.append(compact)

        return cleaned_rows

    def _layout_toolbar_slots(self):
        toolbar = getattr(self.app, "toolbar_frame", None)
        slots = getattr(self.app, "toolbar_slots", None)
        if toolbar is None or not isinstance(slots, dict):
            return

        available_width = max(int(toolbar.winfo_width()) - 8, 260)
        rows = self._build_toolbar_rows(available_width)

        for slot in slots.values():
            slot.grid_forget()

        for row_idx, row in enumerate(rows):
            for col_idx, slot_key in enumerate(row):
                slot = slots.get(slot_key)
                if slot is None:
                    continue
                slot.grid(row=row_idx, column=col_idx, sticky="w", padx=(0, 2), pady=(0 if row_idx == 0 else 2, 0))

    def _on_toolbar_configure(self, _event=None):
        toolbar = getattr(self.app, "toolbar_frame", None)
        if toolbar is None:
            return
        width = int(toolbar.winfo_width())
        if width == self._last_toolbar_wrap_width:
            return
        self._last_toolbar_wrap_width = width
        self._layout_toolbar_slots()

    def _set_theme_from_menu(self, theme_key: str) -> None:
        self.app.theme_var.set(theme_key)
        self.app._on_theme_changed()

    def _recent_changes_menu_items(self):
        if SharedMenuItem is None:
            return ()

        labels = self.app.action_controller.list_recent_change_labels(limit=5)
        if not labels:
            return (SharedMenuItem(type="disabled", label="Keine Änderungen"),)

        return tuple(
            SharedMenuItem(
                type="command",
                label=f"{idx + 1}. {(label.strip() or 'Änderung')}",
                command=lambda recent_index=idx: self._emit_intent(
                    UiIntent.EDIT_UNDO_TO_RECENT_INDEX,
                    recent_index=recent_index,
                ),
            )
            for idx, label in enumerate(labels)
        )

    def _menu_items_file(self):
        return (
            SharedMenuItem(type="command", label="Neu (Strg+N)", command=lambda: self._emit_intent(UiIntent.TOOLBAR_NEW)),
            SharedMenuItem(
                type="command",
                label="Lesson-Index neu aufbauen",
                command=lambda: self._emit_intent(UiIntent.REBUILD_LESSON_INDEX),
            ),
            SharedMenuItem(type="command", label="Einstellungen…", command=lambda: self._emit_intent(UiIntent.OPEN_SETTINGS)),
            SharedMenuItem(type="separator"),
            SharedMenuItem(type="command", label="Beenden", command=self.app.destroy),
        )

    def _menu_items_edit(self):
        return (
            SharedMenuItem(type="command", label="Undo (Strg+Z)", command=lambda: self._emit_intent(UiIntent.TOOLBAR_UNDO)),
            SharedMenuItem(type="command", label="Redo (Strg+Y)", command=lambda: self._emit_intent(UiIntent.TOOLBAR_REDO)),
            SharedMenuItem(type="submenu", label="Letzte Änderungen", items=self._recent_changes_menu_items()),
        )

    def _menu_items_action(self):
        return (
            SharedMenuItem(type="command", label="Einheit kopieren (Strg+C)", command=lambda: self._emit_intent(UiIntent.TOOLBAR_COPY)),
            SharedMenuItem(type="command", label="Einheit einfügen (Strg+V)", command=lambda: self._emit_intent(UiIntent.TOOLBAR_PASTE)),
            SharedMenuItem(type="command", label="Exportieren als... (Strg+P)", command=lambda: self._emit_intent(UiIntent.TOOLBAR_EXPORT_AS)),
            SharedMenuItem(type="command", label="Markdown finden…", command=lambda: self._emit_intent(UiIntent.TOOLBAR_FIND)),
            SharedMenuItem(type="separator"),
            SharedMenuItem(type="command", label="Einheit leeren", command=lambda: self._emit_intent(UiIntent.TOOLBAR_CLEAR)),
            SharedMenuItem(type="command", label="Einheit umbenennen…", command=lambda: self._emit_intent(UiIntent.TOOLBAR_RENAME)),
            SharedMenuItem(type="command", label="Schatteneinheiten anzeigen…", command=lambda: self._emit_intent(UiIntent.SHOW_SHADOW_LESSONS)),
            SharedMenuItem(type="command", label="Einheit aufsplitten", command=lambda: self._emit_intent(UiIntent.TOOLBAR_SPLIT)),
            SharedMenuItem(type="command", label="Einheiten zusammenführen", command=lambda: self._emit_intent(UiIntent.TOOLBAR_MERGE)),
            SharedMenuItem(
                type="command",
                label="Kontextaktion: UB markieren / Ausfall zurücknehmen (Strg+B)",
                command=lambda: self._emit_intent(UiIntent.TOGGLE_RESUME_OR_UB),
            ),
            SharedMenuItem(
                type="command",
                label="Als Hospitation markieren",
                command=lambda: self._emit_intent(UiIntent.TOOLBAR_HOSPITATION),
            ),
        )

    def _menu_items_view(self):
        theme_items = tuple(
            SharedMenuItem(
                type="radio",
                label=THEMES[theme_key].get("label", theme_key),
                checked=(self.app.theme_var.get() == theme_key),
                command=lambda key=theme_key: self._set_theme_from_menu(key),
            )
            for theme_key in THEME_ORDER
        )

        return (
            SharedMenuItem(
                type="radio",
                label="Lange Zeilen aufgeklappt",
                checked=bool(self.app.expand_long_rows_var.get()),
                command=lambda: self._emit_intent(UiIntent.TOGGLE_EXPAND_MODE),
            ),
            SharedMenuItem(
                type="command",
                label="Spaltenarten anzeigen/verstecken… (Strg+L)",
                command=lambda: self._emit_intent(UiIntent.OPEN_COLUMN_VISIBILITY_SETTINGS),
            ),
            SharedMenuItem(
                type="radio",
                label="Auto-Scroll zur nächsten Einheit",
                checked=bool(self.app.auto_scroll_next_unit_var.get()),
                command=lambda: self.app.auto_scroll_next_unit_var.set(not bool(self.app.auto_scroll_next_unit_var.get())),
            ),
            SharedMenuItem(type="separator"),
            SharedMenuItem(
                type="command",
                label="UB-Übersicht anzeigen (Strg+Shift+U)",
                command=lambda: self._emit_intent(UiIntent.SHOW_UB_ACHIEVEMENTS),
            ),
            SharedMenuItem(
                type="command",
                label="Shortcut-Übersicht anzeigen (Strg+H)",
                command=lambda: self._emit_intent(UiIntent.SHOW_SHORTCUT_OVERVIEW),
            ),
            SharedMenuItem(
                type="command",
                label="Shortcut-Runtime-Debug anzeigen (Strg+Shift+D)",
                command=self._open_shortcut_runtime_debug_dialog,
            ),
            SharedMenuItem(type="separator"),
            SharedMenuItem(type="submenu", label="Theme", items=theme_items),
        )

    def _build_menu(self):
        """Erzeugt die Hauptmenüs inklusive Wartungsaktionen."""
        if SharedCustomMenuBar is None or SharedMenuDefinition is None or SharedMenuItem is None:
            self._build_native_menu()
            return

        if self._shared_menu_bar is not None:
            self._shared_menu_bar.destroy()

        definitions = (
            SharedMenuDefinition(key="datei", label="Datei", alt="d", items_provider=self._menu_items_file),
            SharedMenuDefinition(key="bearbeiten", label="Bearbeiten", alt="b", items_provider=self._menu_items_edit),
            SharedMenuDefinition(key="aktion", label="Aktion", alt="k", items_provider=self._menu_items_action),
            SharedMenuDefinition(key="ansicht", label="Ansicht", alt="a", items_provider=self._menu_items_view),
        )

        self._shared_menu_bar = SharedCustomMenuBar(
            self.app,
            definitions,
            theme_key=self.app.theme_var.get(),
        )
        self._shared_menu_bar.build()
        self.app.config(menu="")

    def _build_native_menu(self):
        """Fallback-Menü für Umgebungen ohne Shared CustomMenuBar."""
        menu = ui.Menu(self.app)

        datei = ui.Menu(menu, tearoff=0)
        datei.add_command(label="Neu", accelerator="Strg+N", command=lambda: self._emit_intent(UiIntent.TOOLBAR_NEW))
        datei.add_command(
            label="Lesson-Index neu aufbauen", command=lambda: self._emit_intent(UiIntent.REBUILD_LESSON_INDEX)
        )
        datei.add_command(label="Einstellungen…", command=lambda: self._emit_intent(UiIntent.OPEN_SETTINGS))
        datei.add_separator()
        datei.add_command(label="Beenden", command=self.app.destroy)
        menu.add_cascade(label="Datei", menu=datei)

        bearbeiten = ui.Menu(menu, tearoff=0)
        bearbeiten.add_command(
            label="Undo", accelerator="Strg+Z", command=lambda: self._emit_intent(UiIntent.TOOLBAR_UNDO)
        )
        bearbeiten.add_command(
            label="Redo", accelerator="Strg+Y", command=lambda: self._emit_intent(UiIntent.TOOLBAR_REDO)
        )
        recent_changes_menu = ui.Menu(
            bearbeiten,
            tearoff=0,
            postcommand=lambda: self._populate_recent_changes_menu(recent_changes_menu),
        )
        bearbeiten.add_cascade(label="Letzte Änderungen", menu=recent_changes_menu)
        menu.add_cascade(label="Bearbeiten", menu=bearbeiten)

        aktion = ui.Menu(menu, tearoff=0)
        aktion.add_command(
            label="Einheit kopieren", accelerator="Strg+C", command=lambda: self._emit_intent(UiIntent.TOOLBAR_COPY)
        )
        aktion.add_command(
            label="Einheit einfügen", accelerator="Strg+V", command=lambda: self._emit_intent(UiIntent.TOOLBAR_PASTE)
        )
        aktion.add_command(
            label="Exportieren als...",
            accelerator="Strg+P",
            command=lambda: self._emit_intent(UiIntent.TOOLBAR_EXPORT_AS),
        )
        aktion.add_command(label="Markdown finden…", command=lambda: self._emit_intent(UiIntent.TOOLBAR_FIND))
        aktion.add_separator()
        aktion.add_command(label="Einheit leeren", command=lambda: self._emit_intent(UiIntent.TOOLBAR_CLEAR))
        aktion.add_command(label="Einheit umbenennen…", command=lambda: self._emit_intent(UiIntent.TOOLBAR_RENAME))
        aktion.add_command(
            label="Schatteneinheiten anzeigen…", command=lambda: self._emit_intent(UiIntent.SHOW_SHADOW_LESSONS)
        )
        aktion.add_command(label="Einheit aufsplitten", command=lambda: self._emit_intent(UiIntent.TOOLBAR_SPLIT))
        aktion.add_command(label="Einheiten zusammenführen", command=lambda: self._emit_intent(UiIntent.TOOLBAR_MERGE))
        aktion.add_command(
            label="Kontextaktion: UB markieren / Ausfall zurücknehmen",
            accelerator="Strg+B",
            command=lambda: self._emit_intent(UiIntent.TOGGLE_RESUME_OR_UB),
        )
        aktion.add_command(
            label="Als Hospitation markieren", command=lambda: self._emit_intent(UiIntent.TOOLBAR_HOSPITATION)
        )
        menu.add_cascade(label="Aktion", menu=aktion)

        ansicht = ui.Menu(menu, tearoff=0)
        theme_menu = ui.Menu(ansicht, tearoff=0)
        populate_theme_menu(theme_menu, self.app.theme_var, self.app._on_theme_changed)
        ansicht.add_checkbutton(
            label="Lange Zeilen aufgeklappt",
            variable=self.app.expand_long_rows_var,
            command=lambda: self._emit_intent(UiIntent.TOGGLE_EXPAND_MODE),
        )
        ansicht.add_command(
            label="Spaltenarten anzeigen/verstecken…",
            accelerator="Strg+L",
            command=lambda: self._emit_intent(UiIntent.OPEN_COLUMN_VISIBILITY_SETTINGS),
        )
        ansicht.add_checkbutton(
            label="Auto-Scroll zur nächsten Einheit",
            variable=self.app.auto_scroll_next_unit_var,
        )
        ansicht.add_separator()
        ansicht.add_command(
            label="UB-Übersicht anzeigen",
            accelerator="Strg+Shift+U",
            command=lambda: self._emit_intent(UiIntent.SHOW_UB_ACHIEVEMENTS),
        )
        ansicht.add_command(
            label="Shortcut-Übersicht anzeigen",
            accelerator="Strg+H",
            command=lambda: self._emit_intent(UiIntent.SHOW_SHORTCUT_OVERVIEW),
        )
        ansicht.add_command(
            label="Shortcut-Runtime-Debug anzeigen",
            accelerator="Strg+Shift+D",
            command=self._open_shortcut_runtime_debug_dialog,
        )
        ansicht.add_separator()
        ansicht.add_cascade(label="Theme", menu=theme_menu)
        menu.add_cascade(label="Ansicht", menu=ansicht)

        self.app.config(menu=menu)

    def _populate_recent_changes_menu(self, menu: ui.Menu):
        """Füllt das Untermenü mit den letzten Undo-Einträgen (neueste zuerst)."""
        menu.delete(0, "end")
        labels = self.app.action_controller.list_recent_change_labels(limit=5)
        if not labels:
            menu.add_command(label="Keine Änderungen", state="disabled")
            return

        for idx, label in enumerate(labels):
            short_label = label.strip() or "Änderung"
            menu.add_command(
                label=f"{idx + 1}. {short_label}",
                command=lambda recent_index=idx: self._emit_intent(
                    UiIntent.EDIT_UNDO_TO_RECENT_INDEX,
                    recent_index=recent_index,
                ),
            )

    def _ensure_tooltip_store(self):
        """Stellt sicher, dass Tooltip-Objekte am App-Lifecycle hängen."""
        if not hasattr(self.app, "hover_tooltips"):
            self.app.hover_tooltips = []

    def _add_help(self, widget: ui.Widget, text: str, *, intent: str | None = None) -> HoverTooltip | None:
        """Registriert bei Bedarf eine Hover-Hilfe für ein Widget."""
        base_text = text.strip()
        if not base_text:
            return None

        rendered_text = base_text
        if intent and compose_shared_hover_text_for_intent is not None:
            rendered_text = compose_shared_hover_text_for_intent(
                base_text,
                intent=intent,
                shortcuts=self._runtime_shortcuts,
            )

        tooltip = HoverTooltip(widget, rendered_text)
        if intent is not None:
            self._intent_help_tooltips.append((tooltip, base_text, intent))
        self.app.hover_tooltips.append(tooltip)
        return tooltip

    def _refresh_intent_help_tooltips(self) -> None:
        """Aktualisiert Intent-basierte Hover-Texte nach Shortcut-Registrierung."""

        if compose_shared_hover_text_for_intent is None:
            return

        for tooltip, base_text, intent in list(self._intent_help_tooltips):
            try:
                tooltip.text = compose_shared_hover_text_for_intent(
                    base_text,
                    intent=intent,
                    shortcuts=self._runtime_shortcuts,
                )
            except Exception:
                continue

    def _bind_shortcuts(self):
        """Registriert globale Tastaturkürzel für die Hauptansicht."""
        shortcut_entries = load_shortcut_guide_entries()
        for index, entry in enumerate(shortcut_entries):
            definition = self._register_runtime_shortcut(
                binding_id=f"guide.{entry.intent}.{index}",
                sequence=entry.key_sequence,
                intent=entry.intent,
                modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW),
                allow_when_text_input=False,
            )
            self.app.bind_all(entry.key_sequence, self._build_shortcut_handler(entry, definition=definition))

        self._bind_runtime_shortcut(
            "<F2>",
            lambda event: self._emit_intent(UiIntent.TOOLBAR_RENAME, from_shortcut=True),
            binding_id="global.rename",
            intent=UiIntent.TOOLBAR_RENAME,
            modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW),
        )
        self._bind_runtime_shortcut("<Return>", self._on_grid_enter, binding_id="grid.enter", intent=UiIntent.GRID_ENTER, modes=(UI_MODE_PREVIEW,))
        self._bind_runtime_shortcut("<KP_Enter>", self._on_grid_enter, binding_id="grid.enter.numpad", intent=UiIntent.GRID_ENTER, modes=(UI_MODE_PREVIEW,))
        self._bind_runtime_shortcut("<Up>", self._on_grid_nav_up, binding_id="grid.nav.up", intent=UiIntent.GRID_NAV_UP, modes=(UI_MODE_PREVIEW,), add="+")
        self._bind_runtime_shortcut("<Down>", self._on_grid_nav_down, binding_id="grid.nav.down", intent=UiIntent.GRID_NAV_DOWN, modes=(UI_MODE_PREVIEW,), add="+")
        self._bind_runtime_shortcut("<Left>", self._on_detail_left, binding_id="detail.left", intent=UiIntent.SHORTCUT_DETAIL_LEFT, modes=(UI_MODE_PREVIEW,))
        self._bind_runtime_shortcut("<Right>", self._on_detail_right, binding_id="detail.right", intent=UiIntent.SHORTCUT_DETAIL_RIGHT, modes=(UI_MODE_PREVIEW,))
        self._bind_runtime_shortcut("<Alt-Left>", self._on_detail_left_all, binding_id="detail.left.all", intent=UiIntent.SHORTCUT_DETAIL_LEFT_ALL, modes=(UI_MODE_PREVIEW,))
        self._bind_runtime_shortcut("<Alt-Right>", self._on_detail_right_all, binding_id="detail.right.all", intent=UiIntent.SHORTCUT_DETAIL_RIGHT_ALL, modes=(UI_MODE_PREVIEW,))
        self._bind_runtime_shortcut("<Home>", self._on_home, binding_id="grid.home", intent=UiIntent.GRID_HOME, modes=(UI_MODE_PREVIEW,))
        self._bind_runtime_shortcut("<End>", self._on_end, binding_id="grid.end", intent=UiIntent.GRID_END, modes=(UI_MODE_PREVIEW,))
        self._bind_runtime_shortcut("<Delete>", self._on_grid_delete, binding_id="grid.delete", intent=UiIntent.GRID_DELETE_CELL, modes=(UI_MODE_PREVIEW,))
        self._bind_runtime_shortcut("<BackSpace>", self._on_grid_delete, binding_id="grid.delete.backspace", intent=UiIntent.GRID_DELETE_CELL, modes=(UI_MODE_PREVIEW,))
        self._bind_runtime_shortcut("<Control-Return>", self._on_ctrl_enter, binding_id="grid.commit.ctrl-enter", intent=UiIntent.SHORTCUT_COMMIT_EDIT, modes=(UI_MODE_PREVIEW,), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-KP_Enter>", self._on_ctrl_enter, binding_id="grid.commit.ctrl-enter-numpad", intent=UiIntent.SHORTCUT_COMMIT_EDIT, modes=(UI_MODE_PREVIEW,), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Escape>", self._on_escape, binding_id="global.escape", intent=UiIntent.SHORTCUT_ESCAPE, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW, UI_MODE_DIALOG), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Button-1>", self._on_global_click_commit_cell, binding_id="global.click-commit", intent=UiIntent.GLOBAL_CLICK_COMMIT_CELL, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW), add="+")
        self._bind_runtime_shortcut(
            "<Control-Shift-d>",
            lambda _event: self._open_shortcut_runtime_debug_dialog(),
            binding_id="global.runtime-debug",
            intent="debug.shortcut.runtime",
            modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW, UI_MODE_DIALOG),
            allow_when_text_input=True,
        )
        self._bind_runtime_shortcut(
            "<Control-Shift-o>",
            lambda _event: self._toggle_shortcut_runtime_offline(),
            binding_id="global.runtime-offline",
            intent="debug.shortcut.offline",
            modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW, UI_MODE_DIALOG),
            allow_when_text_input=True,
        )
        self._refresh_intent_help_tooltips()

    def _register_runtime_shortcut(
        self,
        *,
        binding_id: str,
        sequence: str,
        intent: str,
        modes: tuple[str, ...],
        allow_when_text_input: bool,
        allow_when_offline: bool = True,
    ) -> KeyBindingDefinition:
        """Register one runtime shortcut definition in the central resolver."""

        definition = KeyBindingDefinition(
            binding_id=binding_id,
            sequence=sequence,
            intent=intent,
            modes=modes,
            allow_when_text_input=allow_when_text_input,
            allow_when_offline=allow_when_offline,
        )
        self._runtime_shortcuts.register(definition)
        return definition

    def _build_runtime_context(self, event: ui.Event[ui.Misc] | None = None) -> KeybindingRuntimeContext:
        """Build runtime context for mode-aware shortcut evaluation."""

        focus_get = getattr(self.app, "focus_get", None)
        focused_widget = getattr(event, "widget", None)
        if focused_widget is None and callable(focus_get):
            focused_widget = focus_get()
        text_input_focused = self._is_editable_widget(focused_widget)
        self._sync_popup_sessions_from_windows()
        dialog_open = self._popup_registry.has_mode_blocking_popup()
        offline = bool(getattr(self.app, "shortcut_debug_offline", False))

        if offline:
            active_mode = UI_MODE_OFFLINE
        elif dialog_open:
            active_mode = UI_MODE_DIALOG
        elif text_input_focused:
            active_mode = UI_MODE_EDITOR
        elif bool(getattr(self.app, "is_detail_view", False)):
            active_mode = UI_MODE_PREVIEW
        else:
            active_mode = UI_MODE_GLOBAL

        return KeybindingRuntimeContext(
            active_mode=active_mode,
            offline=offline,
            text_input_focused=text_input_focused,
            dialog_open=dialog_open,
        )

    def _bind_runtime_shortcut(
        self,
        sequence: str,
        handler,
        *,
        binding_id: str,
        intent: str,
        modes: tuple[str, ...],
        allow_when_text_input: bool = False,
        allow_when_offline: bool = True,
        add: str | None = None,
    ) -> None:
        """Bind one shortcut through runtime evaluator before handler execution."""

        definition = self._register_runtime_shortcut(
            binding_id=binding_id,
            sequence=sequence,
            intent=intent,
            modes=modes,
            allow_when_text_input=allow_when_text_input,
            allow_when_offline=allow_when_offline,
        )

        def _wrapped(event):
            context = self._build_runtime_context(event)
            can_execute, _reason = self._runtime_shortcuts.evaluate_runtime(definition, context)
            if not can_execute:
                return None
            return handler(event)

        if add is None:
            self.app.bind_all(sequence, _wrapped)
            return
        self.app.bind_all(sequence, _wrapped, add=add)

    def _build_shortcut_handler(self, entry, *, definition: KeyBindingDefinition | None = None):
        """Erzeugt Event-Handler fuer einen Shortcut-Guide-Eintrag."""

        effective_definition = definition
        if effective_definition is None:
            effective_definition = KeyBindingDefinition(
                binding_id=f"adhoc.{entry.intent}.{entry.key_sequence}",
                sequence=entry.key_sequence,
                intent=entry.intent,
                modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW),
                allow_when_text_input=True,
            )

        def _handler(event):
            context = self._build_runtime_context(event)
            can_execute, _reason = self._runtime_shortcuts.evaluate_runtime(effective_definition, context)
            if not can_execute:
                return None

            if self._has_active_popup() and UI_MODE_DIALOG not in effective_definition.modes:
                return "break"
            if entry.intent.startswith("toolbar.") and self._is_editable_widget(getattr(event, "widget", None)):
                return None
            payload = dict(entry.payload)
            if entry.from_shortcut:
                payload["from_shortcut"] = True
            if entry.intent in (
                UiIntent.SHORTCUT_EXPAND_SELECTED_ROW,
                UiIntent.SHORTCUT_COLLAPSE_SELECTED_ROW,
                UiIntent.SHORTCUT_CUT,
                UiIntent.SHORTCUT_COPY,
                UiIntent.SHORTCUT_PASTE,
                UiIntent.TOOLBAR_UNDO,
                UiIntent.TOOLBAR_REDO,
            ):
                payload["event"] = event
            return self._emit_intent(entry.intent, **payload)

        return _handler

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
        widgets.Checkbutton(
            toolbar,
            text="Offline simulieren",
            variable=self.app.shortcut_runtime_debug_offline_var,
            command=self._on_shortcut_runtime_offline_var_changed,
        ).pack(side="left", padx=(12, 0))
        widgets.Button(toolbar, text="Aktualisieren", command=self._refresh_shortcut_runtime_debug_dialog).pack(side="left", padx=(8, 0))

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
        """Sync offline flag from dialog checkbutton and refresh diagnostics."""

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
                    values=(mode, definition.sequence, definition.binding_id, status, "" if can_execute else reason),
                )

        total = active_count + disabled_count
        summary_var = getattr(self.app, "shortcut_runtime_debug_summary_var", None)
        if summary_var is not None:
            summary_var.set(
                f"Bindings: {total} total | {active_count} active | {disabled_count} disabled"
            )

    def _emit_intent(self, intent: str, **payload):
        """Leitet ein View-Ereignis als Intent an die Orchestrierung weiter."""
        return self.app._handle_ui_intent(intent, **payload)

    def _track_popup_window(self, window: ui.Toplevel, *, policy_id: str = "dialog.modal") -> None:
        """Register a popup immediately in the popup policy registry."""

        popup_id = str(window)
        if popup_id in self._tracked_popup_ids:
            return
        self._popup_registry.open_popup(popup_id=popup_id, title=str(window.title() or ""), policy_id=policy_id)
        self._tracked_popup_ids.add(popup_id)

    def _sync_popup_sessions_from_windows(self) -> None:
        """Synchronize tracked popup sessions with currently visible toplevel windows."""

        winfo_children = getattr(self.app, "winfo_children", None)
        if not callable(winfo_children):
            return

        visible_popup_ids: set[str] = set()
        for child in winfo_children():
            if not isinstance(child, ui.Toplevel):
                continue
            try:
                if not int(child.winfo_exists()):
                    continue
                if str(child.state()).lower() == "withdrawn":
                    continue
            except Exception:
                continue

            popup_id = str(child)
            visible_popup_ids.add(popup_id)
            if popup_id in self._tracked_popup_ids:
                continue
            self._popup_registry.open_popup(popup_id=popup_id, title=str(child.title() or ""), policy_id="dialog.modal")
            self._tracked_popup_ids.add(popup_id)

        stale_ids = self._tracked_popup_ids - visible_popup_ids
        for popup_id in tuple(stale_ids):
            self._popup_registry.close_popup(popup_id)
            self._tracked_popup_ids.discard(popup_id)

    def _has_active_popup(self) -> bool:
        """Return whether any modal popup is currently active."""

        self._sync_popup_sessions_from_windows()
        if self._popup_registry.has_mode_blocking_popup():
            return True
        return ScrollablePopupWindow.has_active_popup()

    def _on_global_click_commit_cell(self, event):
        """Meldet globalen Klick als Commit-Intent an den Orchestrator."""
        if self._has_active_popup():
            return "break"
        return self._emit_intent(UiIntent.GLOBAL_CLICK_COMMIT_CELL, event=event)

    def _on_tree_confirm_selection(self, _event):
        """Meldet Kurslisten-Bestätigung als Intent an den Orchestrator."""
        return self._emit_intent(UiIntent.COURSE_CONFIRM_SELECTION, event=_event)

    def _on_tree_hover_select(self, event):
        """Meldet Hover-Selektion der Kursliste als Intent an den Orchestrator."""
        return self._emit_intent(UiIntent.COURSE_HOVER_SELECT, event=event)

    def _on_tree_keyboard_navigation(self, _event):
        """Meldet Tastatur-Navigation in der Kursliste als Intent."""
        return self._emit_intent(UiIntent.COURSE_KEYBOARD_NAVIGATION, event=_event)

    def _on_detail_left(self, _event):
        """Meldet Shortcut für Spaltenfokus nach links als Intent."""
        if self._has_active_popup():
            return "break"
        return self._emit_intent(UiIntent.SHORTCUT_DETAIL_LEFT, event=_event)

    def _on_detail_right(self, _event):
        """Meldet Shortcut für Spaltenfokus nach rechts als Intent."""
        if self._has_active_popup():
            return "break"
        return self._emit_intent(UiIntent.SHORTCUT_DETAIL_RIGHT, event=_event)

    def _on_detail_left_all(self, _event):
        """Meldet Alt-Links für Spaltennavigation ohne Skip-Regeln."""
        if self._has_active_popup():
            return "break"
        return self._emit_intent(UiIntent.SHORTCUT_DETAIL_LEFT_ALL, event=_event)

    def _on_detail_right_all(self, _event):
        """Meldet Alt-Rechts für Spaltennavigation ohne Skip-Regeln."""
        if self._has_active_popup():
            return "break"
        return self._emit_intent(UiIntent.SHORTCUT_DETAIL_RIGHT_ALL, event=_event)

    def _on_grid_nav_up(self, _event):
        """Meldet Pfeil-hoch für Grid-Navigation im Zellauswahlmodus."""
        if self._has_active_popup():
            return "break"
        if int(getattr(_event, "state", 0)) & 0x0004:
            return None
        return self._emit_intent(UiIntent.GRID_NAV_UP, event=_event)

    def _on_grid_nav_down(self, _event):
        """Meldet Pfeil-runter für Grid-Navigation im Zellauswahlmodus."""
        if self._has_active_popup():
            return "break"
        if int(getattr(_event, "state", 0)) & 0x0004:
            return None
        return self._emit_intent(UiIntent.GRID_NAV_DOWN, event=_event)

    def _on_grid_enter(self, _event):
        """Meldet Enter für Übergänge zwischen Spalten-, Zell- und Edit-Modus."""
        if self._has_active_popup():
            return "break"
        return self._emit_intent(UiIntent.GRID_ENTER, event=_event)

    def _on_home(self, _event):
        """Leitet Home je nach Modus an Kurs- oder Grid-Navigation weiter."""
        if self._has_active_popup():
            return "break"
        if self._is_editable_widget(getattr(_event, "widget", None)):
            return None
        if bool(getattr(self.app, "is_detail_view", False)):
            return self._emit_intent(UiIntent.GRID_HOME, event=_event)
        return self._emit_intent(UiIntent.COURSE_HOME, event=_event)

    def _on_end(self, _event):
        """Leitet Ende je nach Modus an Kurs- oder Grid-Navigation weiter."""
        if self._has_active_popup():
            return "break"
        if self._is_editable_widget(getattr(_event, "widget", None)):
            return None
        if bool(getattr(self.app, "is_detail_view", False)):
            return self._emit_intent(UiIntent.GRID_END, event=_event)
        return self._emit_intent(UiIntent.COURSE_END, event=_event)

    @staticmethod
    def _is_editable_widget(widget) -> bool:
        if widget is None:
            return False
        editable_widget_types = (ui.Entry, ui.Text, ui.Spinbox, widgets.Entry, widgets.Combobox)
        return isinstance(widget, editable_widget_types)

    def _on_grid_delete(self, _event):
        """Meldet Delete/Backspace für Zellenleeren im Zellauswahlmodus."""
        if self._has_active_popup():
            return "break"
        return self._emit_intent(UiIntent.GRID_DELETE_CELL, event=_event)

    def _on_escape(self, _event):
        """Meldet Esc-Shortcut als Intent an den Orchestrator."""
        if self._has_active_popup():
            ScrollablePopupWindow.close_active_popup()
            self._sync_popup_sessions_from_windows()
            return "break"
        return self._emit_intent(UiIntent.SHORTCUT_ESCAPE, event=_event)

    def _on_ctrl_enter(self, _event):
        """Meldet Strg+Enter als expliziten Edit-Commit-Intent."""
        if self._has_active_popup():
            return None
        selection_level = getattr(getattr(self.app, "ui_state", None), "selection_level", "")
        column_level = getattr(getattr(self.app, "ui_state", None), "SELECTION_LEVEL_COLUMN", "column")
        if selection_level == column_level:
            return self._emit_intent(UiIntent.SHORTCUT_COMMIT_COLUMN, event=_event)
        return self._emit_intent(UiIntent.SHORTCUT_COMMIT_EDIT, event=_event)

    def show_course_overview(self):
        """Zeigt nur die Kursübersicht und blendet die Detailansicht aus."""
        pane = self.app.main_paned
        panes = set(str(item) for item in pane.panes())
        detail = str(self.app.detail_panel)
        course = str(self.app.course_panel)
        if detail in panes:
            pane.forget(self.app.detail_panel)
        panes = set(str(item) for item in pane.panes())
        if course not in panes:
            pane.add(self.app.course_panel, weight=1)
        self.app.is_detail_view = False
        self.app.overview_controller.ensure_course_selected(prefer_first=True)
        self.app.after_idle(self.app.lesson_tree.focus_set)

    def show_course_detail(self):
        """Zeigt nur die Detailansicht und blendet die Kursliste aus."""
        pane = self.app.main_paned
        panes = set(str(item) for item in pane.panes())
        course = str(self.app.course_panel)
        detail = str(self.app.detail_panel)
        if course in panes:
            pane.forget(self.app.course_panel)
        panes = set(str(item) for item in pane.panes())
        if detail not in panes:
            pane.add(self.app.detail_panel, weight=1)
        self.app.is_detail_view = True
        self.app.after_idle(self.app.grid_canvas.focus_set)

    def _on_ctrl_c(self, event):
        """Meldet globales Copy-Shortcut als Intent an den Orchestrator."""
        return self._emit_intent(UiIntent.SHORTCUT_COPY, event=event)

    def _on_ctrl_v(self, event):
        """Meldet globales Paste-Shortcut als Intent an den Orchestrator."""
        return self._emit_intent(UiIntent.SHORTCUT_PASTE, event=event)

    def _apply_theme(self):
        """Wendet das ausgewählte Theme auf Fenster und Grid-Canvas an."""
        theme_key = self.app.theme_var.get()
        apply_window_theme(self.app, theme_key)
        configure_ttk_theme(self.app, theme_key)
        if self._shared_menu_bar is not None:
            self._shared_menu_bar.refresh_theme(theme_key)
        self._apply_toolbar_icons()

        theme = get_theme(theme_key)
        self.app.fixed_canvas.configure(bg=theme.get("bg_surface", theme["bg_main"]))
        self.app.grid_canvas.configure(bg=theme.get("bg_surface", theme["bg_main"]))

