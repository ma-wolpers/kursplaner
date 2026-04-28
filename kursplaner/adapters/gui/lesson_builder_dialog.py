import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk

from kursplaner.adapters.gui.help_catalog import LESSON_BUILDER_HELP
from kursplaner.adapters.gui.hover_tooltip import HoverTooltip
from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.adapters.gui.selection_overlay_controller import SelectionOverlayController
from kursplaner.adapters.gui.ui_theme import get_theme
from kursplaner.adapters.gui.wrapped_text_field import WrappedTextField


@dataclass(frozen=True)
class LessonBuildResult:
    """Rückgabedaten des Dialogs für die Erstellung einer Unterrichtseinheit."""

    title: str
    topic: str
    oberthema: str
    stundenziel: str
    kompetenzen_refs: list[str]
    inhalte_refs: list[str]
    methodik_refs: list[str]


@dataclass(frozen=True)
class LessonKompetenzenSelectionResult:
    """Rückgabedaten für den Kompetenzen-Auswahl-Dialog in bestehenden Einheiten."""

    kompetenzen_refs: list[str]


class LessonBuilderDialog(ScrollablePopupWindow):
    """Dialog zur strukturierten Erfassung von Einheitsmetadaten und Referenzen."""

    def __init__(
        self,
        master,
        date_label: str,
        title_initial: str,
        topic_initial: str,
        oberthema_initial: str,
        kompetenzen_options: list[str],
        stundenziel_options: list[str],
        inhalte_options: list[str],
        methodik_options: list[str],
        kompetenzen_hint: str = "",
        stundenziel_hint: str = "",
        inhalte_hint: str = "",
        methodik_hint: str = "",
        kompetenzen_initial: list[str] | None = None,
        stundenziel_initial: str = "",
        inhalte_initial: list[str] | None = None,
        methodik_initial: list[str] | None = None,
        ub_sections: list[tuple[str, list[str]]] | None = None,
        ub_error_hint: str = "",
        show_kompetenzen_field: bool = True,
        show_stundenziel_field: bool = True,
        theme_key: str | None = None,
    ):
        """Initialisiert den Dialog zum kuratierten Zusammenstellen einer Einheit."""
        super().__init__(
            master,
            title="Einheit planen",
            geometry="980x620",
            minsize=(880, 460),
            theme_key=theme_key,
        )

        self.result: LessonBuildResult | None = None

        self.kompetenzen_options = kompetenzen_options
        self.stundenziel_options = stundenziel_options
        self.inhalte_options = inhalte_options
        self.methodik_options = methodik_options
        self.kompetenzen_hint = kompetenzen_hint.strip()
        self.stundenziel_hint = stundenziel_hint.strip()
        self.inhalte_hint = inhalte_hint.strip()
        self.methodik_hint = methodik_hint.strip()
        self.ub_sections = [(str(title), list(values)) for title, values in (ub_sections or [])]
        self.ub_error_hint = str(ub_error_hint or "").strip()
        self.show_kompetenzen_field = bool(show_kompetenzen_field)
        self.show_stundenziel_field = bool(show_stundenziel_field)

        self.inhalte_selected: list[str] = list(inhalte_initial or [])
        self.methodik_selected: list[str] = list(methodik_initial or [])
        self._tooltips: list[HoverTooltip] = []

        self._build_ui(date_label)
        self.overlay_controller = SelectionOverlayController(
            self,
            get_items=self._options_for_field,
            on_pick=self._on_overlay_pick,
            is_heading=self._is_heading,
        )
        self._bind_global_overlay_close()
        self.bind("<Control-Return>", self._on_ctrl_enter_accept)
        self.bind("<Control-KP_Enter>", self._on_ctrl_enter_accept)
        self._apply_theme()

        self.title_field.set(title_initial)
        self.topic_field.set(topic_initial)
        self.oberthema_field.set(oberthema_initial)
        if self.kompetenzen_field is not None:
            self.kompetenzen_field.set(" | ".join(kompetenzen_initial or []))
        if self.stundenziel_field is not None:
            self.stundenziel_field.set(stundenziel_initial)

    def _apply_theme(self):
        """Wendet das übergebene Theme auf das Dialogfenster an."""
        self.apply_theme()

    def _build_ui(self, date_label: str):
        """Erzeugt Eingabefelder mit Overlay-gestützter Auswahl."""
        root = ttk.Frame(self.content, padding=16)
        root.pack(fill="both", expand=True)

        basics = ttk.LabelFrame(root, text="Einheitsangaben")
        basics.pack(fill="both", expand=True, pady=(0, 10))

        ttk.Label(basics, text=f"Datum: {date_label}").grid(
            row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(10, 4)
        )

        title_label = ttk.Label(basics, text="Titel (Dateiname)")
        title_label.grid(row=1, column=0, sticky="w", padx=(10, 8), pady=4)
        self.title_field = WrappedTextField(basics, height=2)
        self.title_field.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(0, 10), pady=4)
        self._tooltips.append(HoverTooltip(title_label, LESSON_BUILDER_HELP["title"]))
        self._tooltips.append(HoverTooltip(self.title_field.text, LESSON_BUILDER_HELP["title"]))

        topic_label = ttk.Label(basics, text="Stundenthema")
        topic_label.grid(row=2, column=0, sticky="w", padx=(10, 8), pady=4)
        self.topic_field = WrappedTextField(basics, height=2)
        self.topic_field.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(0, 10), pady=4)
        self._tooltips.append(HoverTooltip(topic_label, LESSON_BUILDER_HELP["topic"]))
        self._tooltips.append(HoverTooltip(self.topic_field.text, LESSON_BUILDER_HELP["topic"]))

        oberthema_label = ttk.Label(basics, text="Oberthema")
        oberthema_label.grid(row=3, column=0, sticky="w", padx=(10, 8), pady=4)
        self.oberthema_field = WrappedTextField(basics, height=2)
        self.oberthema_field.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(0, 10), pady=4)
        self._tooltips.append(HoverTooltip(oberthema_label, LESSON_BUILDER_HELP["oberthema"]))
        self._tooltips.append(HoverTooltip(self.oberthema_field.text, LESSON_BUILDER_HELP["oberthema"]))

        row = 4
        if self.show_kompetenzen_field:
            kompetenzen_label = ttk.Label(basics, text="Kompetenzen")
            kompetenzen_label.grid(row=row, column=0, sticky="w", padx=(10, 8), pady=4)
            self.kompetenzen_field = WrappedTextField(basics, height=3)
            self.kompetenzen_field.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(0, 10), pady=4)
            self._bind_overlay_field(self.kompetenzen_field, "kompetenzen")
            self._tooltips.append(HoverTooltip(kompetenzen_label, LESSON_BUILDER_HELP["kompetenzen"]))
            self._tooltips.append(HoverTooltip(self.kompetenzen_field.text, LESSON_BUILDER_HELP["kompetenzen"]))
            row += 1
            ttk.Label(basics, text=self.kompetenzen_hint, wraplength=760, justify="left").grid(
                row=row, column=1, columnspan=2, sticky="w", padx=(0, 10), pady=(0, 4)
            )
            row += 1
        else:
            self.kompetenzen_field = None

        if self.show_stundenziel_field:
            stundenziel_label = ttk.Label(basics, text="Stundenziel")
            stundenziel_label.grid(row=row, column=0, sticky="w", padx=(10, 8), pady=4)
            self.stundenziel_field = WrappedTextField(basics, height=3)
            self.stundenziel_field.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(0, 10), pady=4)
            self._bind_overlay_field(self.stundenziel_field, "stundenziel")
            self._tooltips.append(HoverTooltip(stundenziel_label, LESSON_BUILDER_HELP["stundenziel"]))
            self._tooltips.append(HoverTooltip(self.stundenziel_field.text, LESSON_BUILDER_HELP["stundenziel"]))
            row += 1
            ttk.Label(basics, text=self.stundenziel_hint, wraplength=760, justify="left").grid(
                row=row, column=1, columnspan=2, sticky="w", padx=(0, 10), pady=(0, 4)
            )
            row += 1
        else:
            self.stundenziel_field = None

        inhalte_label = ttk.Label(basics, text="Inhalte")
        inhalte_label.grid(row=row, column=0, sticky="nw", padx=(10, 8), pady=4)
        self.inhalte_query_field = WrappedTextField(basics, height=2)
        self.inhalte_query_field.grid(row=row, column=1, sticky="ew", padx=(0, 10), pady=4)
        self._bind_overlay_field(self.inhalte_query_field, "inhalte", enable_filter_refresh=True)
        self._tooltips.append(HoverTooltip(inhalte_label, LESSON_BUILDER_HELP["inhalte"]))
        self._tooltips.append(HoverTooltip(self.inhalte_query_field.text, LESSON_BUILDER_HELP["inhalte"]))
        self.inhalte_chip_frame = ttk.Frame(basics)
        self.inhalte_chip_frame.grid(row=row, column=2, sticky="w", padx=(0, 10), pady=4)
        row += 1
        ttk.Label(basics, text=self.inhalte_hint, wraplength=760, justify="left").grid(
            row=row, column=1, columnspan=2, sticky="w", padx=(0, 10), pady=(0, 4)
        )
        row += 1

        methodik_label = ttk.Label(basics, text="Methodik")
        methodik_label.grid(row=row, column=0, sticky="nw", padx=(10, 8), pady=4)
        self.methodik_query_field = WrappedTextField(basics, height=2)
        self.methodik_query_field.grid(row=row, column=1, sticky="ew", padx=(0, 10), pady=4)
        self._bind_overlay_field(self.methodik_query_field, "methodik", enable_filter_refresh=True)
        self._tooltips.append(HoverTooltip(methodik_label, LESSON_BUILDER_HELP["methodik"]))
        self._tooltips.append(HoverTooltip(self.methodik_query_field.text, LESSON_BUILDER_HELP["methodik"]))
        self.methodik_chip_frame = ttk.Frame(basics)
        self.methodik_chip_frame.grid(row=row, column=2, sticky="w", padx=(0, 10), pady=4)
        row += 1
        ttk.Label(basics, text=self.methodik_hint, wraplength=760, justify="left").grid(
            row=row, column=1, columnspan=2, sticky="w", padx=(0, 10), pady=(0, 10)
        )

        basics.columnconfigure(1, weight=1)

        ub_frame = ttk.LabelFrame(root, text="UB-Punkte der letzten Besuche", padding=10)
        ub_frame.pack(fill="x", pady=(0, 10))
        self._render_ub_sections(ub_frame)

        tab_fields = [self.title_field, self.topic_field, self.oberthema_field]
        if self.kompetenzen_field is not None:
            tab_fields.append(self.kompetenzen_field)
        if self.stundenziel_field is not None:
            tab_fields.append(self.stundenziel_field)
        tab_fields.extend([self.inhalte_query_field, self.methodik_query_field])
        self._bind_tab_navigation(tab_fields)

        self._render_inhalte_chips()
        self._render_methodik_chips()

        buttons = ttk.Frame(root)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Übernehmen", command=self._accept).pack(side="left")
        ttk.Button(buttons, text="Abbrechen", command=self.destroy).pack(side="right")

    @staticmethod
    def _format_ub_list(items: list[str]) -> str:
        cleaned = [str(entry).strip() for entry in items if str(entry).strip()]
        if not cleaned:
            return "- Keine Einträge vorhanden."
        return "\n".join(f"- {entry}" for entry in cleaned)

    def _render_ub_sections(self, parent: ttk.LabelFrame) -> None:
        theme = get_theme(self.theme_key)
        fg = str(theme.get("fg_primary", "#111827"))
        bg = str(theme.get("bg_main", "#FFFFFF"))

        if not self.ub_sections:
            hint = "Noch keine UB-Einträge gefunden."
            if self.ub_error_hint:
                hint = (
                    "Hinweis: Die UB-Punkte konnten aktuell nicht geladen werden. "
                    "Bitte Logging prüfen.\n"
                    f"{self.ub_error_hint}"
                )
            self._render_ub_text_label(parent, hint, fg=fg, bg=bg)
            return

        for title, values in self.ub_sections:
            section = ttk.Frame(parent)
            section.pack(fill="x", pady=(0, 8))
            self._render_ub_text_label(section, str(title).strip(), fg=fg, bg=bg, bold=True)
            self._render_ub_text_label(section, self._format_ub_list(values), fg=fg, bg=bg)

    @staticmethod
    def _render_ub_text_label(parent, text: str, *, fg: str, bg: str, bold: bool = False) -> None:
        font = ("Segoe UI", 10, "bold") if bold else ("Segoe UI", 10)
        tk.Label(
            parent,
            text=text,
            justify="left",
            anchor="w",
            wraplength=900,
            fg=fg,
            bg=bg,
            font=font,
        ).pack(anchor="w")

    def _bind_overlay_field(self, field_widget: WrappedTextField, field_name: str, enable_filter_refresh: bool = False):
        text = field_widget.text
        text.bind("<FocusIn>", lambda _e: self.overlay_controller.open(field_name, text))
        text.bind("<Button-1>", lambda _e: self.overlay_controller.open(field_name, text))
        text.bind("<Down>", self._overlay_move_down)
        text.bind("<Up>", self._overlay_move_up)
        text.bind("<Return>", self._overlay_select_from_field)
        text.bind("<Control-Return>", self._on_ctrl_enter_accept)
        text.bind("<Control-KP_Enter>", self._on_ctrl_enter_accept)
        if enable_filter_refresh:
            text.bind("<KeyRelease>", lambda _e: self._refresh_open_overlay(field_name))

    def _on_ctrl_enter_accept(self, _event=None):
        self._accept()
        return "break"

    def _bind_tab_navigation(self, fields: list[WrappedTextField]):
        self._tab_order = [field.text for field in fields]
        self.bind("<Tab>", self._on_tab_next, add="+")
        self.bind("<Shift-Tab>", self._on_tab_prev, add="+")
        self.bind("<ISO_Left_Tab>", self._on_tab_prev, add="+")
        for text in self._tab_order:
            text.bind("<Tab>", self._on_tab_next, add="+")
            text.bind("<Shift-Tab>", self._on_tab_prev, add="+")
            text.bind("<ISO_Left_Tab>", self._on_tab_prev, add="+")

    def _on_tab_next(self, event):
        return self._move_tab_focus(getattr(event, "widget", None), +1)

    def _on_tab_prev(self, event):
        return self._move_tab_focus(getattr(event, "widget", None), -1)

    def _move_tab_focus(self, current_widget, direction: int):
        if not getattr(self, "_tab_order", None):
            return "break"
        try:
            current_index = self._tab_order.index(current_widget)
        except ValueError:
            target_index = 0 if direction > 0 else len(self._tab_order) - 1
            self._tab_order[target_index].focus_set()
            return "break"
        target_index = current_index + direction
        if 0 <= target_index < len(self._tab_order):
            self._tab_order[target_index].focus_set()
        return "break"

    def _bind_global_overlay_close(self):
        """Schließt Overlay bei Klick/Fokuswechsel außerhalb relevanter Widgets."""
        self.bind("<Button-1>", self._on_global_click, add="+")
        self.bind("<FocusIn>", self._on_global_focus_change, add="+")

    @staticmethod
    def _is_heading(item: str) -> bool:
        return str(item).strip().startswith("#")

    @staticmethod
    def _split_multi_values(text: str) -> list[str]:
        parts = [part.strip() for part in str(text).split(" | ")]
        return [part for part in parts if part]

    def _on_global_click(self, event):
        if not self.overlay_controller.is_open:
            return None
        widget = getattr(event, "widget", None)
        if self.overlay_controller.should_keep_open_for_widget(widget):
            return None
        self.overlay_controller.close()
        return None

    def _on_global_focus_change(self, _event):
        if not self.overlay_controller.is_open:
            return None
        focused = self.focus_get()
        if self.overlay_controller.should_keep_open_for_widget(focused):
            return None
        self.overlay_controller.close()
        return None

    def _options_for_field(self, field: str) -> list[str]:
        if field == "kompetenzen":
            return self.kompetenzen_options or ["# Keine Kompetenzen verfügbar"]
        if field == "stundenziel":
            return self.stundenziel_options or ["# Kein Stundenziel verfügbar"]
        if field == "inhalte":
            query = self.inhalte_query_field.get().strip().lower()
            base = self.inhalte_options
            if not query:
                return base or ["# Keine Inhalte verfügbar"]
            filtered = [item for item in base if (not self._is_heading(item)) and query in item.lower()]
            return filtered or ["# Keine Treffer"]
        if field == "methodik":
            query = self.methodik_query_field.get().strip().lower()
            base = self.methodik_options
            if not query:
                return base or ["# Keine Methodik verfügbar"]
            filtered = [item for item in base if (not self._is_heading(item)) and query in item.lower()]
            return filtered or ["# Keine Treffer"]
        return []

    def _refresh_open_overlay(self, expected_field: str):
        if self.overlay_controller.active_field == expected_field:
            self.overlay_controller.refresh()

    def _overlay_move_down(self, _event):
        if (
            not self.overlay_controller.is_open
            and self.overlay_controller.active_field
            and self.overlay_controller.active_anchor
        ):
            self.overlay_controller.open(self.overlay_controller.active_field, self.overlay_controller.active_anchor)
        self.overlay_controller.move(+1)
        return "break"

    def _overlay_move_up(self, _event):
        self.overlay_controller.move(-1)
        return "break"

    def _overlay_select_from_field(self, _event):
        if self.overlay_controller.is_open:
            self.overlay_controller.select_current()
            return "break"
        return None

    def _on_overlay_pick(self, field: str, value: str):
        if field == "kompetenzen":
            values = self._split_multi_values(self.kompetenzen_field.get())
            if value in values:
                values.remove(value)
            else:
                values.append(value)
            self.kompetenzen_field.set(" | ".join(values))
            return

        if field == "stundenziel":
            self.stundenziel_field.set(value)
            return

        if field == "inhalte":
            if value not in self.inhalte_selected:
                self.inhalte_selected.append(value)
                self._render_inhalte_chips()
            self.inhalte_query_field.set("")
            self.overlay_controller.refresh()
            return

        if field == "methodik":
            if value not in self.methodik_selected:
                self.methodik_selected.append(value)
                self._render_methodik_chips()
            self.methodik_query_field.set("")
            self.overlay_controller.refresh()

    def _render_inhalte_chips(self):
        for child in self.inhalte_chip_frame.winfo_children():
            child.destroy()
        for item in self.inhalte_selected:
            chip = ttk.Frame(self.inhalte_chip_frame)
            chip.pack(side="left", padx=(0, 4))
            ttk.Label(chip, text=item).pack(side="left")
            ttk.Button(chip, text="x", width=2, command=lambda value=item: self._remove_inhalt(value)).pack(
                side="left", padx=(2, 0)
            )

    def _render_methodik_chips(self):
        for child in self.methodik_chip_frame.winfo_children():
            child.destroy()
        for item in self.methodik_selected:
            chip = ttk.Frame(self.methodik_chip_frame)
            chip.pack(side="left", padx=(0, 4))
            ttk.Label(chip, text=item).pack(side="left")
            ttk.Button(chip, text="x", width=2, command=lambda value=item: self._remove_methodik(value)).pack(
                side="left", padx=(2, 0)
            )

    def _remove_inhalt(self, value: str):
        self.inhalte_selected = [item for item in self.inhalte_selected if item != value]
        self._render_inhalte_chips()

    def _remove_methodik(self, value: str):
        self.methodik_selected = [item for item in self.methodik_selected if item != value]
        self._render_methodik_chips()

    def _accept(self):
        """Validiert die Eingabe und übernimmt das Ergebnis in `self.result`."""
        title = self.title_field.get()
        topic = self.topic_field.get()
        if not title:
            messagebox.showerror("Einheit planen", "Bitte einen Titel (Dateiname) eingeben.", parent=self)
            return
        if not topic:
            messagebox.showerror("Einheit planen", "Bitte ein Stundenthema eingeben.", parent=self)
            return

        stundenziel = self.stundenziel_field.get() if self.stundenziel_field is not None else ""

        kompetenzen_values: list[str] = []
        if self.kompetenzen_field is not None:
            kompetenzen_values = [
                value for value in self._split_multi_values(self.kompetenzen_field.get()) if not self._is_heading(value)
            ]

        self.result = LessonBuildResult(
            title=title,
            topic=topic,
            oberthema=self.oberthema_field.get(),
            stundenziel=stundenziel,
            kompetenzen_refs=kompetenzen_values,
            inhalte_refs=list(self.inhalte_selected),
            methodik_refs=list(self.methodik_selected),
        )
        self.destroy()


def ask_lesson_builder(
    parent,
    date_label: str,
    title_initial: str,
    topic_initial: str,
    oberthema_initial: str,
    kompetenzen_options: list[str],
    stundenziel_options: list[str],
    inhalte_options: list[str],
    methodik_options: list[str],
    kompetenzen_hint: str = "",
    stundenziel_hint: str = "",
    inhalte_hint: str = "",
    methodik_hint: str = "",
    kompetenzen_initial: list[str] | None = None,
    stundenziel_initial: str = "",
    inhalte_initial: list[str] | None = None,
    methodik_initial: list[str] | None = None,
    ub_sections: list[tuple[str, list[str]]] | None = None,
    ub_error_hint: str = "",
    show_kompetenzen_field: bool = True,
    show_stundenziel_field: bool = True,
    theme_key: str | None = None,
) -> LessonBuildResult | None:
    """Öffnet den Builder-Dialog modal und gibt das übernommene Ergebnis zurück."""
    dialog = LessonBuilderDialog(
        master=parent,
        date_label=date_label,
        title_initial=title_initial,
        topic_initial=topic_initial,
        oberthema_initial=oberthema_initial,
        kompetenzen_options=kompetenzen_options,
        stundenziel_options=stundenziel_options,
        inhalte_options=inhalte_options,
        methodik_options=methodik_options,
        kompetenzen_hint=kompetenzen_hint,
        stundenziel_hint=stundenziel_hint,
        inhalte_hint=inhalte_hint,
        methodik_hint=methodik_hint,
        kompetenzen_initial=kompetenzen_initial,
        stundenziel_initial=stundenziel_initial,
        inhalte_initial=inhalte_initial,
        methodik_initial=methodik_initial,
        ub_sections=ub_sections,
        ub_error_hint=ub_error_hint,
        show_kompetenzen_field=show_kompetenzen_field,
        show_stundenziel_field=show_stundenziel_field,
        theme_key=theme_key,
    )
    dialog.grab_set()
    _activate_modal_focus(dialog, dialog.title_field.text)
    dialog.wait_window()
    return dialog.result


def _activate_modal_focus(dialog: ScrollablePopupWindow, field_widget) -> None:
    """Setzt den initialen Eingabefokus robust in das gewünschte Popup-Feld."""
    try:
        dialog.wait_visibility()
        dialog.lift()
        dialog.focus_force()
        field_widget.focus_set()
        if isinstance(field_widget, tk.Text):
            field_widget.mark_set("insert", "end-1c")
            field_widget.see("insert")
    except tk.TclError:
        return


class LessonKompetenzenSelectionDialog(ScrollablePopupWindow):
    """Kompakter Dialog für die Auswahl von Kompetenzen."""

    def __init__(
        self,
        master,
        date_label: str,
        kompetenzen_options: list[str],
        kompetenzen_initial: list[str] | None = None,
        kompetenzen_hint: str = "",
        theme_key: str | None = None,
    ):
        super().__init__(
            master,
            title="Kompetenzen wählen",
            geometry="780x420",
            minsize=(680, 320),
            theme_key=theme_key,
        )
        self.result: LessonKompetenzenSelectionResult | None = None
        self.kompetenzen_options = kompetenzen_options
        self.kompetenzen_hint = kompetenzen_hint.strip()

        root = ttk.Frame(self.content, padding=16)
        root.pack(fill="both", expand=True)

        basics = ttk.LabelFrame(root, text="Auswahl")
        basics.pack(fill="both", expand=True, pady=(0, 10))

        ttk.Label(basics, text=f"Datum: {date_label}").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 4)
        )

        kompetenzen_label = ttk.Label(basics, text="Kompetenzen")
        kompetenzen_label.grid(row=1, column=0, sticky="w", padx=(10, 8), pady=4)
        self.kompetenzen_field = WrappedTextField(basics, height=4)
        self.kompetenzen_field.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=4)
        self.kompetenzen_field.set(" | ".join(kompetenzen_initial or []))

        self.overlay_controller = SelectionOverlayController(
            self,
            get_items=self._options_for_field,
            on_pick=self._on_overlay_pick,
            is_heading=lambda item: str(item).strip().startswith("#"),
        )
        self._bind_overlay_field(self.kompetenzen_field, "kompetenzen")
        self._bind_tab_navigation([self.kompetenzen_field])
        self.bind("<Escape>", self._on_escape)
        self.bind("<Control-Return>", self._on_ctrl_enter_accept)
        self.bind("<Control-KP_Enter>", self._on_ctrl_enter_accept)

        ttk.Label(basics, text=self.kompetenzen_hint, wraplength=680, justify="left").grid(
            row=2, column=1, sticky="w", padx=(0, 10), pady=(0, 10)
        )
        basics.columnconfigure(1, weight=1)

        self.bind("<Button-1>", self._on_global_click, add="+")
        self.bind("<FocusIn>", self._on_global_focus_change, add="+")

        self._tooltips = [
            HoverTooltip(kompetenzen_label, LESSON_BUILDER_HELP["kompetenzen"]),
            HoverTooltip(self.kompetenzen_field.text, LESSON_BUILDER_HELP["kompetenzen"]),
        ]

        buttons = ttk.Frame(root)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Übernehmen", command=self._accept).pack(side="left")
        ttk.Button(buttons, text="Abbrechen", command=self.destroy).pack(side="right")
        self.apply_theme()

    @staticmethod
    def _split_multi_values(text: str) -> list[str]:
        parts = [part.strip() for part in str(text).split(" | ")]
        return [part for part in parts if part]

    def _bind_overlay_field(self, field_widget: WrappedTextField, field_name: str):
        text = field_widget.text
        text.bind("<FocusIn>", lambda _e: self.overlay_controller.open(field_name, text))
        text.bind("<Button-1>", lambda _e: self.overlay_controller.open(field_name, text))
        text.bind("<Down>", self._overlay_move_down)
        text.bind("<Up>", self._overlay_move_up)
        text.bind("<Return>", self._overlay_select_from_field)
        text.bind("<Control-Return>", self._on_ctrl_enter_accept)
        text.bind("<Control-KP_Enter>", self._on_ctrl_enter_accept)

    def _bind_tab_navigation(self, fields: list[WrappedTextField]):
        self._tab_order = [field.text for field in fields]
        self.bind("<Tab>", self._on_tab_next, add="+")
        self.bind("<Shift-Tab>", self._on_tab_prev, add="+")
        self.bind("<ISO_Left_Tab>", self._on_tab_prev, add="+")
        for text in self._tab_order:
            text.bind("<Tab>", self._on_tab_next, add="+")
            text.bind("<Shift-Tab>", self._on_tab_prev, add="+")
            text.bind("<ISO_Left_Tab>", self._on_tab_prev, add="+")

    def _on_tab_next(self, event):
        return self._move_tab_focus(getattr(event, "widget", None), +1)

    def _on_tab_prev(self, event):
        return self._move_tab_focus(getattr(event, "widget", None), -1)

    def _move_tab_focus(self, current_widget, direction: int):
        if not getattr(self, "_tab_order", None):
            return "break"
        try:
            current_index = self._tab_order.index(current_widget)
        except ValueError:
            target_index = 0 if direction > 0 else len(self._tab_order) - 1
            self._tab_order[target_index].focus_set()
            return "break"
        target_index = current_index + direction
        if 0 <= target_index < len(self._tab_order):
            self._tab_order[target_index].focus_set()
        return "break"

    def _options_for_field(self, field: str) -> list[str]:
        if field == "kompetenzen":
            return self.kompetenzen_options or ["# Keine Kompetenzen verfügbar"]
        return []

    def _on_overlay_pick(self, field: str, value: str):
        if str(value).strip().startswith("#"):
            return
        if field == "kompetenzen":
            values = self._split_multi_values(self.kompetenzen_field.get())
            if value in values:
                values.remove(value)
            else:
                values.append(value)
            self.kompetenzen_field.set(" | ".join(values))

    def _on_escape(self, _event=None):
        self._request_close()
        return "break"

    def _on_ctrl_enter_accept(self, _event=None):
        self.overlay_controller.close()
        self._accept()
        return "break"

    def _overlay_move_down(self, _event):
        self.overlay_controller.move(+1)
        return "break"

    def _overlay_move_up(self, _event):
        self.overlay_controller.move(-1)
        return "break"

    def _overlay_select_from_field(self, _event):
        if self.overlay_controller.is_open:
            self.overlay_controller.select_current()
            return "break"
        return None

    def _on_global_click(self, event):
        if not self.overlay_controller.is_open:
            return None
        widget = getattr(event, "widget", None)
        if self.overlay_controller.should_keep_open_for_widget(widget):
            return None
        self.overlay_controller.close()
        return None

    def _on_global_focus_change(self, _event):
        if not self.overlay_controller.is_open:
            return None
        focused = self.focus_get()
        if self.overlay_controller.should_keep_open_for_widget(focused):
            return None
        self.overlay_controller.close()
        return None

    def _accept(self):
        self.result = LessonKompetenzenSelectionResult(
            kompetenzen_refs=self._split_multi_values(self.kompetenzen_field.get()),
        )
        self.destroy()


def ask_lesson_kompetenzen_selection(
    parent,
    date_label: str,
    kompetenzen_options: list[str],
    kompetenzen_initial: list[str] | None = None,
    kompetenzen_hint: str = "",
    theme_key: str | None = None,
) -> LessonKompetenzenSelectionResult | None:
    """Öffnet den Auswahl-Dialog für Kompetenzen modal."""
    dialog = LessonKompetenzenSelectionDialog(
        master=parent,
        date_label=date_label,
        kompetenzen_options=kompetenzen_options,
        kompetenzen_initial=kompetenzen_initial,
        kompetenzen_hint=kompetenzen_hint,
        theme_key=theme_key,
    )
    dialog.grab_set()
    _activate_modal_focus(dialog, dialog.kompetenzen_field.text)
    dialog.wait_window()
    return dialog.result


class LessonStundenzielSelectionDialog(ScrollablePopupWindow):
    """Kompakter Dialog für die Auswahl des Stundenziels."""

    def __init__(
        self,
        master,
        date_label: str,
        stundenziel_options: list[str],
        stundenziel_initial: str = "",
        stundenziel_hint: str = "",
        theme_key: str | None = None,
    ):
        super().__init__(
            master,
            title="Stundenziel wählen",
            geometry="760x380",
            minsize=(660, 300),
            theme_key=theme_key,
        )
        self.result: str | None = None
        self.stundenziel_options = stundenziel_options
        self.stundenziel_hint = stundenziel_hint.strip()

        root = ttk.Frame(self.content, padding=16)
        root.pack(fill="both", expand=True)

        basics = ttk.LabelFrame(root, text="Auswahl")
        basics.pack(fill="both", expand=True, pady=(0, 10))

        ttk.Label(basics, text=f"Datum: {date_label}").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 4)
        )

        stundenziel_label = ttk.Label(basics, text="Stundenziel")
        stundenziel_label.grid(row=1, column=0, sticky="w", padx=(10, 8), pady=4)
        self.stundenziel_field = WrappedTextField(basics, height=3)
        self.stundenziel_field.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=4)
        self.stundenziel_field.set(stundenziel_initial)

        self.overlay_controller = SelectionOverlayController(
            self,
            get_items=self._options_for_field,
            on_pick=self._on_overlay_pick,
            is_heading=lambda item: str(item).strip().startswith("#"),
        )
        self._bind_overlay_field(self.stundenziel_field, "stundenziel")
        self._bind_tab_navigation([self.stundenziel_field])
        self.bind("<Escape>", self._on_escape)
        self.bind("<Control-Return>", self._on_ctrl_enter_accept)
        self.bind("<Control-KP_Enter>", self._on_ctrl_enter_accept)

        ttk.Label(basics, text=self.stundenziel_hint, wraplength=640, justify="left").grid(
            row=2, column=1, sticky="w", padx=(0, 10), pady=(0, 10)
        )
        basics.columnconfigure(1, weight=1)

        self.bind("<Button-1>", self._on_global_click, add="+")
        self.bind("<FocusIn>", self._on_global_focus_change, add="+")

        self._tooltips = [
            HoverTooltip(stundenziel_label, LESSON_BUILDER_HELP["stundenziel"]),
            HoverTooltip(self.stundenziel_field.text, LESSON_BUILDER_HELP["stundenziel"]),
        ]

        buttons = ttk.Frame(root)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Übernehmen", command=self._accept).pack(side="left")
        ttk.Button(buttons, text="Abbrechen", command=self.destroy).pack(side="right")
        self.apply_theme()

    def _bind_overlay_field(self, field_widget: WrappedTextField, field_name: str):
        text = field_widget.text
        text.bind("<FocusIn>", lambda _e: self.overlay_controller.open(field_name, text))
        text.bind("<Button-1>", lambda _e: self.overlay_controller.open(field_name, text))
        text.bind("<Down>", self._overlay_move_down)
        text.bind("<Up>", self._overlay_move_up)
        text.bind("<Return>", self._overlay_select_from_field)
        text.bind("<Control-Return>", self._on_ctrl_enter_accept)
        text.bind("<Control-KP_Enter>", self._on_ctrl_enter_accept)

    def _bind_tab_navigation(self, fields: list[WrappedTextField]):
        self._tab_order = [field.text for field in fields]
        self.bind("<Tab>", self._on_tab_next, add="+")
        self.bind("<Shift-Tab>", self._on_tab_prev, add="+")
        self.bind("<ISO_Left_Tab>", self._on_tab_prev, add="+")
        for text in self._tab_order:
            text.bind("<Tab>", self._on_tab_next, add="+")
            text.bind("<Shift-Tab>", self._on_tab_prev, add="+")
            text.bind("<ISO_Left_Tab>", self._on_tab_prev, add="+")

    def _on_tab_next(self, event):
        return self._move_tab_focus(getattr(event, "widget", None), +1)

    def _on_tab_prev(self, event):
        return self._move_tab_focus(getattr(event, "widget", None), -1)

    def _move_tab_focus(self, current_widget, direction: int):
        if not getattr(self, "_tab_order", None):
            return "break"
        try:
            current_index = self._tab_order.index(current_widget)
        except ValueError:
            target_index = 0 if direction > 0 else len(self._tab_order) - 1
            self._tab_order[target_index].focus_set()
            return "break"
        target_index = current_index + direction
        if 0 <= target_index < len(self._tab_order):
            self._tab_order[target_index].focus_set()
        return "break"

    def _options_for_field(self, field: str) -> list[str]:
        if field == "stundenziel":
            return self.stundenziel_options or ["# Kein Stundenziel verfügbar"]
        return []

    def _on_overlay_pick(self, _field: str, value: str):
        if str(value).strip().startswith("#"):
            return
        current_value = self.stundenziel_field.get().strip()
        if current_value == value:
            self.stundenziel_field.set("")
        else:
            self.stundenziel_field.set(value)

    def _overlay_move_down(self, _event):
        self.overlay_controller.move(+1)
        return "break"

    def _overlay_move_up(self, _event):
        self.overlay_controller.move(-1)
        return "break"

    def _overlay_select_from_field(self, _event):
        if self.overlay_controller.is_open:
            self.overlay_controller.select_current()
            return "break"
        return None

    def _on_global_click(self, event):
        if not self.overlay_controller.is_open:
            return None
        widget = getattr(event, "widget", None)
        if self.overlay_controller.should_keep_open_for_widget(widget):
            return None
        self.overlay_controller.close()
        return None

    def _on_global_focus_change(self, _event):
        if not self.overlay_controller.is_open:
            return None
        focused = self.focus_get()
        if self.overlay_controller.should_keep_open_for_widget(focused):
            return None
        self.overlay_controller.close()
        return None

    def _on_escape(self, _event=None):
        self._request_close()
        return "break"

    def _on_ctrl_enter_accept(self, _event=None):
        self.overlay_controller.close()
        self._accept()
        return "break"

    def _accept(self):
        self.result = self.stundenziel_field.get()
        self.destroy()


def ask_lesson_stundenziel_selection(
    parent,
    date_label: str,
    stundenziel_options: list[str],
    stundenziel_initial: str = "",
    stundenziel_hint: str = "",
    theme_key: str | None = None,
) -> str | None:
    """Öffnet den Auswahl-Dialog für Stundenziel modal."""
    dialog = LessonStundenzielSelectionDialog(
        master=parent,
        date_label=date_label,
        stundenziel_options=stundenziel_options,
        stundenziel_initial=stundenziel_initial,
        stundenziel_hint=stundenziel_hint,
        theme_key=theme_key,
    )
    dialog.grab_set()
    _activate_modal_focus(dialog, dialog.stundenziel_field.text)
    dialog.wait_window()
    return dialog.result
