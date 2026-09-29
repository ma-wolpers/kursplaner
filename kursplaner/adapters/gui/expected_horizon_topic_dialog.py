"""Modaler Dialog: Oberthemen für einen Kompetenzhorizont auswählen.

Zeigt die Kandidaten aus `ExpectedHorizonTopicQueryUseCase` (chronologisch,
mit Zeitraum und Stundenzahl) als Checkbox-Liste, vorbelegt mit der
gespeicherten bzw. naheliegenden Auswahl. Warnt vor gespeicherten, aber nicht
mehr verfügbaren Themen und vor Stunden mit ungültigem Oberthema. Enthält
keine fachlichen Regeln — Kandidaten, Reihenfolge und Vorbelegung kommen
fertig aus dem Use Case.
"""

from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets
from bw_gui.widgets import Checkbox

from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.core.usecases.expected_horizon_topic_query_usecase import (
    ExpectedHorizonTopicOption,
    ExpectedHorizonTopicOptions,
)


def _option_label(option: ExpectedHorizonTopicOption) -> str:
    """Anzeigetext einer Option: Thema, Zeitraum und Anzahl der Stunden."""
    unit_text = "Stunde" if option.unit_count == 1 else "Stunden"
    if option.first_date == option.last_date:
        span = f"{option.first_date:%d.%m.%Y}"
    else:
        span = f"{option.first_date:%d.%m.} – {option.last_date:%d.%m.%Y}"
    return f"{option.oberthema}   ({span}, {option.unit_count} {unit_text})"


def _cutoff_text(options: ExpectedHorizonTopicOptions) -> str:
    day = f"{options.cutoff.day:%d.%m.%Y}"
    return f"bis einschließlich {day}" if options.cutoff.includes_day else f"vor dem {day}"


class ExpectedHorizonTopicDialog(ScrollablePopupWindow):
    """Checkbox-Liste der wählbaren Oberthemen eines Kompetenzhorizonts."""

    def __init__(self, master, *, options: ExpectedHorizonTopicOptions, theme_key: str | None = None) -> None:
        """Baut den Dialog auf.

        Args:
            master: Elternfenster.
            options: Ergebnis der Kandidatenabfrage (Optionen, Vorbelegung, Warnungen).
            theme_key: Optionaler Theme-Name; ``None`` übernimmt das Parent-Theme.
        """
        super().__init__(
            master,
            title="Kompetenzhorizont – Oberthemen",
            geometry="560x420",
            minsize=(480, 320),
            theme_key=theme_key,
        )
        self.result: list[str] | None = None
        self._options = options
        preselected = set(options.preselected)
        self._vars = [ui.BooleanVar(value=option.oberthema in preselected) for option in options.options]
        self._toggles: list[Checkbox] = []
        self._accept_button: widgets.Button | None = None
        self._build_ui()
        self.apply_theme()
        self._update_accept_state()
        self.after_idle(self._focus_first_toggle)

    def _build_ui(self) -> None:
        frame = widgets.Frame(self.content, padding=14)
        frame.pack(fill="both", expand=True)

        widgets.Label(
            frame,
            text=(
                "Welche Oberthemen soll der Kompetenzhorizont umfassen?\n"
                f"Angeboten werden Themen mit Unterrichtsstunden {_cutoff_text(self._options)}."
            ),
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        for warning in self._warnings():
            widgets.Label(frame, text=f"⚠ {warning}", justify="left", wraplength=500).pack(anchor="w", pady=(0, 6))

        list_frame = widgets.Frame(frame)
        list_frame.pack(fill="x", pady=(4, 0))
        for index, (option, var) in enumerate(zip(self._options.options, self._vars)):
            toggle = Checkbox(
                list_frame,
                text=_option_label(option),
                variable=var,
                on_select=lambda _selected: self._update_accept_state(),
            )
            toggle.pack(anchor="w", pady=1)
            self._register_nav(toggle, index)
            self._toggles.append(toggle)

        quick_row = widgets.Frame(frame)
        quick_row.pack(fill="x", pady=(10, 0))
        widgets.Button(quick_row, text="Alle", command=lambda: self._set_all(True)).pack(side="left")
        widgets.Button(quick_row, text="Keine", command=lambda: self._set_all(False)).pack(side="left", padx=(8, 0))

        widgets.Separator(frame, orient="horizontal").pack(fill="x", pady=12)
        button_row = widgets.Frame(frame)
        button_row.pack(fill="x")
        self._accept_button = widgets.Button(button_row, text="Übernehmen", command=self._accept)
        self._accept_button.pack(side="right")
        widgets.Button(button_row, text="Abbrechen", command=self.destroy).pack(side="right", padx=(0, 8))

    def _warnings(self) -> list[str]:
        """Warntexte für nicht verfügbare gespeicherte Themen und ungültige Oberthemen."""
        warnings: list[str] = []
        if self._options.unavailable_stored:
            names = ", ".join(self._options.unavailable_stored)
            warnings.append(f"Gespeichert, aber nicht mehr verfügbar: {names} – wird beim Export entfernt.")
        if self._options.invalid_unit_count:
            count = self._options.invalid_unit_count
            warnings.append(f"{count} Stunde(n) mit ungültigem Oberthema werden nicht berücksichtigt.")
        return warnings

    def _register_nav(self, toggle: Checkbox, index: int) -> None:
        """Pfeiltasten bewegen den Fokus in der Liste, Leertaste schaltet um."""
        toggle.bind("<Up>", lambda _e, i=index: self._focus_toggle(i - 1), add="+")
        toggle.bind("<Down>", lambda _e, i=index: self._focus_toggle(i + 1), add="+")
        toggle.bind("<space>", lambda _e, t=toggle: self._invoke(t), add="+")

    def _focus_toggle(self, index: int) -> str:
        if 0 <= index < len(self._toggles):
            self._toggles[index].focus_set()
        return "break"

    @staticmethod
    def _invoke(toggle: Checkbox) -> str:
        toggle.invoke()
        return "break"

    def _focus_first_toggle(self) -> None:
        if self._toggles and self._toggles[0].winfo_exists():
            self._toggles[0].focus_set()

    def _set_all(self, value: bool) -> None:
        for var in self._vars:
            var.set(value)
        self._update_accept_state()

    def _selected(self) -> list[str]:
        return [option.oberthema for option, var in zip(self._options.options, self._vars) if var.get()]

    def _update_accept_state(self) -> None:
        """Übernehmen ist nur mit mindestens einem gewählten Thema aktiv."""
        if self._accept_button is not None:
            self._accept_button.configure(state="normal" if self._selected() else "disabled")

    def _accept(self) -> None:
        selected = self._selected()
        if not selected:
            return
        self.result = selected
        self.destroy()


def ask_expected_horizon_topics(
    master, options: ExpectedHorizonTopicOptions, *, theme_key: str | None = None
) -> list[str] | None:
    """Öffnet den Themendialog modal.

    Returns:
        Die gewählten Themen in chronologischer Reihenfolge, oder ``None`` bei Abbruch.
    """
    dialog = ExpectedHorizonTopicDialog(master, options=options, theme_key=theme_key)
    dialog.wait_window()
    return dialog.result
