from __future__ import annotations

from datetime import date

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets  # noqa: E402

from kursplaner.core.config.settings import WEEKDAY_SHORT_OPTIONS  # noqa: E402
from kursplaner.core.domain.course_rhythm import WeekdayRhythm, current_segment  # noqa: E402


class WeekdayRhythmPicker:
    """Wochentags-Auswahl mit Startzeit- und Stundeneingabe je Tag (Mo–Fr).

    Gemeinsames Widget für den Kurs-Erstelldialog (`NewCourseWindow`) und den
    Stundenplanänderungs-Dialog (`TimetableChangeDialog`) — beide bauten zuvor
    dieselbe Checkbutton+Spinbox-Struktur unabhängig auf; die Erweiterung um
    eine Startzeit hätte diese Duplikation verdreifacht.

    Komponiert einen `widgets.Frame` statt ihn zu erben (wie `WrappedTextField`
    in bw-gui) und delegiert unbekannte Attribute (`pack`/`grid`/…) an den
    Container — vermeidet eine neue lokale UI-Basisklasse.
    """

    def __getattr__(self, name: str):
        """Delegiert unbekannte Widget-Attribute an den zusammengesetzten Container."""
        return getattr(self._container, name)

    def __init__(
        self,
        master,
        *,
        weekdays: list[tuple[str, int]] = WEEKDAY_SHORT_OPTIONS,
        default_hours: str = "2",
        default_start: str = "08:00",
    ):
        """Baut je aktivierbarem Wochentag Checkbutton, Startzeit-Entry und Stunden-Spinbox."""
        self._container = widgets.Frame(master)
        self._weekdays = weekdays
        self._default_hours = default_hours
        self._default_start = default_start
        self._enabled_vars: dict[int, ui.BooleanVar] = {}
        self._start_vars: dict[int, ui.StringVar] = {}
        self._hours_vars: dict[int, ui.StringVar] = {}
        self._start_widgets: dict[int, widgets.Entry] = {}
        self._hours_widgets: dict[int, widgets.Spinbox] = {}

        row = widgets.Frame(self._container)
        row.pack(fill="x", padx=6, pady=6)

        for short_label, weekday in weekdays:
            cell = widgets.Frame(row)
            cell.pack(side="left", padx=(0, 12))

            enabled_var = ui.BooleanVar(value=False)
            start_var = ui.StringVar(value=default_start)
            hours_var = ui.StringVar(value=default_hours)
            self._enabled_vars[weekday] = enabled_var
            self._start_vars[weekday] = start_var
            self._hours_vars[weekday] = hours_var

            widgets.Checkbutton(
                cell,
                text=short_label,
                variable=enabled_var,
                command=lambda w=weekday: self._toggle(w),
            ).pack(side="left")

            start_entry = widgets.Entry(cell, textvariable=start_var, width=6)
            start_entry.pack(side="left", padx=(4, 0))
            self._start_widgets[weekday] = start_entry

            hours_spin = widgets.Spinbox(cell, from_=1, to=4, textvariable=hours_var, width=3)
            hours_spin.pack(side="left", padx=(4, 0))
            self._hours_widgets[weekday] = hours_spin

            self._toggle(weekday)

    def _toggle(self, weekday: int) -> None:
        """Aktiviert/deaktiviert Startzeit- und Stunden-Eingabe für einen Wochentag."""
        enabled = self._enabled_vars[weekday].get()
        state = "normal" if enabled else "disabled"
        self._start_widgets[weekday].configure(state=state)
        self._hours_widgets[weekday].configure(state=state)
        if not enabled:
            return
        if not self._hours_vars[weekday].get().strip():
            self._hours_vars[weekday].set(self._default_hours)
        if not self._start_vars[weekday].get().strip():
            self._start_vars[weekday].set(self._default_start)

    def set_from_rhythm(self, entries: tuple[WeekdayRhythm, ...], on: date | None = None) -> None:
        """Befüllt die Auswahl aus bestehenden Rhythmus-Einträgen (z. B. beim Bearbeiten).

        Args:
            entries: Alle Rhythmus-Einträge eines Kurses (über alle Segmente).
            on: Referenzdatum für das wirksame Segment; ``None`` verwendet
                ``entries`` unverändert (z. B. ein bereits vorgefiltertes
                Einzelsegment).
        """
        active = current_segment(entries, on) if on is not None else entries
        by_weekday = {entry.weekday: entry for entry in active}
        for _, weekday in self._weekdays:
            entry = by_weekday.get(weekday)
            self._enabled_vars[weekday].set(entry is not None)
            self._start_vars[weekday].set(entry.start_time if entry is not None else self._default_start)
            self._hours_vars[weekday].set(str(entry.hours) if entry is not None else self._default_hours)
            self._toggle(weekday)

    def collect_raw(self) -> dict[int, tuple[str, str]]:
        """Liefert die aktivierten Wochentage als ``{weekday: (start_raw, hours_raw)}``."""
        return {
            weekday: (self._start_vars[weekday].get(), self._hours_vars[weekday].get())
            for weekday, enabled_var in self._enabled_vars.items()
            if enabled_var.get()
        }
