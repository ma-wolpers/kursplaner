from __future__ import annotations

import pathlib
import re
import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, simpledialog, ttk

from kursplaner.core.usecases.load_plan_detail_usecase import MissingLessonYamlFrontmatterError
from kursplaner.core.usecases.reconcile_ub_overview_usecase import UbReconcileAction, UbReconcileConflict


class MainWindowOverviewController:
    """Kapselt Übersichtsladen und Tabellenaufbereitung für die Hauptansicht.

    Diese Klasse nutzt ausschließlich die vom `app` injizierten Use Cases (via
    `app.gui_dependencies`) und instanziiert keine Repositories selbst.
    """

    def __init__(self, app):
        """Initialisiert Controller mit injizierten Read-Use-Cases aus dem Composition Root."""
        self.app = app
        deps = getattr(app, "gui_dependencies", None)
        if deps is None:
            raise RuntimeError("GUI Dependencies not available on app")
        self.list_lessons_usecase = deps.list_lessons_usecase
        self.load_plan_detail_usecase = deps.load_plan_detail_usecase
        self.column_visibility_projection_usecase = deps.column_visibility_projection_usecase
        self.repair_lesson_yaml_frontmatter_usecase = deps.repair_lesson_yaml_frontmatter_usecase
        self.reconcile_ub_overview_usecase = deps.reconcile_ub_overview_usecase
        self.cleanup_lzk_expected_horizon_links_usecase = deps.cleanup_lzk_expected_horizon_links_usecase
        self.path_settings_usecase = app.path_settings_usecase

    def _project_visible_day_columns(self, raw_day_columns: list[dict[str, object]]) -> list[dict[str, object]]:
        """Projiziert Tages-Spalten nach aktiven Sichtbarkeits-/Marker-Regeln."""
        projection = self.column_visibility_projection_usecase.project(
            day_columns=raw_day_columns,
            settings=self.app.column_visibility_settings,
        )
        return projection.visible_day_columns

    def _ask_ub_conflict_action(self, conflict: UbReconcileConflict) -> UbReconcileAction:
        """Fragt die gewünschte Auflösung für genau einen UB-Konflikt ab."""
        answer = messagebox.askyesnocancel(
            "UB-Konflikt erkannt",
            f"Konfliktart: {conflict.kind}\n"
            f"Zeile: {conflict.row_index + 1}\n"
            f"Einheit: {conflict.lesson_path.name}\n"
            f"UB: {conflict.ub_stem}\n\n"
            f"{conflict.message}\n\n"
            "Ja: Übersicht reparieren\n"
            "Nein: Einheit reparieren\n"
            "Abbrechen: ignorieren",
            parent=self.app,
        )
        if answer is None:
            return "ignore"
        return "fix_overview" if answer else "fix_lesson"

    def _run_ub_reconciliation(self, table) -> bool:
        """Prüft und behebt UB-Konflikte per geführter Nutzerentscheidung."""
        try:
            scan_result = self.reconcile_ub_overview_usecase.scan(table)
        except Exception as exc:
            messagebox.showwarning("UB-Abgleich", f"UB-Abgleich fehlgeschlagen:\n{exc}", parent=self.app)
            return False

        if not scan_result.conflicts:
            return False

        changed = False
        for conflict in scan_result.conflicts:
            action = self._ask_ub_conflict_action(conflict)
            if action == "ignore":
                continue
            apply_result = self.reconcile_ub_overview_usecase.apply_resolution(
                table=table,
                conflict=conflict,
                action=action,
            )
            if not apply_result.proceed:
                messagebox.showwarning(
                    "UB-Abgleich",
                    apply_result.error_message or "Unbekannter Fehler beim UB-Abgleich.",
                    parent=self.app,
                )
                continue
            changed = True

        return changed

    @staticmethod
    def _normalize_yaml_kind(value: str | None) -> str | None:
        """Normalisiert Nutzereingaben auf kanonische YAML-Artbezeichner."""
        text = str(value or "").strip().lower()
        mapping = {
            "u": "unterricht",
            "unterricht": "unterricht",
            "l": "lzk",
            "lzk": "lzk",
            "h": "hospitation",
            "ho": "hospitation",
            "hospitation": "hospitation",
        }
        return mapping.get(text)

    def _ask_yaml_kind(self) -> str | None:
        """Fragt interaktiv die gewünschte Art für YAML-Reparatur ab.

        Returns:
            Kanonische Art (`unterricht`, `lzk`, `hospitation`) oder `None`
            bei Abbruch des Dialogs.
        """
        while True:
            value = simpledialog.askstring(
                "YAML-Art wählen",
                "Welche Art soll ergänzt werden?\n"
                "- Unterricht\n"
                "- LZK\n"
                "- Hospitation\n\n"
                "Eingabe: unterricht | lzk | hospitation",
                parent=self.app,
            )
            if value is None:
                return None
            normalized = self._normalize_yaml_kind(value)
            if normalized is not None:
                return normalized
            messagebox.showerror(
                "Ungültige Art",
                "Bitte 'unterricht', 'lzk' oder 'hospitation' eingeben.",
                parent=self.app,
            )

    def _prompt_and_repair_missing_frontmatter(self, error: MissingLessonYamlFrontmatterError) -> bool:
        """Steuert den GUI-Reparaturfluss für fehlendes Lesson-Frontmatter.

        Zeigt Bestätigungsdialog, erfragt die Ziel-Art und delegiert die
        Reparatur an den Use Case.
        """
        should_repair = messagebox.askyesno(
            "YAML fehlt",
            "Am Dateianfang der Einheit fehlt ein YAML-Frontmatter.\n\n"
            f"Datei:\n{error.lesson_path}\n\n"
            "Soll das YAML ergänzt werden?",
            parent=self.app,
        )
        if not should_repair:
            return False

        kind = self._ask_yaml_kind()
        if kind is None:
            return False

        try:
            self.repair_lesson_yaml_frontmatter_usecase.execute(
                lesson_path=error.lesson_path,
                kind=kind,
            )
            return True
        except Exception as exc:
            messagebox.showerror(
                "YAML ergänzen fehlgeschlagen",
                str(exc),
                parent=self.app,
            )
            return False

    def refresh_overview(self):
        """Lädt die Unterrichtsübersicht neu und rendert die linke Baumansicht."""
        base_dir = self.app.base_dir_var.get().strip()
        unterricht_key = self.path_settings_usecase.UNTERRICHT_KEY
        if base_dir:
            updated_values, changed = self.path_settings_usecase.apply_selected_path(
                self.app.path_values,
                unterricht_key,
                base_dir,
            )
            if changed:
                saved_values = self.path_settings_usecase.save_values(updated_values)
                self.app._apply_saved_paths(saved_values)

        for item in self.app.lesson_tree.get_children():
            self.app.lesson_tree.delete(item)
        self.app.lesson_load_errors = {}

        result = self.list_lessons_usecase.execute(pathlib.Path(base_dir).expanduser().resolve()) if base_dir else None
        lessons = result.lessons if result is not None else []
        self.app.count_var.set(f"{len(lessons)} Kurspläne")

        for lesson in lessons:
            iid = str(lesson.markdown_path) if lesson.markdown_path else lesson.folder_name
            name = lesson.folder_name
            tags: tuple[str, ...] = tuple()
            if lesson.load_error:
                name = f"⚠ {name}"
                tags = ("load_error",)
                self.app.lesson_load_errors[iid] = lesson.load_error
            self.app.lesson_tree.insert(
                "",
                "end",
                iid=iid,
                values=(name, lesson.next_topic, str(lesson.remaining_hours), lesson.next_lzk),
                tags=tags,
            )

        if result is not None and result.warnings:
            messagebox.showwarning(
                "Markierte Einträge",
                "Einige Kurse konnten nicht vollständig berechnet werden.\n"
                "Sie sind in der Übersicht mit ⚠ markiert und bleiben sichtbar.",
                parent=self.app,
            )

        self.clear_plan_table("Bitte links einen Kurs auswählen.")
        self.app._show_course_overview()
        self.ensure_course_selected(prefer_first=True)

    def ensure_course_selected(self, *, prefer_first: bool = False):
        """Stellt eine gültige Kursselektion sicher, damit Tastaturnavigation sofort greift."""
        items = list(self.app.lesson_tree.get_children())
        if not items:
            return

        selected = self.app.lesson_tree.focus()
        if selected and self.app.lesson_tree.exists(selected):
            self.app.lesson_tree.selection_set(selected)
            self.app.lesson_tree.see(selected)
            return

        selection = self.app.lesson_tree.selection()
        if selection:
            first = selection[0]
            if self.app.lesson_tree.exists(first):
                self.app.lesson_tree.focus(first)
                self.app.lesson_tree.selection_set(first)
                self.app.lesson_tree.see(first)
                return

        if prefer_first:
            first = items[0]
            self.app.lesson_tree.focus(first)
            self.app.lesson_tree.selection_set(first)
            self.app.lesson_tree.see(first)

    def _show_loading_dialog(self, text: str):
        """Zeigt einen kleinen, nicht-blockierenden Ladehinweis mit laufender Progressbar."""
        dialog = tk.Toplevel(self.app)
        dialog.title("Lade Kurs")
        dialog.transient(self.app)
        dialog.resizable(False, False)
        dialog.geometry("320x90")
        dialog.protocol("WM_DELETE_WINDOW", lambda: None)

        content = ttk.Frame(dialog, padding=12)
        content.pack(fill="both", expand=True)
        ttk.Label(content, text=text).pack(anchor="w")
        progress = ttk.Progressbar(content, mode="indeterminate", length=280)
        progress.pack(fill="x", pady=(10, 0))
        progress.start(10)

        dialog.update_idletasks()
        self.app.update_idletasks()

        def _close():
            try:
                progress.stop()
            except Exception:
                pass
            if dialog.winfo_exists():
                dialog.destroy()

        return _close

    def clear_plan_table(self, title: str):
        """Leert die Planansicht und setzt UI-Statusfelder auf Initialwerte."""
        self.app.preview_title_var.set(title)
        self.app.selected_column_var.set("Ausgewählte Spalte: keine")
        self.app.current_table = None
        self.app.raw_day_columns = []
        self.app.day_columns = []
        self.app.day_column_x_positions = {}
        self.app.selected_day_indices = set()
        self.app.ui_state.clear_selected_cell()
        self.app.ui_state.clear_active_editor()
        self.app.ui_state.set_selection_level(self.app.ui_state.SELECTION_LEVEL_COURSE)
        if bool(self.app.auto_row_mode_var.get()):
            self.app._set_row_mode(self.app.row_display_mode_usecase.MODE_UNTERRICHT, manual=False)
        self.app._rebuild_grid()

    def load_selected_table(self, _event=None):
        """Lädt die aktuell selektierte Plan-Datei in die rechte Detailansicht."""
        selected = self.app.lesson_tree.focus()
        if not selected:
            return

        path = pathlib.Path(selected)
        if not path.exists() or not path.is_file():
            self.clear_plan_table("Keine gleichnamige Plan-Datei gefunden.")
            return

        known_error = self.app.lesson_load_errors.get(selected)
        if known_error:
            messagebox.showinfo(
                "Markierter Eintrag",
                "Dieser Kurs war beim letzten Überblickslauf fehlerhaft markiert.\n"
                "Es wird jetzt versucht, ihn gezielt zu laden.\n\n"
                f"Letzter Fehler:\n{known_error}",
                parent=self.app,
            )

        close_loading = self._show_loading_dialog("Kursplan wird geladen …")
        try:
            detail = self.load_plan_detail_usecase.execute(path)
            if self._run_ub_reconciliation(detail.table):
                detail = self.load_plan_detail_usecase.execute(path)
            cleanup_result = self.cleanup_lzk_expected_horizon_links_usecase.execute(
                table=detail.table,
                day_columns=detail.day_columns,
            )
            if cleanup_result.cleared_links > 0 or cleanup_result.repaired_timestamps > 0:
                detail = self.load_plan_detail_usecase.execute(path)
            self.app.current_table = detail.table
            self.app.raw_day_columns = list(detail.day_columns)
            self.app.day_columns = self._project_visible_day_columns(self.app.raw_day_columns)
            self.app._update_row_mode_from_selection()
            self.app.lesson_load_errors.pop(selected, None)
            self.app._show_course_detail()
        except MissingLessonYamlFrontmatterError as exc:
            if self._prompt_and_repair_missing_frontmatter(exc):
                self.load_selected_table(_event)
                return
            self.clear_plan_table(f"Tabelle konnte nicht geladen werden: {exc}")
            self.app._show_course_overview()
            return
        except Exception as exc:
            self.clear_plan_table(f"Tabelle konnte nicht geladen werden: {exc}")
            self.app._show_course_overview()
            return
        finally:
            close_loading()

        self.app.preview_title_var.set(f"Kursplan · {path.name}")
        self.app._rebuild_grid()
        next_index = self._next_lesson_column_index()
        if next_index is not None:
            self.app._set_single_column_selection(next_index, ensure_visible=True)
        self.app.ui_state.set_selection_level(self.app.ui_state.SELECTION_LEVEL_COLUMN)
        if bool(self.app.auto_scroll_next_unit_var.get()):
            self.app.after_idle(self._scroll_to_next_unit)

    def close_detail_view(self):
        """Wechselt zurück zur reinen Kursübersicht ohne den Kursfokus zu verlieren."""
        self.app.selected_day_indices = set()
        self.app.ui_state.clear_selected_cell()
        self.app.ui_state.clear_active_editor()
        self.app.ui_state.set_selection_level(self.app.ui_state.SELECTION_LEVEL_COURSE)
        self.app._update_selected_column_label()
        self.app._show_course_overview()
        self.app.action_controller.update_action_controls()
        self.ensure_course_selected(prefer_first=True)

    @staticmethod
    def _parse_day_date(raw_value: object) -> date | None:
        """Parst Datumsangaben robust aus Grid-Headern verschiedener Formate."""
        text = str(raw_value or "").strip()
        if not text:
            return None

        for pattern in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%d-%m-%Y", "%d-%m-%y"):
            try:
                return datetime.strptime(text, pattern).date()
            except ValueError:
                continue

        iso_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        if iso_match:
            try:
                return datetime.strptime(iso_match.group(1), "%Y-%m-%d").date()
            except ValueError:
                return None

        german_match = re.search(r"(\d{1,2})[\.-](\d{1,2})(?:[\.-](\d{2,4}))?", text)
        if german_match:
            day = int(german_match.group(1))
            month = int(german_match.group(2))
            year_token = german_match.group(3)
            if year_token:
                year = int(year_token)
                if year < 100:
                    year += 2000
            else:
                year = date.today().year
            try:
                return date(year, month, day)
            except ValueError:
                return None

        return None

    def _next_lesson_column_index(self) -> int | None:
        """Bestimmt die nächste Unterrichtsspalte relativ zum heutigen Datum."""
        if not self.app.day_columns:
            return None

        today = date.today()
        fallback_first_occurring: int | None = None

        for idx, day_info in enumerate(self.app.day_columns):
            if bool(day_info.get("is_cancel", False)):
                continue

            if fallback_first_occurring is None:
                fallback_first_occurring = idx

            day_date = self._parse_day_date(day_info.get("datum", ""))
            if day_date is None:
                continue
            if day_date >= today:
                return idx

        return fallback_first_occurring

    def _scroll_to_next_unit(self):
        """Scrollt die Detailansicht horizontal zur nächsten Unterrichtseinheit."""
        target_index = self._next_lesson_column_index()
        if target_index is None:
            return

        self.app.grid_canvas.update_idletasks()
        bbox = self.app.grid_canvas.bbox(self.app.grid_window)
        if bbox is None:
            return

        full_width = max(1, bbox[2] - bbox[0])
        viewport_width = max(1, int(self.app.grid_canvas.winfo_width()))
        x_positions = getattr(self.app, "day_column_x_positions", {})
        target_pixel = int(x_positions.get(target_index, target_index * self.app.day_column_width))
        target_fraction = target_pixel / float(full_width)
        max_fraction = max(0.0, 1.0 - (viewport_width / float(full_width)))
        self.app.grid_canvas.xview_moveto(min(max(target_fraction, 0.0), max_fraction))

    def collect_day_columns(self):
        """Erzeugt die Grid-Read-Projektion (`day_columns`) aus der aktuellen Tabelle."""
        if self.app.current_table is None:
            self.app.raw_day_columns = []
            self.app.day_columns = []
            return
        self.app.raw_day_columns = self.load_plan_detail_usecase.build_day_columns(self.app.current_table)
        self.app.day_columns = self._project_visible_day_columns(self.app.raw_day_columns)
