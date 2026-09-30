"""Modaler Dialog: Oberthemen für einen Kompetenzhorizont auswählen.

Zeigt die Kandidaten aus `ExpectedHorizonTopicQueryUseCase` (chronologisch,
mit Zeitraum und Stundenzahl) als Checkbox-Liste, vorbelegt mit der
gespeicherten bzw. naheliegenden Auswahl. Warnt vor gespeicherten, aber nicht
mehr verfügbaren Themen und vor Stunden mit ungültigem Oberthema. Entsteht ein
PDF, fragt der Dialog zusätzlich die Layout-Optionen ab (leere „Aufgaben“-Spalte,
Schriftgröße per Zahlbox). Enthält keine fachlichen Regeln — Kandidaten,
Reihenfolge und Vorbelegung kommen fertig aus dem Use Case.
"""

from __future__ import annotations

from dataclasses import dataclass

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets
from bw_gui.widgets import Checkbox

from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.core.domain.expected_horizon_pdf_layout import (
    DEFAULT_FONT_SIZE,
    FONT_SIZE_STEP,
    MAX_FONT_SIZE,
    MIN_FONT_SIZE,
    ExpectedHorizonPdfLayout,
)
from kursplaner.core.usecases.expected_horizon_topic_query_usecase import (
    ExpectedHorizonTopicOption,
    ExpectedHorizonTopicOptions,
)


@dataclass(frozen=True)
class ExpectedHorizonDialogResult:
    """Ergebnis des Dialogs: gewählte Themen und (nur bei PDF-Ausgabe) das PDF-Layout."""

    topics: list[str]
    pdf_layout: ExpectedHorizonPdfLayout | None = None


def _parse_font_size(text: str) -> float | None:
    """Liest die Zahlbox (Komma oder Punkt); ``None`` bei ungültiger/außerhalb liegender Eingabe."""
    try:
        value = float(str(text).strip().replace(",", "."))
    except ValueError:
        return None
    return value if MIN_FONT_SIZE <= value <= MAX_FONT_SIZE else None


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

    def __init__(
        self,
        master,
        *,
        options: ExpectedHorizonTopicOptions,
        theme_key: str | None = None,
        with_pdf_layout: bool = False,
    ) -> None:
        """Baut den Dialog auf.

        Args:
            master: Elternfenster.
            options: Ergebnis der Kandidatenabfrage (Optionen, Vorbelegung, Warnungen).
            theme_key: Optionaler Theme-Name; ``None`` übernimmt das Parent-Theme.
            with_pdf_layout: Zeigt die PDF-Optionen (Aufgaben-Spalte, Schriftgröße);
                nur sinnvoll, wenn der Export ein PDF erzeugt.
        """
        super().__init__(
            master,
            title="Kompetenzhorizont – Oberthemen",
            geometry="560x520" if with_pdf_layout else "560x420",
            minsize=(480, 320),
            theme_key=theme_key,
        )
        self.result: ExpectedHorizonDialogResult | None = None
        self._options = options
        self._with_pdf_layout = with_pdf_layout
        self._task_column_var = ui.BooleanVar(value=False)
        self._font_size_var = ui.StringVar(value=f"{DEFAULT_FONT_SIZE:g}")
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

        if self._with_pdf_layout:
            self._build_pdf_layout(frame)

        widgets.Separator(frame, orient="horizontal").pack(fill="x", pady=12)
        button_row = widgets.Frame(frame)
        button_row.pack(fill="x")
        self._accept_button = widgets.Button(button_row, text="Übernehmen", command=self._accept)
        self._accept_button.pack(side="right")
        widgets.Button(button_row, text="Abbrechen", command=self.destroy).pack(side="right", padx=(0, 8))

    def _build_pdf_layout(self, frame) -> None:
        """PDF-Optionen: Checkbox für die leere „Aufgaben“-Spalte und Zahlbox für die Schriftgröße."""
        widgets.Separator(frame, orient="horizontal").pack(fill="x", pady=(12, 8))
        widgets.Label(frame, text="PDF-Layout", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        Checkbox(
            frame,
            text="Leere Spalte „Aufgaben“ am rechten Rand (zum Eintragen)",
            variable=self._task_column_var,
        ).pack(anchor="w", pady=(4, 2))
        size_row = widgets.Frame(frame)
        size_row.pack(anchor="w", pady=(4, 0))
        widgets.Label(size_row, text="Schriftgröße (pt):").pack(side="left")
        widgets.Spinbox(
            size_row,
            from_=MIN_FONT_SIZE,
            to=MAX_FONT_SIZE,
            increment=FONT_SIZE_STEP,
            textvariable=self._font_size_var,
            width=5,
        ).pack(side="left", padx=(8, 0))
        self._font_size_var.trace_add("write", lambda *_args: self._update_accept_state())

    def _pdf_layout(self) -> ExpectedHorizonPdfLayout | None:
        """Aktuelles PDF-Layout; ``None`` ohne PDF-Optionen oder bei ungültiger Schriftgröße."""
        if not self._with_pdf_layout:
            return None
        font_size = _parse_font_size(self._font_size_var.get())
        if font_size is None:
            return None
        return ExpectedHorizonPdfLayout(with_task_column=bool(self._task_column_var.get()), font_size=font_size)

    def _is_valid(self) -> bool:
        """Mindestens ein Thema gewählt und (bei PDF) eine gültige Schriftgröße eingetragen."""
        return bool(self._selected()) and (not self._with_pdf_layout or self._pdf_layout() is not None)

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
        """Übernehmen ist nur mit gewähltem Thema und (bei PDF) gültiger Schriftgröße aktiv."""
        if self._accept_button is not None:
            self._accept_button.configure(state="normal" if self._is_valid() else "disabled")

    def _accept(self) -> None:
        """Übernimmt Themen und ggf. PDF-Layout als Ergebnis und schließt den Dialog."""
        if not self._is_valid():
            return
        self.result = ExpectedHorizonDialogResult(topics=self._selected(), pdf_layout=self._pdf_layout())
        self.destroy()


def ask_expected_horizon_topics(
    master,
    options: ExpectedHorizonTopicOptions,
    *,
    theme_key: str | None = None,
    with_pdf_layout: bool = False,
) -> ExpectedHorizonDialogResult | None:
    """Öffnet den Themendialog modal.

    Args:
        master: Elternfenster.
        options: Kandidaten, Vorbelegung und Warnungen.
        theme_key: Optionaler Theme-Name.
        with_pdf_layout: Zusätzlich die PDF-Optionen abfragen.

    Returns:
        Gewählte Themen (chronologisch) und ggf. PDF-Layout, oder ``None`` bei Abbruch.
    """
    dialog = ExpectedHorizonTopicDialog(master, options=options, theme_key=theme_key, with_pdf_layout=with_pdf_layout)
    dialog.wait_window()
    return dialog.result
