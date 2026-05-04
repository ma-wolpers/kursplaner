import tkinter as tk
from datetime import time
from tkinter import ttk

from kursplaner.adapters.gui.dialog_services import filedialog, messagebox

from kursplaner.adapters.gui.hover_tooltip import HoverTooltip
from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.core.config.ui_preferences_store import LessonBuilderFieldSettings
from kursplaner.core.usecases.path_settings_usecase import PathSettingsUseCase


class SettingsWindow(ScrollablePopupWindow):
    """Stellt die GUI-Komponente Settings Window bereit.

    Die Klasse kapselt Bedienlogik und delegiert fachliche Entscheidungen an Use Cases.
    """

    def __init__(
        self,
        master,
        path_values: dict[str, str],
        on_saved=None,
        ub_past_cutoff_time: time | None = None,
        on_ub_past_cutoff_saved=None,
        lesson_builder_field_settings: LessonBuilderFieldSettings | None = None,
        on_lesson_builder_fields_saved=None,
        theme_key: str | None = None,
        path_settings_usecase: PathSettingsUseCase | None = None,
    ):
        """Initialisiert den Einstellungen-Dialog für Pfadwerte."""
        super().__init__(
            master,
            title="Einstellungen",
            geometry="900x500",
            minsize=(760, 340),
            theme_key=theme_key,
        )

        self.on_saved = on_saved
        self.on_ub_past_cutoff_saved = on_ub_past_cutoff_saved
        self.on_lesson_builder_fields_saved = on_lesson_builder_fields_saved
        if path_settings_usecase is None:
            raise RuntimeError("PathSettingsUseCase fehlt in SettingsWindow-Verdrahtung.")
        self.path_settings_usecase = path_settings_usecase

        cutoff = ub_past_cutoff_time or time(hour=15, minute=0)
        self.ub_cutoff_hour_var = tk.StringVar(value=f"{int(cutoff.hour):02d}")
        self.ub_cutoff_minute_var = tk.StringVar(value=f"{int(cutoff.minute):02d}")
        builder_fields = lesson_builder_field_settings or LessonBuilderFieldSettings()
        self.show_kompetenzen_var = tk.BooleanVar(value=bool(builder_fields.show_kompetenzen))
        self.show_stundenziel_var = tk.BooleanVar(value=bool(builder_fields.show_stundenziel))

        self.path_vars: dict[str, tk.StringVar] = {
            field.key: tk.StringVar(value=path_values.get(field.key, ""))
            for field in self.path_settings_usecase.path_field_definitions()
        }
        self._tooltips: list[HoverTooltip] = []

        self._build_ui()
        self._apply_theme()

    def _apply_theme(self):
        """Wendet Theme-Farben auf Fenster und ttk-Styles an."""
        self.apply_theme()

    def _build_ui(self):
        """Erzeugt Eingabefelder und Buttons für die Pfadkonfiguration."""
        root = ttk.Frame(self.content, padding=16)
        root.pack(fill="both", expand=True)

        paths = ttk.LabelFrame(root, text="Pfad-Einstellungen")
        paths.pack(fill="x", expand=True)

        row = 0
        for field in self.path_settings_usecase.path_field_definitions():
            label = ttk.Label(paths, text=field.label)
            label.grid(
                row=row,
                column=0,
                sticky="w",
                pady=((10 if row == 0 else 8), 4),
                padx=(10, 0),
            )
            self._tooltips.append(HoverTooltip(label, field.help_text))
            row += 1
            entry = ttk.Entry(paths, textvariable=self.path_vars[field.key])
            entry.grid(
                row=row,
                column=0,
                sticky="ew",
                padx=(10, 0),
                pady=(0, 4),
            )
            self._tooltips.append(HoverTooltip(entry, field.help_text))
            ttk.Button(paths, text="Auswählen…", command=lambda key=field.key: self._pick_path(key)).grid(
                row=row,
                column=1,
                padx=10,
                pady=(0, 4),
            )
            row += 1

        paths.columnconfigure(0, weight=1)

        ub_rules = ttk.LabelFrame(root, text="UB-Vergangenheitsregel")
        ub_rules.pack(fill="x", expand=False, pady=(10, 0))

        ttk.Label(
            ub_rules,
            text="UBs am aktuellen Datum zählen ab folgender Uhrzeit als Vergangenheit:",
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(10, 4))
        ttk.Spinbox(ub_rules, from_=0, to=23, width=4, textvariable=self.ub_cutoff_hour_var).grid(
            row=1,
            column=0,
            sticky="w",
            padx=(10, 4),
            pady=(0, 10),
        )
        ttk.Label(ub_rules, text=":").grid(row=1, column=1, sticky="w", pady=(0, 10))
        ttk.Spinbox(ub_rules, from_=0, to=59, width=4, textvariable=self.ub_cutoff_minute_var).grid(
            row=1,
            column=2,
            sticky="w",
            padx=(4, 0),
            pady=(0, 10),
        )
        ttk.Label(ub_rules, text="(24h-Format)").grid(row=1, column=3, sticky="w", padx=(8, 0), pady=(0, 10))

        lesson_builder_rules = ttk.LabelFrame(root, text="Einheit planen: optionale Felder")
        lesson_builder_rules.pack(fill="x", expand=False, pady=(10, 0))
        ttk.Checkbutton(
            lesson_builder_rules,
            text="Kompetenzen anzeigen",
            variable=self.show_kompetenzen_var,
        ).pack(anchor="w", padx=10, pady=(10, 4))
        ttk.Checkbutton(
            lesson_builder_rules,
            text="Stundenziel anzeigen",
            variable=self.show_stundenziel_var,
        ).pack(anchor="w", padx=10, pady=(0, 10))

        buttons = ttk.Frame(root)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Speichern", command=self._save).pack(side="left")
        ttk.Button(buttons, text="Abbrechen", command=self.destroy).pack(side="right")

    def _current_values(self) -> dict[str, str]:
        return {key: var.get().strip() for key, var in self.path_vars.items()}

    def _pick_path(self, key: str):
        """Öffnet Dateidialog passend zum Pfadtyp des gewählten Felds."""
        field = self.path_settings_usecase.path_field_by_key(key)
        if field is None:
            return
        current = self.path_settings_usecase.resolve_for_key(self._current_values(), key)
        initial = current if current.exists() else current.parent
        if field.kind == "file":
            selected = filedialog.askopenfilename(
                parent=self,
                title=field.pick_title,
                initialdir=str(initial),
                filetypes=[("JSON", "*.json"), ("Alle Dateien", "*.*")],
            )
        else:
            selected = filedialog.askdirectory(
                parent=self,
                title=field.pick_title,
                initialdir=str(initial),
            )

        if selected:
            self.path_vars[key].set(selected)

    def _current_ub_cutoff_time(self) -> time:
        hour_text = self.ub_cutoff_hour_var.get().strip()
        minute_text = self.ub_cutoff_minute_var.get().strip()
        hour = int(hour_text) if hour_text.isdigit() else 15
        minute = int(minute_text) if minute_text.isdigit() else 0
        hour = max(0, min(23, hour))
        minute = max(0, min(59, minute))
        return time(hour=hour, minute=minute)

    def _save(self):
        """Validiert und speichert die eingegebenen Pfade."""
        values = self._current_values()

        issues = self.path_settings_usecase.validate_values(values)
        if issues:
            first = issues[0]
            choose_other = messagebox.askyesno(
                "Einstellungen",
                f"{first.message}\n\nMöchten Sie stattdessen einen anderen Ort auswählen?",
                parent=self,
            )
            if choose_other:
                self._pick_path(first.key)
            return

        saved = self.path_settings_usecase.save_values(values)
        if self.on_saved:
            self.on_saved(saved)
        if self.on_ub_past_cutoff_saved:
            self.on_ub_past_cutoff_saved(self._current_ub_cutoff_time())
        if self.on_lesson_builder_fields_saved:
            self.on_lesson_builder_fields_saved(
                LessonBuilderFieldSettings(
                    show_kompetenzen=bool(self.show_kompetenzen_var.get()),
                    show_stundenziel=bool(self.show_stundenziel_var.get()),
                )
            )
        self.destroy()
