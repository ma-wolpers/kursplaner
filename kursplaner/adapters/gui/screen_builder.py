from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.dialogs import open_tabbed_settings_dialog as _open_tabbed_settings_dialog_contract_marker
from bw_gui.runtime import ui, widgets
from bw_gui.widgets import Switch

from bw_libs.ui_contract.keybinding import KeybindingRegistry
from bw_libs.ui_contract.popup import POPUP_KIND_MODAL, POPUP_KIND_NON_MODAL, PopupPolicy, PopupPolicyRegistry
from kursplaner.adapters.gui._screen_key_handlers import ScreenKeyHandlersMixin
from kursplaner.adapters.gui._screen_menus import ScreenMenusMixin
from kursplaner.adapters.gui._screen_shortcut_debug import ScreenShortcutDebugMixin
from kursplaner.adapters.gui._screen_shortcuts import ScreenShortcutsMixin
from kursplaner.adapters.gui._screen_toolbar import ScreenToolbarMixin
from kursplaner.adapters.gui.help_catalog import MAIN_WINDOW_HELP
from kursplaner.adapters.gui.hover_tooltip import HoverTooltip
from kursplaner.adapters.gui.search_overlay_view import SearchOverlayView
from kursplaner.adapters.gui.toolbar_viewmodel import (
    TOOLBAR_ACTIONS,
    TOOLBAR_SEPARATOR_SLOTS,
    TOOLBAR_SLOT_MIN_WIDTH,
    TOOLBAR_SLOT_ORDER,
)
from kursplaner.adapters.gui.ui_intents import UiIntent


class ScreenBuilder(ScreenKeyHandlersMixin, ScreenShortcutDebugMixin, ScreenShortcutsMixin, ScreenMenusMixin, ScreenToolbarMixin):
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
        self._intent_help_tooltips: list[tuple[HoverTooltip, str, str]] = []

    def build_ui(self, frame=None):
        """Erzeugt Widgets und verbindet UI-Events mit Adapter-Delegationspunkten."""
        root = widgets.Frame(frame if frame is not None else self.app, padding=16)
        root.pack(fill="both", expand=True)
        self._ensure_tooltip_store()
        self.app.action_buttons = {}
        self.app.action_help_tooltips = {}
        self.app.toolbar_slots = {}
        self.app.toolbar_separators = {}
        self.app.course_overview_buttons = {}
        self.app.course_overview_toggle_button = None

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

        paned = widgets.Panedwindow(root, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = widgets.Frame(paned)
        right = widgets.Frame(paned)
        paned.add(left, weight=1)
        paned.add(right, weight=3)
        self.app.main_paned = paned
        self.app.course_panel = left
        self.app.detail_panel = right

        overview_toolbar = widgets.Frame(left, style="Toolbar.TFrame")
        overview_toolbar.pack(fill="x", pady=(0, 6))
        self.app.course_overview_toolbar = overview_toolbar

        new_course_button = widgets.Button(
            overview_toolbar,
            text="Neuer Kurs",
            command=lambda: self._emit_intent(UiIntent.TOOLBAR_NEW, from_shortcut=False),
            style="Action.Primary.TButton",
            width=12,
        )
        new_course_button.pack(side="left")
        self.app.course_overview_buttons["new"] = new_course_button
        self._add_help(new_course_button, MAIN_WINDOW_HELP.get("course_overview_new", ""), intent=UiIntent.TOOLBAR_NEW)

        toggle_former_button = widgets.Button(
            overview_toolbar,
            text="Ehemalige anzeigen",
            command=lambda: self._emit_intent(UiIntent.COURSE_TOGGLE_SHOW_FORMER),
            style="Action.Utility.TButton",
            width=20,
        )
        toggle_former_button.pack(side="left", padx=(8, 0))
        self.app.course_overview_toggle_button = toggle_former_button
        self.app.course_overview_buttons["toggle_former"] = toggle_former_button
        self._add_help(
            toggle_former_button,
            MAIN_WINDOW_HELP.get("toggle_former_courses", ""),
            intent=UiIntent.COURSE_TOGGLE_SHOW_FORMER,
        )

        school_wide_cancellations_button = widgets.Button(
            overview_toolbar,
            text="Schulweite Ausfälle…",
            command=lambda: self._emit_intent(UiIntent.COURSE_OPEN_SCHOOL_WIDE_CANCELLATIONS),
            style="Action.Utility.TButton",
        )
        school_wide_cancellations_button.pack(side="left", padx=(8, 0))
        self.app.course_overview_buttons["school_wide_cancellations"] = school_wide_cancellations_button
        self._add_help(
            school_wide_cancellations_button,
            MAIN_WINDOW_HELP.get("school_wide_cancellations", ""),
            intent=UiIntent.COURSE_OPEN_SCHOOL_WIDE_CANCELLATIONS,
        )

        widgets.Label(left, textvariable=self.app.count_var, style="Toolbar.TLabel").pack(anchor="e", pady=(0, 6))

        detail_toolbar = widgets.Frame(right, style="Toolbar.TFrame")
        detail_toolbar.pack(fill="x", pady=(0, 2))
        self.app.toolbar_frame = detail_toolbar
        for slot_key in TOOLBAR_SLOT_ORDER:
            slot = widgets.Frame(detail_toolbar, style="Toolbar.TFrame")
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

        styler = getattr(self.app, "toolbar_icon_styler", None)
        for spec in TOOLBAR_ACTIONS:
            slot = self.app.toolbar_slots[spec.slot_key]
            command = lambda intent=spec.intent, payload=spec.payload: self._emit_intent(intent, **dict(payload))
            button = styler.create_button(slot, spec, command) if styler is not None else None
            if button is None:
                button_kwargs: dict = {
                    "text": spec.text,
                    "command": command,
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

        self._layout_toolbar_slots()
        detail_toolbar.bind("<Configure>", self._on_toolbar_configure)

        overview_columns = ("name", "stufe", "next_topic", "next_unit", "remaining_hours", "next_lzk", "next_ub")
        tree_frame = widgets.Frame(left)
        tree_frame.pack(fill="both", expand=True)

        self.app.lesson_tree = widgets.Treeview(tree_frame, columns=overview_columns, show="headings")
        self.app.lesson_tree.heading("name", text="Kurs")
        self.app.lesson_tree.heading("stufe", text="Stufe")
        self.app.lesson_tree.heading("next_topic", text="Nächstes Thema")
        self.app.lesson_tree.heading("next_unit", text="Nächste Einheit")
        self.app.lesson_tree.heading("remaining_hours", text="Reststunden")
        self.app.lesson_tree.heading("next_lzk", text="Nächste LZK")
        self.app.lesson_tree.heading("next_ub", text="Nächster UB")
        self.app.lesson_tree.column("name", width=220, anchor="w")
        self.app.lesson_tree.column("stufe", width=55, anchor="center")
        self.app.lesson_tree.column("next_topic", width=240, anchor="w")
        self.app.lesson_tree.column("next_unit", width=120, anchor="center")
        self.app.lesson_tree.column("remaining_hours", width=90, anchor="center")
        self.app.lesson_tree.column("next_lzk", width=110, anchor="center")
        self.app.lesson_tree.column("next_ub", width=130, anchor="center")

        tree_scroll = widgets.Scrollbar(tree_frame, orient="vertical", command=self.app.lesson_tree.yview)
        self.app.lesson_tree.configure(yscrollcommand=tree_scroll.set)

        self.app.lesson_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self._add_help(self.app.lesson_tree, MAIN_WINDOW_HELP["lesson_tree"])

        self.app.lesson_tree.bind("<Return>", self._on_tree_enter)
        self.app.lesson_tree.bind("<KP_Enter>", self._on_tree_enter)
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

        auto_mode_check = Switch(
            mode_bar,
            text="Auto je Spalte",
            variable=self.app.auto_row_mode_var,
            on_change=lambda _auto: self._emit_intent(UiIntent.TOGGLE_AUTO_ROW_MODE),
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

        row_filter_btn = widgets.Button(
            mode_bar,
            text="Zeilenfelder…",
            command=lambda: self._emit_intent(UiIntent.OPEN_ROW_FILTER_SETTINGS),
            style="Action.Utility.TButton",
        )
        row_filter_btn.pack(side="left", padx=(6, 0))
        self.app.action_buttons["row_filter"] = row_filter_btn

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

        y_scroll = widgets.Scrollbar(editor_frame, orient="vertical", command=self.app._on_vertical_scroll)
        self.app.x_scroll = widgets.Scrollbar(editor_frame, orient="horizontal", command=self.app._on_horizontal_scroll)
        self.app.grid_canvas.configure(yscrollcommand=y_scroll.set, xscrollcommand=self.app.viewport_sync_h.on_view_changed)
        y_scroll.grid(row=1, column=2, sticky="ns")
        self.app.x_scroll.grid(row=2, column=1, sticky="ew")

        self.app.search_overlay_view = SearchOverlayView(self.app, editor_frame)

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

        self.refresh_course_overview_toolbar()
        self.show_course_overview()


