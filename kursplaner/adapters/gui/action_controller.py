from __future__ import annotations

import pathlib
import tkinter as tk
from datetime import date
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable

from kursplaner.adapters.gui.column_visibility_dialog import ask_column_visibility
from kursplaner.adapters.gui.export_selection_dialog import ask_export_selection
from kursplaner.adapters.gui.help_catalog import MAIN_WINDOW_HELP, SHADOW_LESSONS_HELP
from kursplaner.adapters.gui.hover_tooltip import HoverTooltip
from kursplaner.adapters.gui.new_lesson_window import NewLessonWindow
from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.adapters.gui.shortcut_guide import load_shortcut_guide_entries
from kursplaner.adapters.gui.shortcut_overview_dialog import ShortcutOverviewDialog
from kursplaner.adapters.gui.toolbar_viewmodel import (
    TOOLBAR_ACTION_BY_KEY,
    TOOLBAR_SEPARATOR_SLOTS,
    TOOLBAR_SLOT_ORDER,
    ToolbarActionView,
    ToolbarViewModel,
    build_toolbar_view_model,
)
from kursplaner.adapters.gui.ub_mark_dialog import ask_mark_unit_as_ub
from kursplaner.adapters.gui.ui_theme import get_theme
from kursplaner.core.config.path_store import CALENDAR_DIR_KEY, resolve_path_value
from kursplaner.core.domain.lesson_directory import resolve_lesson_dir
from kursplaner.core.domain.models import StartRequest, StartResult
from kursplaner.core.flows.lesson_transfer_flow import LessonTransferFlowWriteRequest


class MainWindowActionController:
    """Kapselt allgemeine GUI-Aktionen der Hauptansicht.

    Enthält nur Adapterlogik (Dialoge/Validierung/Delegation), keine Fachregeln.
    """

    ACHIEVEMENT_COLORS_LIGHT: dict[str, str] = {
        "half": "#B8BDC9",
        "full": "#D4AF37",
        "ubplus": "#1E3A8A",
        "bub": "#8B1A5A",
    }
    ACHIEVEMENT_COLORS_DARK: dict[str, str] = {
        "half": "#D0D5DF",
        "full": "#E3C257",
        "ubplus": "#5B7FD9",
        "bub": "#C04E8C",
    }

    def __init__(self, app):
        """Speichert den App-Adapter als Delegationsziel für UI-Aktionen."""
        self.app = app
        self._achievement_icons: dict[str, tk.PhotoImage] = {}
        deps = getattr(app, "gui_dependencies", None)
        if deps is None:
            raise RuntimeError("GUI Dependencies not available on app")
        self._lesson_transfer = deps.lesson_transfer
        self._lesson_transfer_flow = deps.lesson_transfer_flow
        self._find_markdown_for_selected_uc = deps.find_markdown_for_selected
        self._clear_selected_lesson_uc = deps.clear_selected_lesson
        self._split_selected_unit_uc = deps.split_selected_unit
        self._merge_selected_units_uc = deps.merge_selected_units
        self._restore_selected_from_cancel_uc = deps.restore_selected_from_cancel
        self._rename_linked_file_for_row_uc = deps.rename_linked_file_for_row
        self._action_button_state_uc = deps.action_button_state_usecase
        self._history_uc = deps.history_usecase
        self._tracked_write_uc = deps.tracked_write_usecase
        self._extend_plan_to_next_vacation_uc = deps.extend_plan_to_next_vacation_usecase
        self._export_topic_units_pdf_uc = deps.export_topic_units_pdf_usecase
        self._export_topic_units_markdown_uc = deps.export_topic_units_markdown_usecase
        self._export_expected_horizon_pdf_uc = deps.export_expected_horizon_pdf_usecase
        self._export_expected_horizon_markdown_uc = deps.export_expected_horizon_markdown_usecase
        self._export_lzk_expected_horizon_uc = deps.export_lzk_expected_horizon_usecase
        self._mark_unit_as_ub_uc = deps.mark_unit_as_ub_usecase
        self._remove_unit_ub_link_uc = deps.remove_unit_ub_link_usecase
        self._query_ub_achievements_uc = deps.query_ub_achievements_usecase
        self._load_last_ub_insights_uc = deps.load_last_ub_insights_usecase

    @staticmethod
    def _workspace_root_from_path(path: pathlib.Path) -> pathlib.Path:
        """Leitet den Workspace-Stamm robust aus einem Projektpfad ab."""
        resolved = path.expanduser().resolve()
        for parent in (resolved, *resolved.parents):
            if parent.name == "7thCloud":
                return parent
        return resolved.anchor and pathlib.Path(resolved.anchor) or resolved.parent

    @staticmethod
    def _achievement_icon_dir() -> pathlib.Path:
        return pathlib.Path(__file__).resolve().parents[3] / "assets" / "achievements"

    @staticmethod
    def _achievement_icon_file_by_domain() -> dict[str, str]:
        return {
            "Pädagogik": "ac_paedagogik.png",
            "Mathematik": "ac_mathematik.png",
            "Informatik": "ac_informatik.png",
            "Darstellendes Spiel": "ac_darstellendes_spiel.png",
        }

    def _achievement_icon_for_domain(self, domain: str) -> tk.PhotoImage | None:
        key = str(domain or "").strip()
        if not key:
            return None
        cached = self._achievement_icons.get(key)
        if cached is not None:
            return cached

        filename = self._achievement_icon_file_by_domain().get(key)
        if not filename:
            return None

        icon_path = self._achievement_icon_dir() / filename
        if not icon_path.exists() or not icon_path.is_file():
            return None

        try:
            icon = tk.PhotoImage(file=str(icon_path))
        except tk.TclError:
            return None

        max_size = 24
        width = int(icon.width())
        height = int(icon.height())
        max_dim = max(width, height)
        factor = max(1, max_dim // max_size)
        if factor > 1:
            try:
                icon = icon.subsample(factor)
            except tk.TclError:
                pass

        self._achievement_icons[key] = icon
        return icon

    def pick_base_dir(self):
        """Delegiert die Auswahl des Unterrichtsordners an den Pfad-Controller."""
        self.app.path_settings_controller.pick_base_dir()

    def apply_saved_paths(self, values: dict[str, str]):
        """Übernimmt persistierte Pfadwerte in den laufenden UI-Zustand."""
        self.app.path_settings_controller.apply_saved_paths(values)

    def archive_dir(self) -> pathlib.Path:
        """Liefert den aktuell berechneten Archivordner der Anwendung."""
        return self.app.path_settings_controller.archive_dir()

    def auto_archive_enabled(self) -> bool:
        """Liefert, ob automatisches Archivieren aktiv ist."""
        return self.app.path_settings_controller.auto_archive_enabled()

    def open_settings_window(self):
        """Öffnet den Settings-Dialog über den dedizierten Pfad-Controller."""
        self.app.path_settings_controller.open_settings_window()

    def open_column_visibility_settings(self):
        """Öffnet den Dialog zum Ein-/Ausblenden von Spaltenarten."""
        settings = ask_column_visibility(
            self.app,
            current=self.app.column_visibility_settings,
            theme_key=self.app.theme_var.get(),
        )
        if settings is None:
            return
        self.app._set_column_visibility_settings(settings)

    def on_paths_saved(self, values: dict[str, str]):
        """Reagiert auf gespeicherte Pfade und triggert nachgelagerte Updates."""
        self.app.path_settings_controller.on_paths_saved(values)

    def refresh_overview(self):
        """Delegiert das Neuladen der Unterrichtsübersicht an den Overview-Controller."""
        self.app.overview_controller.refresh_overview()

    def open_new_lesson_window(self):
        """Öffnet den Dialog zur Anlage neuer Unterrichtseinheiten."""
        window = NewLessonWindow(
            self.app,
            on_success=self.app.refresh_overview,
            on_paths_changed=self.app._on_paths_saved,
            theme_key=self.app.theme_var.get(),
            form_usecase=self.app.new_lesson_form_usecase,
            new_lesson_usecase=self.app.new_lesson_usecase,
            path_settings_usecase=self.app.path_settings_usecase,
            create_lesson_action=self.create_new_lesson_tracked,
        )
        window.after_idle(window.grab_set)

    def create_new_lesson_tracked(
        self,
        request: StartRequest,
        confirm_change: Callable[[str, str], bool],
    ) -> StartResult:
        """Führt den New-Lesson-Write-Flow mit History-Tracking aus."""
        expected_dir = (request.base_dir / request.folder_name).expanduser().resolve()
        expected_markdown = (expected_dir / f"{request.folder_name}.md").expanduser().resolve()

        def _action() -> StartResult:
            return self.app.new_lesson_usecase.execute(request, confirm_change=confirm_change)

        return self._tracked_write_uc.run_tracked_action(
            label="Unterricht anlegen",
            action=_action,
            table=None,
            day_columns=[],
            selected_day_indices=set(),
            extra_before=[expected_dir, expected_markdown],
            extra_after_from_result=lambda result: [result.lesson_dir, result.lesson_markdown],
        )

    def _collect_shadow_lesson_files(self) -> list[pathlib.Path]:
        """Sammelt unverkettete Dateien aus dem Einheiten-Ordner des aktiven Plans."""
        table = self.app.current_table
        if table is None:
            return []

        lesson_dir = resolve_lesson_dir(table.markdown_path.parent, create_if_missing=False)
        if not lesson_dir.exists() or not lesson_dir.is_dir():
            return []

        linked_paths: set[pathlib.Path] = set()
        for row_index in range(len(table.rows)):
            link = self._lesson_transfer.resolve_existing_link(table, row_index)
            if isinstance(link, pathlib.Path) and link.exists() and link.is_file():
                linked_paths.add(link.resolve())

        shadow_files: list[pathlib.Path] = []
        for candidate in sorted(lesson_dir.glob("*.md"), key=lambda item: item.name.lower()):
            if not candidate.is_file():
                continue
            resolved = candidate.resolve()
            if resolved in linked_paths:
                continue
            shadow_files.append(resolved)

        return shadow_files

    def _shadow_preview_text(self, path: pathlib.Path) -> str:
        """Lädt den vollständigen Markdown-Inhalt einer Schatteneinheit inkl. YAML."""
        try:
            return path.read_text(encoding="utf-8")
        except Exception as exc:
            return f"Datei konnte nicht gelesen werden:\n{path}\n\n{exc}"

    def show_shadow_lessons(self):
        """Zeigt eine Liste unverketteter Einheiten an und bietet Copy/Paste-Hilfen."""
        if self.app.current_table is None:
            messagebox.showinfo("Schatteneinheiten", "Kein Kursplan geladen.", parent=self.app)
            return

        shadow_files = self._collect_shadow_lesson_files()
        if not shadow_files:
            messagebox.showinfo("Schatteneinheiten", "Keine Schatteneinheiten gefunden.", parent=self.app)
            return

        dialog = ScrollablePopupWindow(
            self.app,
            title="Schatteneinheiten",
            geometry="1080x460",
            minsize=(860, 340),
            theme_key=self.app.theme_var.get(),
        )
        dialog.apply_theme()
        dialog._hover_tooltips = []

        root = ttk.Frame(dialog.content, padding=12)
        root.pack(fill="both", expand=True)

        ttk.Label(
            root,
            text="Nicht verlinkte Dateien im Einheiten-Ordner. Rechts wird der volle Markdown-Inhalt (inkl. YAML) angezeigt.",
        ).pack(fill="x", pady=(0, 8))

        body = ttk.Panedwindow(root, orient="horizontal")
        body.pack(fill="both", expand=True)

        list_frame = ttk.Frame(body)
        preview_frame = ttk.Frame(body)
        body.add(list_frame, weight=1)
        body.add(preview_frame, weight=2)

        listbox = tk.Listbox(list_frame, exportselection=False)
        listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
        scroll.pack(side="right", fill="y")
        listbox.configure(yscrollcommand=scroll.set)

        preview = tk.Text(preview_frame, wrap="none", state="disabled")
        preview.pack(side="left", fill="both", expand=True)
        preview_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=preview.yview)
        preview_scroll.pack(side="right", fill="y")
        preview_scroll_x = ttk.Scrollbar(preview_frame, orient="horizontal", command=preview.xview)
        preview_scroll_x.pack(side="bottom", fill="x")
        preview.configure(yscrollcommand=preview_scroll.set, xscrollcommand=preview_scroll_x.set)
        dialog._hover_tooltips.append(HoverTooltip(listbox, SHADOW_LESSONS_HELP["list"]))
        dialog._hover_tooltips.append(HoverTooltip(preview, SHADOW_LESSONS_HELP["preview"]))

        for path in shadow_files:
            listbox.insert(tk.END, path.name)
        listbox.selection_set(0)
        listbox.activate(0)

        status_var = tk.StringVar(value="")
        ttk.Label(root, textvariable=status_var).pack(fill="x", pady=(8, 0))

        def _selected_path() -> pathlib.Path | None:
            current = listbox.curselection()
            if not current:
                return None
            idx = current[0]
            if not (0 <= idx < len(shadow_files)):
                return None
            return shadow_files[idx]

        def _refresh_preview() -> None:
            selected = _selected_path()
            if not isinstance(selected, pathlib.Path):
                return
            text = self._shadow_preview_text(selected)
            preview.configure(state="normal")
            preview.delete("1.0", "end")
            preview.insert("1.0", text)
            preview.configure(state="disabled")

        listbox.bind("<<ListboxSelect>>", lambda _event: _refresh_preview())
        _refresh_preview()

        def _set_as_clipboard_lesson():
            selected = _selected_path()
            if not isinstance(selected, pathlib.Path):
                status_var.set("Keine Datei ausgewählt.")
                return
            self.app.clipboard_lesson_path = selected
            self.update_action_controls()
            status_var.set(f"Als Kopie gesetzt: {selected.name}")

        def _copy_selected_path():
            selected = _selected_path()
            if not isinstance(selected, pathlib.Path):
                status_var.set("Keine Datei ausgewählt.")
                return
            self.app.clipboard_clear()
            self.app.clipboard_append(str(selected))
            status_var.set(f"Pfad kopiert: {selected}")

        buttons = ttk.Frame(root)
        buttons.pack(fill="x", pady=(10, 0))
        set_clipboard_btn = ttk.Button(buttons, text="Als Kopie setzen", command=_set_as_clipboard_lesson)
        set_clipboard_btn.pack(side="left")
        copy_path_btn = ttk.Button(buttons, text="Pfad kopieren", command=_copy_selected_path)
        copy_path_btn.pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Schließen", command=dialog.destroy).pack(side="right")
        dialog._hover_tooltips.append(HoverTooltip(set_clipboard_btn, SHADOW_LESSONS_HELP["set_clipboard"]))
        dialog._hover_tooltips.append(HoverTooltip(copy_path_btn, SHADOW_LESSONS_HELP["copy_path"]))

        dialog.grab_set()

    def show_shortcut_overview(self):
        """Öffnet eine Übersicht aller Strg-Shortcuts inklusive Merkregeln."""
        try:
            entries = load_shortcut_guide_entries()
        except Exception as exc:
            messagebox.showerror("Shortcut-Übersicht", str(exc), parent=self.app)
            return

        dialog = ShortcutOverviewDialog(
            self.app,
            entries=entries,
            theme_key=self.app.theme_var.get(),
        )
        dialog.apply_theme()
        dialog.grab_set()

    def clear_plan_table(self, title: str):
        """Setzt die rechte Planansicht in einen leeren/neutralen Zustand."""
        self.app.overview_controller.clear_plan_table(title)

    def mark_selected_as_ub(self):
        """Markiert eine Einheit als UB oder entfernt eine bestehende UB-Verknüpfung."""
        context = self._single_selection_context()
        if context is None or self.app.current_table is None:
            return
        selected_index, row_index, day = context

        lesson_yaml = day.get("yaml") if isinstance(day, dict) else {}
        ub_link = ""
        if isinstance(lesson_yaml, dict):
            ub_link = str(lesson_yaml.get("Unterrichtsbesuch", "")).strip()

        workspace_root = self._workspace_root_from_path(self.app.current_table.markdown_path)

        if ub_link:
            delete_ub_markdown = messagebox.askyesno(
                "Unterrichtsbesuch-Datei löschen",
                "Soll die verknüpfte UB-Datei ebenfalls gelöscht werden?\n"
                "(Nein entfernt nur die Verknüpfung in der Einheit.)",
                parent=self.app,
            )

            try:
                result = self._run_tracked_write(
                    label="Unterrichtsbesuch-Verknüpfung entfernen",
                    action=lambda: self._remove_unit_ub_link_uc.execute(
                        workspace_root=workspace_root,
                        table=self.app.current_table,
                        row_index=row_index,
                        delete_ub_markdown=delete_ub_markdown,
                    ),
                    extra_after_from_result=lambda item: [
                        path
                        for path in (
                            getattr(item, "lesson_path", None),
                            getattr(item, "ub_path", None),
                            getattr(item, "overview_path", None),
                        )
                        if isinstance(path, pathlib.Path)
                    ],
                )
            except Exception as exc:
                messagebox.showerror("Unterrichtsbesuch", str(exc), parent=self.app)
                return

            if not result.proceed:
                messagebox.showerror(
                    "Unterrichtsbesuch",
                    result.error_message or "UB-Verknüpfung konnte nicht entfernt werden.",
                    parent=self.app,
                )
                return

            self._refresh_after_write(selected_index=selected_index)
            return

        dialog_result = ask_mark_unit_as_ub(self.app, theme_key=self.app.theme_var.get())
        if dialog_result is None:
            return

        try:
            result = self._run_tracked_write(
                label="Unterrichtsbesuch markieren",
                action=lambda: self._mark_unit_as_ub_uc.execute(
                    workspace_root=workspace_root,
                    table=self.app.current_table,
                    row_index=row_index,
                    ub_kinds=dialog_result.ub_kinds,
                    langentwurf=dialog_result.langentwurf,
                    beobachtungsschwerpunkt=dialog_result.beobachtungsschwerpunkt,
                ),
                extra_after_from_result=lambda item: [
                    path
                    for path in (
                        getattr(item, "lesson_path", None),
                        getattr(item, "ub_path", None),
                        getattr(item, "overview_path", None),
                    )
                    if isinstance(path, pathlib.Path)
                ],
            )
        except Exception as exc:
            messagebox.showerror("Unterrichtsbesuch", str(exc), parent=self.app)
            return

        if not result.proceed:
            messagebox.showerror(
                "Unterrichtsbesuch",
                result.error_message or "UB-Markierung fehlgeschlagen.",
                parent=self.app,
            )
            return

        self._refresh_after_write(selected_index=selected_index)

    @staticmethod
    def _is_dark_hex(color: str) -> bool:
        """Bestimmt anhand der Luminanz, ob eine Hex-Farbe dunkel ist."""
        text = str(color or "").strip().lstrip("#")
        if len(text) != 6:
            return False
        red = int(text[0:2], 16)
        green = int(text[2:4], 16)
        blue = int(text[4:6], 16)
        luminance = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255.0
        return luminance < 0.45

    @staticmethod
    def _hex_to_rgb(color: str) -> tuple[int, int, int]:
        text = str(color or "").strip().lstrip("#")
        if len(text) != 6:
            return (0, 0, 0)
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))

    @classmethod
    def _color_distance(cls, color_a: str, color_b: str) -> int:
        ax, ay, az = cls._hex_to_rgb(color_a)
        bx, by, bz = cls._hex_to_rgb(color_b)
        return abs(ax - bx) + abs(ay - by) + abs(az - bz)

    def _draw_progress_ring(
        self,
        parent,
        *,
        title: str,
        domain: str,
        current: int,
        target: int,
        tooltip: str,
        symbol: str,
        category: str,
        is_fulfilled: bool,
        tooltip_store: list[HoverTooltip] | None = None,
    ):
        """Rendert eine Achievement-Kachel mit Ring, Symbol, Label und Hover-Erklärung."""
        frame = ttk.Frame(parent, padding=(4, 4))
        canvas = tk.Canvas(frame, width=92, height=92, highlightthickness=0, bg="#000000", bd=0)
        canvas.pack()

        total = max(1, int(target))
        value = max(0, min(int(current), total))
        ratio = value / float(total)
        extent = int(360 * ratio)
        if value == 0:
            extent = max(extent, int(360 * 0.05))

        theme = get_theme(self.app.theme_var.get())
        is_dark = self._is_dark_hex(str(theme.get("bg_main", "#FFFFFF")))
        category_colors = self.ACHIEVEMENT_COLORS_DARK if is_dark else self.ACHIEVEMENT_COLORS_LIGHT
        progress_color = category_colors.get(str(category), category_colors["half"])
        muted_symbol = "#6B7280" if not is_dark else "#7E8794"
        center_bg = str(theme.get("bg_surface", "#FFFFFF"))
        ring_bg = str(theme.get("border", "#C5CCD8"))
        if self._color_distance(progress_color, ring_bg) < 96:
            ring_bg = "#4B5563" if is_dark else "#E5EAF1"
        center_fg = progress_color if is_fulfilled else muted_symbol
        canvas.configure(bg=center_bg)

        center = 46
        radius = 34
        canvas.create_oval(
            center - radius,
            center - radius,
            center + radius,
            center + radius,
            outline=ring_bg,
            width=8,
        )
        canvas.create_arc(
            center - radius,
            center - radius,
            center + radius,
            center + radius,
            start=90,
            extent=-extent,
            outline=progress_color,
            width=8,
            style="arc",
        )

        symbol_radius = 18
        canvas.create_oval(
            center - symbol_radius,
            center - symbol_radius,
            center + symbol_radius,
            center + symbol_radius,
            fill=center_bg,
            outline=ring_bg,
            width=1,
        )
        icon = self._achievement_icon_for_domain(domain)
        if icon is not None:
            canvas.create_image(center, center - 2, image=icon)
        else:
            canvas.create_text(center, center - 2, text=symbol, font=("Segoe UI", 14, "bold"), fill=center_fg)

        # Always show the numeric progress to keep the goal state glanceable.
        progress_fg = progress_color if is_fulfilled else muted_symbol
        canvas.create_text(
            center,
            center + 22,
            text=f"{value}/{total}",
            font=("Segoe UI", 9, "bold"),
            fill=progress_fg,
        )

        title_label = ttk.Label(
            frame,
            text=title,
            anchor="center",
            justify="center",
            wraplength=140,
        )
        title_label.pack(fill="x", pady=(4, 0))

        tile_tooltip = HoverTooltip(frame, tooltip)
        tile_tooltip.bind_widget(canvas)
        tile_tooltip.bind_widget(title_label)
        if isinstance(tooltip_store, list):
            tooltip_store.append(tile_tooltip)
        return frame

    def _active_subject_name(self) -> str:
        """Liest das aktive Kursfach aus dem aktuellen Plankontext."""
        table = self.app.current_table
        if table is None:
            return "Informatik"
        subject = str(table.metadata.get("Kursfach", "")).strip()
        return subject or "Informatik"

    def _workspace_root_for_ub_view(self) -> pathlib.Path | None:
        """Ermittelt den Workspace-Stamm für die globale UB-Ansicht."""
        if self.app.current_table is not None:
            return self._workspace_root_from_path(self.app.current_table.markdown_path)

        base_dir_text = str(self.app.base_dir_var.get()).strip()
        if base_dir_text:
            return self._workspace_root_from_path(resolve_path_value(base_dir_text))

        path_settings_usecase = getattr(self.app, "path_settings_usecase", None)
        unterricht_key = getattr(path_settings_usecase, "UNTERRICHT_KEY", "")
        if unterricht_key:
            raw_unterricht = str(self.app.path_values.get(unterricht_key, "")).strip()
            if raw_unterricht:
                return self._workspace_root_from_path(resolve_path_value(raw_unterricht))

        messagebox.showinfo(
            "UB-Ansicht",
            "Kein Unterrichtspfad gefunden. Bitte in den Einstellungen den Kursordner setzen.",
            parent=self.app,
        )
        self.open_settings_window()
        return None

    def toggle_resume_or_mark_ub(self):
        """Führt kontextsensitiv Ausfall-Rücknahme oder UB-Markierung aus."""
        context = self._single_selection_context()
        if context is None:
            return
        _, _, day = context
        if bool(day.get("is_cancel", False)):
            self.restore_selected_from_cancel_action()
            return
        self.mark_selected_as_ub()

    def show_ub_achievements_view(self):
        """Öffnet die UB-Ansicht mit Fortschrittsringen und letzten Entwicklungsimpulsen."""
        workspace_root = self._workspace_root_for_ub_view()
        if workspace_root is None:
            return

        try:
            achievements = self._query_ub_achievements_uc.execute(workspace_root=workspace_root)
            insights = self._load_last_ub_insights_uc.execute(
                workspace_root=workspace_root,
                subject_name=self._active_subject_name(),
            )
        except Exception as exc:
            messagebox.showerror("UB-Ansicht", str(exc), parent=self.app)
            return

        dialog = ScrollablePopupWindow(
            self.app,
            title="UB-Ansicht",
            geometry="980x640",
            minsize=(760, 480),
            theme_key=self.app.theme_var.get(),
        )
        dialog.apply_theme()
        dialog._hover_tooltips = []
        root = ttk.Frame(dialog.content, padding=12)
        root.pack(fill="both", expand=True)

        ttk.Label(
            root,
            text="Kursübergreifender UB-Fortschritt (gesamt)",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        rings_wrap = ttk.Frame(root)
        rings_wrap.pack(fill="x")

        for idx, item in enumerate(achievements.items):
            ring = self._draw_progress_ring(
                rings_wrap,
                title=str(item.title),
                domain=str(item.domain),
                current=int(item.current),
                target=int(item.target),
                tooltip=str(item.tooltip),
                symbol=str(item.symbol),
                category=str(item.category),
                is_fulfilled=bool(item.is_fulfilled),
                tooltip_store=dialog._hover_tooltips,
            )
            ring.grid(row=idx // 4, column=idx % 4, padx=8, pady=8, sticky="n")

        insights_frame = ttk.LabelFrame(root, text="Letzte Entwicklungsimpulse", padding=10)
        insights_frame.pack(fill="both", expand=True, pady=(10, 0))

        def _format_list(items: list[str]) -> str:
            cleaned = [str(entry).strip() for entry in items if str(entry).strip()]
            if not cleaned:
                return "-"
            return "\n".join(f"- {entry}" for entry in cleaned)

        sections: list[tuple[str, list[str]]] = []
        for domain in insights.domain_sections:
            sections.append((f"{domain.domain_name} - Professionalisierungsschritte", domain.steps))
            sections.append((f"{domain.domain_name} - Nutzbare Ressourcen", domain.resources))

        if not sections:
            sections = [
                ("Pädagogik - Professionalisierungsschritte", insights.paedagogik_steps),
                ("Pädagogik - Nutzbare Ressourcen", insights.paedagogik_resources),
            ]

        for title, values in sections:
            section = ttk.Frame(insights_frame)
            section.pack(fill="x", pady=(0, 8))
            ttk.Label(section, text=title, font=("Segoe UI", 10, "bold")).pack(anchor="w")
            ttk.Label(section, text=_format_list(values), justify="left", wraplength=880).pack(anchor="w")

        dialog.grab_set()

    def rebuild_lesson_index(self):
        """Führt einen manuellen Lesson-Index-Rebuild über den Wartungs-Use-Case aus."""
        base_dir_text = self.app.base_dir_var.get().strip()
        if not base_dir_text:
            messagebox.showwarning("Lesson-Index", "Kein Kursordner konfiguriert.", parent=self.app)
            return

        base_dir = pathlib.Path(base_dir_text).expanduser().resolve()
        if not base_dir.exists() or not base_dir.is_dir():
            messagebox.showerror("Lesson-Index", f"Kursordner nicht gefunden:\n{base_dir}", parent=self.app)
            return

        try:
            self.app.gui_dependencies.rebuild_lesson_index.execute(base_dir)
            messagebox.showinfo("Lesson-Index", "Lesson-Index erfolgreich neu aufgebaut.", parent=self.app)
        except Exception as exc:
            messagebox.showerror("Lesson-Index", f"Rebuild fehlgeschlagen:\n{exc}", parent=self.app)

    def _single_selection_context(self) -> tuple[int, int, dict[str, object]] | None:
        if self.app.current_table is None:
            return None
        selected_index = self.app._get_single_selected_or_warn()
        if selected_index is None:
            return None
        day = self.app.day_columns[selected_index]
        row_index = self.app._to_int(day.get("row_index", 0), 0)
        return selected_index, row_index, day

    def _refresh_after_write(self, *, selected_index: int | None = None) -> None:
        self.app._collect_day_columns()
        if isinstance(selected_index, int) and 0 <= selected_index < len(self.app.day_columns):
            self.app.selected_day_indices = {selected_index}
            self.app._update_selected_column_label()
        self.app._refresh_grid_content()
        self.app._update_selected_lesson_metrics()
        self.update_action_controls()

    def _run_tracked_write(
        self,
        *,
        label: str,
        action,
        extra_before: list[pathlib.Path] | None = None,
        extra_after: list[pathlib.Path] | None = None,
        extra_after_from_result=None,
    ):
        if self.app.current_table is None:
            return action()
        return self._tracked_write_uc.run_tracked_action(
            label=label,
            action=action,
            table=self.app.current_table,
            day_columns=self.app.day_columns,
            selected_day_indices=self.app.selected_day_indices,
            extra_before=extra_before,
            extra_after=extra_after,
            extra_after_from_result=extra_after_from_result,
        )

    def _set_slot_visibility(self, slot_key: str, visible: bool) -> None:
        slots = getattr(self.app, "toolbar_slots", None)
        if not isinstance(slots, dict):
            return
        slot = slots.get(slot_key)
        if slot is None:
            return
        manager = str(slot.winfo_manager())
        if manager == "grid":
            if visible:
                slot.grid()
            else:
                slot.grid_remove()
            return
        # Toolbar slots are laid out via ScreenBuilder._layout_toolbar_slots using grid.
        # Never fallback to pack() here, otherwise Tk raises a geometry-manager conflict.
        if not manager:
            return
        raise RuntimeError(f"Toolbar-Slot '{slot_key}' uses unexpected geometry manager '{manager}'. Expected 'grid'.")

    def _apply_toolbar_view_model(self, toolbar_vm) -> set[str]:
        buttons = getattr(self.app, "action_buttons", None)
        if not isinstance(buttons, dict):
            return set()

        visible_actions: set[str] = set()
        for action_key, view in toolbar_vm.actions.items():
            button = buttons.get(action_key)
            if button is None:
                continue
            definition = TOOLBAR_ACTION_BY_KEY.get(action_key)
            slot_key = definition.slot_key if definition is not None else action_key
            self._set_slot_visibility(slot_key, True)
            button.state(["!disabled"] if view.enabled else ["disabled"])
            if view.enabled:
                visible_actions.add(action_key)

        for separator_slot in TOOLBAR_SEPARATOR_SLOTS:
            self._set_slot_visibility(separator_slot, True)

        for slot_key in TOOLBAR_SLOT_ORDER:
            if slot_key in TOOLBAR_SEPARATOR_SLOTS:
                continue
            if slot_key in TOOLBAR_ACTION_BY_KEY:
                continue
            self._set_slot_visibility(slot_key, True)

        styler = getattr(self.app, "toolbar_icon_styler", None)
        if styler is not None:
            styler.apply(self.app.theme_var.get())

        self._update_contextual_toolbar_help()

        return visible_actions

    def _update_contextual_toolbar_help(self) -> None:
        """Passt kontextabhängige Toolbar-Hovertexte (z. B. Ausfall/Resume) an."""
        tooltips = getattr(self.app, "action_help_tooltips", None)
        if not isinstance(tooltips, dict):
            return

        ausfall_tooltip = tooltips.get("ausfall")
        if ausfall_tooltip is not None:
            text = MAIN_WINDOW_HELP.get("as_ausfall", "")
            selected_indices = sorted(int(idx) for idx in getattr(self.app, "selected_day_indices", set()))
            if len(selected_indices) == 1:
                day_columns = list(getattr(self.app, "day_columns", []))
                idx = selected_indices[0]
                if 0 <= idx < len(day_columns):
                    day = day_columns[idx]
                    if bool(day.get("is_cancel", False)):
                        text = "Nimmt Ausfall zurück und gibt die Einheit wieder frei. - Strg+Q"
            ausfall_tooltip.text = str(text).strip()

    def update_action_controls(self) -> None:
        """Aktualisiert die Aktivierbarkeit der Aktionsbuttons aus fachlicher Zustandslogik."""
        buttons = getattr(self.app, "action_buttons", None)
        if not isinstance(buttons, dict):
            return

        state = self._action_button_state_uc.compute(
            selected_day_indices=set(self.app.selected_day_indices),
            day_columns=list(self.app.day_columns),
            current_table=self.app.current_table,
            clipboard_path=getattr(self.app, "clipboard_lesson_path", None),
            is_detail_view=bool(getattr(self.app, "is_detail_view", False)),
        )

        toolbar_vm = build_toolbar_view_model(
            action_state=state,
            can_undo=self._history_uc.can_undo(),
            can_redo=self._history_uc.can_redo(),
        )

        ui_state = getattr(self.app, "ui_state", None)
        selection_level = getattr(ui_state, "selection_level", "")
        if selection_level == getattr(ui_state, "SELECTION_LEVEL_CELL", "cell"):
            actions = dict(toolbar_vm.actions)
            if "paste" in actions:
                actions["paste"] = ToolbarActionView(
                    visible=actions["paste"].visible,
                    enabled=self._has_non_whitespace_clipboard_text(),
                )
                toolbar_vm = ToolbarViewModel(actions=actions)

        visible_actions = self._apply_toolbar_view_model(toolbar_vm)
        self.app.ui_state.visible_toolbar_actions = visible_actions

    def _has_non_whitespace_clipboard_text(self) -> bool:
        try:
            clipboard_value = self.app.clipboard_get()
        except tk.TclError:
            return False
        if clipboard_value is None:
            return False
        return bool(str(clipboard_value).strip())

    def _refresh_after_history_step(self) -> None:
        selected_iid = self.app.lesson_tree.focus()
        self.app.refresh_overview()
        if selected_iid and self.app.lesson_tree.exists(selected_iid):
            self.app.lesson_tree.focus(selected_iid)
            self.app.lesson_tree.selection_set(selected_iid)
            self.app._load_selected_table()
        self.update_action_controls()

    def undo_history(self):
        """Führt Undo über den zentralen History-Use-Case aus und aktualisiert die GUI."""
        result = self._history_uc.execute_undo()
        if not result.applied:
            messagebox.showinfo("Undo", "Kein Undo-Eintrag vorhanden.", parent=self.app)
            self.update_action_controls()
            return
        self._refresh_after_history_step()

    def redo_history(self):
        """Führt Redo über den zentralen History-Use-Case aus und aktualisiert die GUI."""
        result = self._history_uc.execute_redo()
        if not result.applied:
            messagebox.showinfo("Redo", "Kein Redo-Eintrag vorhanden.", parent=self.app)
            self.update_action_controls()
            return
        self._refresh_after_history_step()

    def list_recent_change_labels(self, *, limit: int = 5) -> list[str]:
        """Liefert die letzten Undo-Labels (neueste zuerst) für Menüdarstellung."""
        recent_entries = self._history_uc.list_recent_undo_entries(limit=limit)
        labels: list[str] = []
        for entry in recent_entries:
            label = self._short_history_label(str(entry.label))
            labels.append(label)
        return labels

    @staticmethod
    def _short_history_label(label: str) -> str:
        """Reduziert Labels für Verlaufseinträge auf maximal vier Wörter."""
        text = " ".join(str(label or "").strip().split())
        if not text:
            return "Änderung"
        words = text.split(" ")
        if len(words) <= 4:
            return text
        return " ".join(words[:4])

    def undo_history_to_recent_index(self, recent_index: int):
        """Führt Undo bis zum ausgewählten Verlaufseintrag aus."""
        result = self._history_uc.execute_undo_to_recent_index(recent_index=recent_index, limit=5)
        if result.applied_count <= 0:
            messagebox.showinfo("Letzte Änderungen", "Kein passender Undo-Eintrag vorhanden.", parent=self.app)
            self.update_action_controls()
            return
        self._refresh_after_history_step()

    def copy_selected_lesson(self):
        """Kopiert die verlinkte Stunden-Datei der ausgewählten Spalte in die Zwischenablage."""
        context = self._single_selection_context()
        if context is None or self.app.current_table is None:
            return
        _, row_index, _ = context
        link = self._lesson_transfer.resolve_existing_link(self.app.current_table, row_index)
        if not isinstance(link, pathlib.Path) or not link.exists() or not link.is_file():
            messagebox.showinfo(
                "Kopieren", "Für die ausgewählte Spalte existiert keine verlinkte Einheit.", parent=self.app
            )
            return
        self.app.clipboard_lesson_path = link.resolve()
        self.update_action_controls()
        messagebox.showinfo("Kopieren", f"Einheit kopiert:\n{self.app.clipboard_lesson_path.name}", parent=self.app)

    def export_selected_topic_as_pdf_action(self):
        """Exportiert die aktuelle Sequenz als Sequenzplan oder Kompetenzhorizont."""
        context = self._single_selection_context()
        if context is None or self.app.current_table is None:
            return

        selection = ask_export_selection(self.app, theme_key=self.app.theme_var.get())
        if selection is None:
            return

        selected_index, _, _ = context
        if selection.layout == "expected_horizon":
            base_name = "Kompetenzhorizont"
        else:
            base_name = "Sequenzplan"

        extension = ".pdf" if selection.output_format == "pdf" else ".md"
        filetype_label = "PDF" if selection.output_format == "pdf" else "Markdown"
        default_name = f"{base_name}-Export {date.today().strftime('%Y-%m-%d')}{extension}"
        selected_file = filedialog.asksaveasfilename(
            parent=self.app,
            title="Exportieren als...",
            defaultextension=extension,
            initialfile=default_name,
            filetypes=[(filetype_label, f"*{extension}")],
        )
        if not selected_file:
            return

        output_path = pathlib.Path(selected_file).expanduser().resolve()
        if selection.layout == "expected_horizon":
            if selection.output_format == "pdf":
                export_uc = self._export_expected_horizon_pdf_uc
            else:
                export_uc = self._export_expected_horizon_markdown_uc
        else:
            if selection.output_format == "pdf":
                export_uc = self._export_topic_units_pdf_uc
            else:
                export_uc = self._export_topic_units_markdown_uc

        try:
            result = export_uc.execute(
                table=self.app.current_table,
                day_columns=list(self.app.day_columns),
                selected_day_index=selected_index,
                output_path=output_path,
                export_date=date.today(),
            )
        except Exception as exc:
            messagebox.showerror("Exportieren als...", str(exc), parent=self.app)
            return

        messagebox.showinfo(
            "Exportieren als...",
            f"{filetype_label} erfolgreich exportiert:\n{result.output_path}\n\nEinheiten: {result.row_count}\nTitel: {result.title}",
            parent=self.app,
        )

    def export_selected_lzk_expected_horizon_action(self):
        """Exportiert den Kompetenzhorizont der ausgewählten LZK als Markdown und PDF."""
        context = self._single_selection_context()
        if context is None or self.app.current_table is None:
            return

        selected_index, _row_index, _day = context
        try:
            targets = self._export_lzk_expected_horizon_uc.resolve_targets(
                table=self.app.current_table,
                day_columns=list(self.app.day_columns),
                selected_day_index=selected_index,
            )
        except Exception as exc:
            messagebox.showerror("LZK-Kompetenzhorizont", str(exc), parent=self.app)
            return

        try:
            result = self._run_tracked_write(
                label="LZK-Kompetenzhorizont exportieren",
                action=lambda: self._export_lzk_expected_horizon_uc.execute(
                    table=self.app.current_table,
                    day_columns=list(self.app.day_columns),
                    selected_day_index=selected_index,
                    export_date=date.today(),
                ),
                # History capture is text-based; tracking binary PDFs would crash UTF-8 decoding.
                extra_before=[targets.markdown_path],
                extra_after=[targets.markdown_path],
            )
        except Exception as exc:
            messagebox.showerror("LZK-Kompetenzhorizont", str(exc), parent=self.app)
            return

        self._refresh_after_write(selected_index=selected_index)
        messagebox.showinfo(
            "LZK-Kompetenzhorizont",
            "Kompetenzhorizont erfolgreich aktualisiert:\n"
            f"Markdown: {result.markdown_path}\n"
            f"PDF: {result.pdf_path}\n\n"
            f"Einheiten: {result.row_count}\n"
            f"Titel: {result.title}",
            parent=self.app,
        )

    def paste_copied_lesson(self):
        """Fügt die kopierte Stunde in die ausgewählte Spalte ein."""
        context = self._single_selection_context()
        if context is None or self.app.current_table is None:
            return
        selected_index, row_index, _ = context

        copied = getattr(self.app, "clipboard_lesson_path", None)
        if not isinstance(copied, pathlib.Path):
            messagebox.showinfo("Einfügen", "Keine kopierte Einheit vorhanden.", parent=self.app)
            return

        try:
            self._lesson_transfer_flow.validate_source(copied)
            content = self._lesson_transfer_flow.read_source_content(copied)
            plan = self._lesson_transfer_flow.build_execution_plan(self.app.current_table, copied.stem)
        except Exception as exc:
            messagebox.showerror("Einfügen", str(exc), parent=self.app)
            return

        decision = "move"
        allow_delete = False
        existing = self._lesson_transfer_flow.resolve_existing_target_link(self.app.current_table, row_index)
        if isinstance(existing, pathlib.Path):
            choice = messagebox.askyesnocancel(
                "Ziel bereits belegt",
                "Die Zielspalte enthält bereits eine Einheit.\n\n"
                "Ja: bestehende Einheiten nach hinten verschieben\n"
                "Nein: bestehende Einheit als Schatteneinheit behalten\n"
                "Abbrechen: optional löschen oder Vorgang abbrechen",
                parent=self.app,
            )
            if choice is True:
                decision = "move"
            elif choice is False:
                decision = "shadow"
            else:
                delete_existing = messagebox.askyesno(
                    "Bestehende Einheit löschen?",
                    "Soll die bestehende Zieleinheit gelöscht und durch die kopierte ersetzt werden?",
                    parent=self.app,
                )
                if delete_existing:
                    decision = "delete"
                    allow_delete = True
                else:
                    return

        result = self._run_tracked_write(
            label="Einheit einfügen",
            action=lambda: self._lesson_transfer_flow.execute_write(
                LessonTransferFlowWriteRequest(
                    table=self.app.current_table,
                    row_index=row_index,
                    decision=decision,
                    allow_delete=allow_delete,
                    target_path=plan.target_path,
                    content=content,
                    source_stem=copied.stem,
                )
            ),
            extra_after=[plan.target_path],
            extra_after_from_result=lambda item: [item.created_path]
            if isinstance(getattr(item, "created_path", None), pathlib.Path)
            else [],
        )

        if not result.proceed:
            messagebox.showerror("Einfügen", result.error_message or "Einfügen fehlgeschlagen.", parent=self.app)
            return

        self._refresh_after_write(selected_index=selected_index)
        if isinstance(result.shadow_link, pathlib.Path):
            messagebox.showinfo(
                "Einfügen",
                f"Bestehende Einheit als Schatteneinheit behalten:\n{result.shadow_link.name}",
                parent=self.app,
            )

    def link_markdown_for_selected(self):
        """Verknüpft eine vorhandene Markdown-Datei mit der ausgewählten Planzeile."""
        context = self._single_selection_context()
        if context is None or self.app.current_table is None:
            return
        selected_index, row_index, _ = context

        selected_file = filedialog.askopenfilename(
            parent=self.app,
            title="Einheiten-Markdown auswählen",
            filetypes=[("Markdown", "*.md")],
        )
        if not selected_file:
            return

        source = pathlib.Path(selected_file).expanduser().resolve()
        plan = self._find_markdown_for_selected_uc.build_selection_plan(table=self.app.current_table, source=source)
        if not plan.source_valid:
            messagebox.showerror("Markdown finden", plan.source_error or "Ungültige Einheiten-Datei.", parent=self.app)
            return
        if plan.has_target_conflict:
            messagebox.showerror(
                "Markdown finden",
                f"Zieldatei existiert bereits:\n{plan.target}\n\nBitte Datei umbenennen oder verschieben.",
                parent=self.app,
            )
            return

        allow_create_target_dir = True
        if plan.requires_target_dir_creation:
            allow_create_target_dir = messagebox.askyesno(
                "Zielordner erstellen",
                f"Zielordner fehlt und soll erstellt werden?\n{plan.target_dir}",
                parent=self.app,
            )
            if not allow_create_target_dir:
                return

        allow_move = True
        if plan.requires_move:
            allow_move = messagebox.askyesno(
                "Datei verschieben",
                f"Die Datei wird verschoben nach:\n{plan.target}",
                parent=self.app,
            )
            if not allow_move:
                return

        result = self._run_tracked_write(
            label="Markdown finden",
            action=lambda: self._find_markdown_for_selected_uc.execute(
                table=self.app.current_table,
                row_index=row_index,
                source=source,
                allow_create_target_dir=allow_create_target_dir,
                allow_move=allow_move,
                allow_plan_save=True,
            ),
            extra_after=[source, plan.target],
            extra_after_from_result=lambda item: [item.linked_path]
            if isinstance(getattr(item, "linked_path", None), pathlib.Path)
            else [],
        )
        if not result.proceed:
            messagebox.showerror("Markdown finden", result.error_message or "Vorgang abgebrochen.", parent=self.app)
            return

        self._refresh_after_write(selected_index=selected_index)

    def clear_selected_lesson_content(self):
        """Leert die ausgewählte Planzeile (Inhalt) und behält ggf. Schattenlink bei."""
        context = self._single_selection_context()
        if context is None or self.app.current_table is None:
            return
        selected_index, row_index, _ = context

        confirmed = messagebox.askyesno(
            "Einheit löschen",
            "Soll der Inhalt der ausgewählten Einheit wirklich geleert werden?",
            parent=self.app,
        )
        if not confirmed:
            return

        try:
            result = self._run_tracked_write(
                label="Einheit leeren",
                action=lambda: self._clear_selected_lesson_uc.execute(self.app.current_table, row_index),
                extra_after_from_result=lambda item: [item.shadow_link]
                if isinstance(getattr(item, "shadow_link", None), pathlib.Path)
                else [],
            )
        except Exception as exc:
            messagebox.showerror("Einheit löschen", str(exc), parent=self.app)
            return

        self._refresh_after_write(selected_index=selected_index)
        if isinstance(result.shadow_link, pathlib.Path):
            messagebox.showinfo(
                "Einheit löschen",
                f"Verlinkte Datei bleibt als Schatteneinheit erhalten:\n{result.shadow_link.name}",
                parent=self.app,
            )

    def rename_selected_lesson(self):
        """Benennt die verlinkte Einheit der Auswahl anhand eines neuen Inhalts-Titels um."""
        context = self._single_selection_context()
        if context is None or self.app.current_table is None:
            return
        selected_index, row_index, day = context

        existing = self._lesson_transfer.resolve_existing_link(self.app.current_table, row_index)
        if not isinstance(existing, pathlib.Path) or not existing.exists() or not existing.is_file():
            messagebox.showinfo(
                "Einheit umbenennen", "Für die ausgewählte Spalte existiert keine verlinkte Einheit.", parent=self.app
            )
            return

        initial_title = str(self.app._field_value(day, "inhalt") or "").strip()
        new_title = simpledialog.askstring(
            "Einheit umbenennen",
            "Neuer Einheitstitel:",
            initialvalue=initial_title,
            parent=self.app,
        )
        if new_title is None:
            return
        new_title = new_title.strip()
        if not new_title:
            messagebox.showinfo("Einheit umbenennen", "Der Titel darf nicht leer sein.", parent=self.app)
            return

        desired_stem = self.app.lesson_context_controller.build_regular_stem(
            new_title,
            str(day.get("datum", "")).strip(),
        )

        result = self._run_tracked_write(
            label="Einheit umbenennen",
            action=lambda: self._rename_linked_file_for_row_uc.execute(
                table=self.app.current_table,
                row_index=row_index,
                desired_stem=desired_stem,
                allow_rename=True,
                allow_plan_save=True,
                preserve_alias=False,
            ),
            extra_after=[existing],
            extra_after_from_result=lambda item: [item.target_path]
            if isinstance(getattr(item, "target_path", None), pathlib.Path)
            else [],
        )

        if not result.proceed:
            messagebox.showerror(
                "Einheit umbenennen", result.error_message or "Umbenennen fehlgeschlagen.", parent=self.app
            )
            return

        self._refresh_after_write(selected_index=selected_index)

    def split_selected_unit_action(self):
        """Teilt eine Mehrstunden-Einheit in einzelne Stunden."""
        context = self._single_selection_context()
        if context is None or self.app.current_table is None:
            return
        selected_index, row_index, _ = context

        try:
            hours = self._split_selected_unit_uc.preview_hours(self.app.current_table, row_index)
        except Exception as exc:
            messagebox.showinfo("Aufsplitten", str(exc), parent=self.app)
            return

        confirmed = messagebox.askyesno(
            "Einheit aufsplitten",
            f"Die Einheit mit {hours} Stunden wird in einzelne Einheiten aufgeteilt. Fortfahren?",
            parent=self.app,
        )
        if not confirmed:
            return

        try:
            self._run_tracked_write(
                label="Einheit aufsplitten",
                action=lambda: self._split_selected_unit_uc.execute(self.app.current_table, row_index),
            )
        except Exception as exc:
            messagebox.showerror("Aufsplitten", str(exc), parent=self.app)
            return

        self._refresh_after_write(selected_index=selected_index)

    def merge_selected_units_action(self):
        """Führt alle zusammenführbaren Einheiten des ausgewählten Datums zusammen."""
        context = self._single_selection_context()
        if context is None or self.app.current_table is None:
            return
        selected_index, row_index, _ = context

        try:
            preview = self._merge_selected_units_uc.preview(self.app.current_table, row_index)
        except Exception as exc:
            messagebox.showinfo("Zusammenführen", str(exc), parent=self.app)
            return

        confirmed = messagebox.askyesno(
            "Einheiten zusammenführen",
            f"{preview.merged_count} Einheiten werden zu einer Einheit mit {preview.total_hours} Stunden verbunden. Fortfahren?",
            parent=self.app,
        )
        if not confirmed:
            return

        try:
            self._run_tracked_write(
                label="Einheiten zusammenführen",
                action=lambda: self._merge_selected_units_uc.execute(self.app.current_table, row_index),
            )
        except Exception as exc:
            messagebox.showerror("Zusammenführen", str(exc), parent=self.app)
            return

        self._refresh_after_write(selected_index=selected_index)

    def restore_selected_from_cancel_action(self):
        """Hebt eine Ausfall-Markierung der ausgewählten Spalte auf."""
        context = self._single_selection_context()
        if context is None or self.app.current_table is None:
            return
        selected_index, row_index, day = context

        if not bool(day.get("is_cancel", False)):
            messagebox.showinfo("Ausfall zurücknehmen", "Die ausgewählte Spalte ist kein Ausfall.", parent=self.app)
            return

        confirmed = messagebox.askyesno(
            "Ausfall zurücknehmen",
            "Soll die Ausfall-Markierung entfernt werden?",
            parent=self.app,
        )
        if not confirmed:
            return

        try:
            self._run_tracked_write(
                label="Ausfall zurücknehmen",
                action=lambda: self._restore_selected_from_cancel_uc.execute(self.app.current_table, row_index),
            )
        except Exception as exc:
            messagebox.showerror("Ausfall zurücknehmen", str(exc), parent=self.app)
            return

        self._refresh_after_write(selected_index=selected_index)

    def extend_plan_to_next_vacation(self):
        """Erweitert den aktiven Kursplan ab Kursende bis zur nächsten Ferienphase."""
        if self.app.current_table is None:
            messagebox.showinfo("Plan erweitern", "Kein Kursplan geladen.", parent=self.app)
            return

        calendar_raw = str(self.app.path_values.get(CALENDAR_DIR_KEY, "")).strip()
        if not calendar_raw:
            messagebox.showerror("Plan erweitern", "Kein Kalenderordner konfiguriert.", parent=self.app)
            return

        calendar_dir = resolve_path_value(calendar_raw)

        try:
            result = self._run_tracked_write(
                label="Plan bis nächste Ferien erweitern",
                action=lambda: self._extend_plan_to_next_vacation_uc.execute(
                    markdown_path=self.app.current_table.markdown_path,
                    calendar_dir=calendar_dir,
                ),
                extra_after=[self.app.current_table.markdown_path],
            )
        except Exception as exc:
            messagebox.showerror("Plan erweitern", str(exc), parent=self.app)
            return

        self._refresh_after_write()
        messagebox.showinfo(
            "Plan erweitert",
            f"Es wurden {result.rows_added} Zeilen ergänzt.\nZeitraum: {result.range_start} bis {result.range_end}",
            parent=self.app,
        )
