import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Callable

from kursplaner.adapters.gui.help_catalog import NEW_LESSON_HELP
from kursplaner.adapters.gui.hover_tooltip import HoverTooltip
from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.core.config.path_store import CALENDAR_DIR_KEY, UNTERRICHT_DIR_KEY
from kursplaner.core.config.settings import WEEKDAY_SHORT_OPTIONS
from kursplaner.core.usecases.new_lesson_form_usecase import NewLessonFormData, NewLessonFormUseCase
from kursplaner.core.usecases.new_lesson_usecase import NewLessonUseCase
from kursplaner.core.usecases.path_settings_usecase import PathSettingsUseCase

if TYPE_CHECKING:
    from kursplaner.core.domain.models import StartRequest, StartResult

CreateLessonAction = Callable[["StartRequest", Callable[[str, str], bool]], "StartResult"]


class NewLessonWindow(ScrollablePopupWindow):
    """Stellt die GUI-Komponente New Lesson Window bereit.

    Die Klasse kapselt Bedienlogik und delegiert fachliche Entscheidungen an Use Cases.
    """

    def __init__(
        self,
        master,
        on_success=None,
        on_paths_changed=None,
        theme_key: str | None = None,
        form_usecase: NewLessonFormUseCase | None = None,
        new_lesson_usecase: NewLessonUseCase | None = None,
        path_settings_usecase: PathSettingsUseCase | None = None,
        create_lesson_action: CreateLessonAction | None = None,
    ):
        """Initialisiert den Dialog für das Anlegen eines neuen Unterrichts."""
        super().__init__(
            master,
            title="Neuer Unterricht",
            geometry="980x760",
            minsize=(920, 560),
            theme_key=theme_key,
        )

        self.on_success = on_success
        self.on_paths_changed = on_paths_changed
        if form_usecase is None:
            raise RuntimeError("NewLessonFormUseCase fehlt in NewLessonWindow-Verdrahtung.")
        if new_lesson_usecase is None:
            raise RuntimeError("NewLessonUseCase fehlt in NewLessonWindow-Verdrahtung.")
        if path_settings_usecase is None:
            raise RuntimeError("PathSettingsUseCase fehlt in NewLessonWindow-Verdrahtung.")
        self.form_usecase = form_usecase
        self.new_lesson_usecase = new_lesson_usecase
        self.path_settings_usecase = path_settings_usecase
        self.create_lesson_action = create_lesson_action

        self.path_values = self.path_settings_usecase.load_values()

        self.subject_var = tk.StringVar(value="Mathematik")
        self.group_var = tk.StringVar()
        self.grade_var = tk.StringVar(value="8")
        self.period_input_var = tk.StringVar()
        self.vacation_horizon_var = tk.StringVar(value="1")
        self.preview_var = tk.StringVar(value="Ordnervorschau: –")
        self.vacation_preview_var = tk.StringVar(value="Planende (Ferienbeginn): –")

        self.day_enabled_vars: dict[int, tk.BooleanVar] = {}
        self.day_hours_vars: dict[int, tk.StringVar] = {}
        self._tooltips: list[HoverTooltip] = []
        self._focus_attempts = 0

        self._build_ui()
        self._bind_preview_updates()
        self._refresh_preview()
        self._apply_theme()
        self.after_idle(self._set_initial_focus)

    def _build_ui(self):
        """Erzeugt Formularfelder für Stammdaten, Tage und Pfade."""
        root = ttk.Frame(self.content, padding=16)
        root.pack(fill="both", expand=True)

        basics = ttk.LabelFrame(root, text="Kursdaten")
        basics.pack(fill="x", pady=(0, 10))

        ttk.Label(basics, text="Kursfach").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Combobox(
            basics,
            textvariable=self.subject_var,
            values=["Mathematik", "Informatik", "Darstellendes Spiel"],
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(basics, text="Kursgruppe").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(basics, textvariable=self.group_var).grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(basics, text="Stufe (1–13)").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Spinbox(basics, from_=1, to=13, textvariable=self.grade_var, width=6).grid(
            row=2, column=1, sticky="w", pady=4
        )

        period_label = ttk.Label(basics, text="Halbjahr ODER Startdatum")
        period_label.grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        period_entry = ttk.Entry(basics, textvariable=self.period_input_var)
        period_entry.grid(row=3, column=1, sticky="ew", pady=4)
        self._period_entry = period_entry
        self._tooltips.append(HoverTooltip(period_label, NEW_LESSON_HELP["period_input"]))
        self._tooltips.append(HoverTooltip(period_entry, NEW_LESSON_HELP["period_input"]))

        self.vacation_horizon_frame = ttk.Frame(basics)
        self.vacation_horizon_frame.grid(row=4, column=1, sticky="w", pady=(0, 4))
        vacation_label = ttk.Label(self.vacation_horizon_frame, text="Bei Startdatum planen bis:")
        vacation_label.pack(side="left", padx=(0, 8))
        ttk.Label(self.vacation_horizon_frame, text="Ferienstart-Niveau:").pack(side="left")
        horizon_spin = ttk.Spinbox(
            self.vacation_horizon_frame, from_=1, to=99, textvariable=self.vacation_horizon_var, width=4
        )
        horizon_spin.pack(side="left", padx=(6, 0))
        self._tooltips.append(HoverTooltip(vacation_label, NEW_LESSON_HELP["vacation_horizon"]))
        self._tooltips.append(HoverTooltip(horizon_spin, NEW_LESSON_HELP["vacation_horizon"]))

        ttk.Label(basics, text="Beispiele: 26-1 oder 2026-02-20").grid(row=5, column=1, sticky="w", pady=(0, 4))
        ttk.Label(basics, textvariable=self.preview_var).grid(row=6, column=0, columnspan=2, sticky="w", pady=(4, 2))
        ttk.Label(basics, textvariable=self.vacation_preview_var).grid(
            row=7, column=0, columnspan=2, sticky="w", pady=(0, 2)
        )
        basics.columnconfigure(1, weight=1)

        self._refresh_vacation_horizon_visibility()

        days_frame = ttk.LabelFrame(root, text="Stunden pro Tag (Mo–Fr)")
        days_frame.pack(fill="x", pady=(0, 10))

        row = ttk.Frame(days_frame)
        row.pack(fill="x", padx=6, pady=6)

        for short_label, weekday in WEEKDAY_SHORT_OPTIONS:
            cell = ttk.Frame(row)
            cell.pack(side="left", padx=(0, 12))

            enabled_var = tk.BooleanVar(value=True)
            hours_var = tk.StringVar(value="2")
            self.day_enabled_vars[weekday] = enabled_var
            self.day_hours_vars[weekday] = hours_var

            ttk.Checkbutton(
                cell,
                text=short_label,
                variable=enabled_var,
                command=lambda w=weekday: self._toggle_day_input(w),
            ).pack(side="left")

            spin = ttk.Spinbox(cell, from_=1, to=4, textvariable=hours_var, width=3)
            spin.pack(side="left", padx=(4, 0))
            setattr(self, f"_spin_{weekday}", spin)

        buttons = ttk.Frame(root)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Anlegen", command=self._run).pack(side="left")
        ttk.Button(buttons, text="Schließen", command=self.destroy).pack(side="right")

    def _apply_theme(self):
        """Wendet das gewählte Theme auf das Fenster und ttk-Styles an."""
        self.apply_theme()

    def _set_initial_focus(self):
        """Setzt den initialen Fokus in das zentrale Eingabefeld des Dialogs."""
        entry = getattr(self, "_period_entry", None)
        if entry is None:
            return
        if not self.winfo_exists():
            return
        try:
            if self.winfo_viewable():
                self.lift()
                self.focus_set()
                entry.focus_set()
                entry.icursor(tk.END)
                self._focus_attempts = 0
                return
        except tk.TclError:
            return

        # Avoid blocking calls here: retry shortly until the toplevel is viewable.
        if self._focus_attempts < 20:
            self._focus_attempts += 1
            self.after(30, self._set_initial_focus)

    def _bind_preview_updates(self):
        """Verdrahtet Formularänderungen mit der Ordnervorschau."""
        for var in (self.subject_var, self.group_var, self.period_input_var):
            var.trace_add("write", lambda *_: self._refresh_preview())
        self.period_input_var.trace_add("write", lambda *_: self._refresh_vacation_horizon_visibility())
        self.vacation_horizon_var.trace_add("write", lambda *_: self._refresh_preview())

    def _toggle_day_input(self, weekday: int):
        """Aktiviert oder deaktiviert den Stunden-Spinner für einen Wochentag."""
        spin = getattr(self, f"_spin_{weekday}")
        if self.day_enabled_vars[weekday].get():
            spin.configure(state="normal")
            if not self.day_hours_vars[weekday].get().strip():
                self.day_hours_vars[weekday].set("2")
        else:
            spin.configure(state="disabled")

    def _collect_day_hours_raw(self) -> dict[int, str]:
        """Sammelt Rohwerte der aktivierten Unterrichtstage für den Form-UseCase."""
        raw: dict[int, str] = {}
        for _, weekday in WEEKDAY_SHORT_OPTIONS:
            if self.day_enabled_vars[weekday].get():
                raw[weekday] = self.day_hours_vars[weekday].get()
        return raw

    def _collect_form_data(self) -> NewLessonFormData:
        """Bündelt aktuelle GUI-Eingaben als formularnahe Rohdaten."""
        return NewLessonFormData(
            subject_raw=self.subject_var.get(),
            group_raw=self.group_var.get(),
            grade_raw=self.grade_var.get(),
            period_raw=self.period_input_var.get(),
            base_dir_raw=self.path_values[UNTERRICHT_DIR_KEY],
            calendar_dir_raw=self.path_values[CALENDAR_DIR_KEY],
            day_hours_raw=self._collect_day_hours_raw(),
            vacation_break_horizon_raw=self.vacation_horizon_var.get(),
            kc_profile_id_raw="",
            process_competencies_raw=(),
            content_competency_raw="",
        )

    def _refresh_vacation_horizon_visibility(self):
        """Zeigt die Ferienhorizont-Auswahl nur für Datumsmodus an."""
        raw = self.period_input_var.get().strip()
        is_date_mode = bool(raw) and ("-" in raw)
        if is_date_mode:
            self.vacation_horizon_frame.grid()
        else:
            self.vacation_horizon_frame.grid_remove()
            self.vacation_preview_var.set("Planende (Ferienbeginn): –")

    def _refresh_preview(self):
        """Aktualisiert die Ordnervorschau aus den aktuellen Formulardaten."""
        form_data = self._collect_form_data()
        try:
            preview = self.form_usecase.preview_folder_name(form_data)
            if not preview:
                self.preview_var.set("Ordnervorschau: –")
            else:
                self.preview_var.set(f"Ordnervorschau: {preview}")

            min_horizon, max_horizon = self.form_usecase.vacation_horizon_limits(form_data)
            current_horizon = self.form_usecase.parse_vacation_horizon(self.vacation_horizon_var.get())
            clamped_horizon = max(min_horizon, min(max_horizon, current_horizon))
            if clamped_horizon != current_horizon:
                self.vacation_horizon_var.set(str(clamped_horizon))

            end_date = self.form_usecase.preview_vacation_end_date(self._collect_form_data())
            if end_date is None:
                self.vacation_preview_var.set("Planende (Ferienbeginn): –")
            else:
                self.vacation_preview_var.set(
                    f"Planende (Ferienbeginn): {end_date.isoformat()} (Horizont max: {max_horizon})"
                )
        except Exception:
            self.preview_var.set("Ordnervorschau: –")
            self.vacation_preview_var.set("Planende (Ferienbeginn): –")

    def _confirm_fs_change(self, action: str, details: str = "") -> bool:
        """Fragt eine Benutzerbestätigung für Dateisystem-Schreibaktionen ab."""
        text = action.strip()
        if details.strip():
            text += f"\n\n{details.strip()}"
        text += "\n\nÄnderung wirklich durchführen?"
        return messagebox.askyesno("Dateisystem-Änderung", text, parent=self)

    def _run(self):
        """Startet den vollständigen Anlegen-Flow inklusive Bestätigung und Ergebnisdialog."""
        try:
            request = self.form_usecase.build_start_request(self._collect_form_data())

            should_create = messagebox.askyesno(
                "Dateisystem-Änderung",
                "Neuen Unterricht wirklich anlegen?\n\n"
                f"Ordner: {request.base_dir / request.folder_name}\n"
                f"Kalender: {request.calendar_dir}",
                parent=self,
            )
            if not should_create:
                return

            if self.create_lesson_action is None:
                result = self.new_lesson_usecase.execute(request, confirm_change=self._confirm_fs_change)
            else:
                result = self.create_lesson_action(request, self._confirm_fs_change)

        except (ValueError, FileNotFoundError, FileExistsError, RuntimeError) as exc:
            messagebox.showerror("Neuer Unterricht", str(exc), parent=self)
            return
        except Exception as exc:
            messagebox.showerror("Neuer Unterricht", f"Unerwarteter Fehler:\n{exc}", parent=self)
            return

        message = (
            f"Unterricht erfolgreich angelegt.\n\n"
            f"Ordner: {result.lesson_dir}\n"
            f"Datei: {result.lesson_markdown}\n"
            f"Terminzeilen: {result.planned_rows}\n"
            f"Zeitraum: {result.range_start} bis {result.range_end}"
        )

        if result.warnings:
            message += "\n\nWarnungen:\n- " + "\n- ".join(result.warnings)

        messagebox.showinfo("Neuer Unterricht", message, parent=self)
        if self.on_success:
            self.on_success()
        self.destroy()
