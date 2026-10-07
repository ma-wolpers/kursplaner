from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets  # noqa: E402
from bw_gui.widgets import Checkbox  # noqa: E402

from kursplaner.core.config.settings import WEEKDAY_SHORT_OPTIONS  # noqa: E402
from kursplaner.core.domain.course_rhythm import WeekdayRhythm, current_segment  # noqa: E402

MODE_EVERY_WEEK = "jede Woche"
MODE_EVEN = "gKW"
MODE_ODD = "uKW"
MODE_AB = "gKW + uKW"
WEEK_MODES: tuple[str, ...] = (MODE_EVERY_WEEK, MODE_EVEN, MODE_ODD, MODE_AB)

# Je Modus die erzeugten Paritaeten, in Zeilenreihenfolge (Zeile 1, ggf. Zeile 2).
_MODE_PARITIES: dict[str, tuple[int | None, ...]] = {
    MODE_EVERY_WEEK: (None,),
    MODE_EVEN: (0,),
    MODE_ODD: (1,),
    MODE_AB: (0, 1),
}


def mode_for_parities(parities: set[int | None]) -> str:
    """Leitet den Wochenmodus eines Tages aus den Paritaeten seines Segments ab.

    Example::

        mode_for_parities({0, 1})
        # -> "gKW + uKW"
    """
    for mode, mode_parities in _MODE_PARITIES.items():
        if set(mode_parities) == parities:
            return mode
    raise ValueError(f"Keine Wochenauswahl fuer Paritaeten {parities!r}.")


@dataclass
class _LineInputs:
    """Startzeit-/Stunden-Eingabe einer Zeile (Zeile 1 = Normalfall/gKW, Zeile 2 = uKW bei A/B)."""

    frame: object
    label_var: ui.StringVar
    start_var: ui.StringVar
    hours_var: ui.StringVar
    start_widget: object
    hours_widget: object


@dataclass
class _DayInputs:
    """Alle Eingaben eines Wochentags."""

    enabled_var: ui.BooleanVar
    mode_var: ui.StringVar
    mode_widget: object
    lines: tuple[_LineInputs, _LineInputs]


class WeekdayRhythmPicker:
    """Wochentags-Auswahl mit Wochenmodus, Startzeit und Stunden je Tag (Mo–Fr).

    Gemeinsames Widget für den Kurs-Erstelldialog (`NewCourseWindow`) und den
    Stundenplanänderungs-Dialog (`TimetableChangeDialog`). Je Wochentag:
    Checkbox, Wochenmodus (`jede Woche | gKW | uKW | gKW + uKW`), Startzeit,
    Stunden; im Modus `gKW + uKW` erscheint eine zweite Zeile mit eigener
    Startzeit/Stundenzahl für die ungeraden Wochen (A/B-Tag).

    Quelle der Wahrheit:

    - Die **Checkbox** bestimmt, ob der Tag aktiv ist. Ist sie aus, sind alle
      Eingaben deaktiviert und `collect_raw` ignoriert den Tag vollständig;
      die Werte bleiben für ein späteres Wiedereinschalten stehen.
    - Der **Modus** bestimmt, welche `(weekday, parity)`-Schlüssel entstehen;
      die zweite Zeile wird nur im Modus `gKW + uKW` angezeigt und gelesen.

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
        """Baut je aktivierbarem Wochentag Checkbox, Wochenmodus und zwei Eingabezeilen."""
        self._container = widgets.Frame(master)
        self._weekdays = weekdays
        self._default_hours = default_hours
        self._default_start = default_start
        self._days: dict[int, _DayInputs] = {}

        row = widgets.Frame(self._container)
        row.pack(fill="x", padx=6, pady=6)
        for short_label, weekday in weekdays:
            self._days[weekday] = self._build_day(row, short_label, weekday)
            self._refresh(weekday)

    def _build_day(self, parent, short_label: str, weekday: int) -> _DayInputs:
        """Baut die Zelle eines Wochentags: Kopfzeile (Checkbox, Modus, Zeile 1) und Zeile 2."""
        cell = widgets.Frame(parent)
        cell.pack(side="left", anchor="n", padx=(0, 12))
        head = widgets.Frame(cell)
        head.pack(anchor="w")

        enabled_var = ui.BooleanVar(value=False)
        mode_var = ui.StringVar(value=MODE_EVERY_WEEK)
        Checkbox(
            head,
            text=short_label,
            variable=enabled_var,
            on_select=lambda _selected, w=weekday: self._refresh(w),
        ).pack(side="left")
        mode_widget = widgets.Combobox(head, textvariable=mode_var, values=list(WEEK_MODES), state="readonly", width=10)
        mode_widget.pack(side="left", padx=(4, 0))

        first = self._build_line(head)
        first.frame.pack(side="left")
        second = self._build_line(cell)
        day = _DayInputs(enabled_var=enabled_var, mode_var=mode_var, mode_widget=mode_widget, lines=(first, second))
        mode_var.trace_add("write", lambda *_args, w=weekday: self._refresh(w))
        return day

    def _build_line(self, parent) -> _LineInputs:
        """Baut eine Eingabezeile aus Kurzlabel (`g`/`u`), Startzeit-Entry und Stunden-Spinbox."""
        frame = widgets.Frame(parent)
        label_var = ui.StringVar(value="")
        start_var = ui.StringVar(value=self._default_start)
        hours_var = ui.StringVar(value=self._default_hours)
        widgets.Label(frame, textvariable=label_var, width=1).pack(side="left", padx=(4, 0))
        start_widget = widgets.Entry(frame, textvariable=start_var, width=6)
        start_widget.pack(side="left", padx=(2, 0))
        hours_widget = widgets.Spinbox(frame, from_=1, to=4, textvariable=hours_var, width=3)
        hours_widget.pack(side="left", padx=(4, 0))
        return _LineInputs(frame, label_var, start_var, hours_var, start_widget, hours_widget)

    def _refresh(self, weekday: int) -> None:
        """Gleicht Aktivierung, Beschriftung und Sichtbarkeit der Zeilen an Checkbox und Modus an."""
        day = self._days.get(weekday)
        if day is None:
            return
        enabled = day.enabled_var.get()
        is_ab = day.mode_var.get() == MODE_AB
        state = "normal" if enabled else "disabled"
        day.mode_widget.configure(state="readonly" if enabled else "disabled")
        for line in day.lines:
            line.start_widget.configure(state=state)
            line.hours_widget.configure(state=state)
            if enabled:
                if not line.hours_var.get().strip():
                    line.hours_var.set(self._default_hours)
                if not line.start_var.get().strip():
                    line.start_var.set(self._default_start)
        first, second = day.lines
        first.label_var.set("g" if is_ab else "")
        second.label_var.set("u" if is_ab else "")
        if is_ab:
            second.frame.pack(anchor="e", pady=(2, 0))
        else:
            second.frame.pack_forget()

    def set_from_rhythm(self, entries: tuple[WeekdayRhythm, ...], on: date | None = None) -> None:
        """Befüllt die Auswahl aus bestehenden Rhythmus-Einträgen (z. B. beim Bearbeiten).

        Der Wochenmodus je Tag folgt aus den Paritäten im Segment: kein
        Eintrag → Tag aus; ohne Kürzel → `jede Woche`; nur gKW/uKW →
        `gKW`/`uKW`; beide → `gKW + uKW` mit beiden Zeilen befüllt.

        Args:
            entries: Alle Rhythmus-Einträge eines Kurses (über alle Segmente).
            on: Referenzdatum für das wirksame Segment; ``None`` verwendet
                ``entries`` unverändert (z. B. ein bereits vorgefiltertes
                Einzelsegment).
        """
        active = current_segment(entries, on) if on is not None else entries
        for _, weekday in self._weekdays:
            day = self._days[weekday]
            day_entries = {entry.week_parity: entry for entry in active if entry.weekday == weekday}
            day.enabled_var.set(bool(day_entries))
            mode = mode_for_parities(set(day_entries)) if day_entries else MODE_EVERY_WEEK
            parities = _MODE_PARITIES[mode]
            for index, line in enumerate(day.lines):
                entry = day_entries.get(parities[index]) if index < len(parities) else None
                line.start_var.set(entry.start_time if entry is not None else self._default_start)
                line.hours_var.set(str(entry.hours) if entry is not None else self._default_hours)
            day.mode_var.set(mode)
            self._refresh(weekday)

    def collect_raw(self) -> dict[tuple[int, int | None], tuple[str, str]]:
        """Liefert die aktiven Eingaben als ``{(weekday, parity): (start_raw, hours_raw)}``.

        Deaktivierte Tage fehlen vollständig; die zweite Zeile wird nur im
        Modus `gKW + uKW` gelesen (siehe Klassen-Docstring).
        """
        raw: dict[tuple[int, int | None], tuple[str, str]] = {}
        for weekday, day in self._days.items():
            if not day.enabled_var.get():
                continue
            for line, parity in zip(day.lines, _MODE_PARITIES[day.mode_var.get()]):
                raw[(weekday, parity)] = (line.start_var.get(), line.hours_var.get())
        return raw
