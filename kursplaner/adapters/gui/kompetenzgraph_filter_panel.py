from __future__ import annotations

from collections.abc import Callable

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets

from kursplaner.adapters.gui.help_catalog import KOMPETENZGRAPH_HELP
from kursplaner.adapters.gui.hover_tooltip import HoverTooltip
from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphFilter
from kursplaner.core.domain.kompetenzgraph_filter_options import compute_filter_options
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot

_ALLE = "(alle)"
_KONTEXTTIEFE_MIN = 0
_KONTEXTTIEFE_MAX = 5


class KompetenzGraphFilterPanel:
    """Baut und verwaltet die Filter-Sidebar des Kompetenzgraph-Popups.

    Fach ist eine echte Mehrfachauswahl (Checkbutton-Liste, analog dem
    Muster in `column_visibility_dialog.py`) -- alle übrigen Filter sind
    einfache Single-Select-Comboboxen. Alle Optionslisten werden dynamisch
    aus dem übergebenen Snapshot abgeleitet (`compute_filter_options()`),
    niemals hartkodiert. Jede Änderung ruft sofort `on_change` mit dem
    neu zusammengebauten `KompetenzGraphFilter` auf.
    """

    def __init__(
        self,
        parent,
        *,
        snapshot: KompetenzGraphSnapshot,
        initial_filter: KompetenzGraphFilter,
        on_change: Callable[[KompetenzGraphFilter], None],
    ):
        """Baut die Filter-Widgets auf und belegt sie mit `initial_filter`.

        Args:
            parent: Übergeordnetes Tk-Widget (Sidebar-Container).
            snapshot: Aktuelles Kompetenznetz-Snapshot (für Filter-Optionen
                und Bereichs-Titel).
            initial_filter: Vorbelegung (z. B. aus dem aktuellen Kurs
                abgeleitet, siehe `build_initial_kompetenz_graph_filter`).
            on_change: Wird bei jeder Nutzerinteraktion mit dem neuen
                Filterzustand aufgerufen.
        """
        self._snapshot = snapshot
        self._on_change = on_change
        self._options = compute_filter_options(snapshot)
        self._subject_vars: dict[str, ui.BooleanVar] = {}
        self._inhaltsbereich_label_to_id: dict[str, str] = {}
        self._prozessbereich_label_to_id: dict[str, str] = {}

        self.frame = widgets.Frame(parent, padding=(10, 10))
        self._build(initial_filter)

    def _bereich_title(self, bereich_id: str) -> str:
        bereich = self._snapshot.bereiche.get(bereich_id)
        return bereich.title if bereich is not None else bereich_id

    def _build(self, initial: KompetenzGraphFilter) -> None:
        widgets.Label(self.frame, text="Fach", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        initial_subjects = initial.subjects or frozenset()
        for subject in self._options.subjects:
            var = ui.BooleanVar(value=subject in initial_subjects)
            var.trace_add("write", lambda *_args: self._emit_change())
            self._subject_vars[subject] = var
            widgets.Checkbutton(self.frame, text=subject, variable=var).pack(anchor="w")
        if not self._options.subjects:
            widgets.Label(self.frame, text="(kein strukturiertes Fach gefunden)", foreground="gray").pack(anchor="w")

        self._jahrgang_var = self._build_combobox(
            "Jahrgang", [str(jahrgang) for jahrgang in self._options.jahrgaenge], str(initial.jahrgang) if initial.jahrgang is not None else None
        )
        self._schulform_var = self._build_combobox("Schulform", list(self._options.schulformen), initial.schulform)
        self._bundesland_var = self._build_combobox("Bundesland", list(self._options.bundeslaender), initial.bundesland)
        self._niveau_var = self._build_combobox("Niveau", list(self._options.niveaus), initial.niveau)
        self._status_var = self._build_combobox("Status", list(self._options.status_werte), initial.status)
        self._anforderung_var = self._build_combobox("Anforderung", list(self._options.anforderungen), initial.anforderung)
        self._inhaltsbereich_var = self._build_bereich_combobox(
            "Inhaltsbereich", self._options.inhaltsbereich_ids, initial.inhaltsbereich_id, self._inhaltsbereich_label_to_id
        )
        self._prozessbereich_var = self._build_bereich_combobox(
            "Prozessbereich", self._options.prozessbereich_ids, initial.prozessbereich_id, self._prozessbereich_label_to_id
        )

        kontexttiefe_label = widgets.Label(self.frame, text="Matchingtiefe", font=("Segoe UI", 9, "bold"))
        kontexttiefe_label.pack(anchor="w", pady=(8, 0))
        self._kontexttiefe_var = ui.IntVar(value=initial.kontexttiefe)
        spinbox = widgets.Spinbox(
            self.frame,
            from_=_KONTEXTTIEFE_MIN,
            to=_KONTEXTTIEFE_MAX,
            textvariable=self._kontexttiefe_var,
            width=4,
            state="readonly",
        )
        spinbox.pack(anchor="w", pady=(0, 8))
        self._kontexttiefe_var.trace_add("write", lambda *_args: self._emit_change())
        tooltip_text = KOMPETENZGRAPH_HELP.get("kontexttiefe", "")
        self._kontexttiefe_tooltips = [HoverTooltip(kontexttiefe_label, tooltip_text), HoverTooltip(spinbox, tooltip_text)]

    def _build_combobox(self, label: str, options: list[str], initial_value: str | None) -> ui.StringVar:
        widgets.Label(self.frame, text=label).pack(anchor="w")
        var = ui.StringVar(value=initial_value if initial_value is not None else _ALLE)
        combo = widgets.Combobox(self.frame, textvariable=var, values=[_ALLE, *options], state="readonly")
        combo.pack(anchor="w", fill="x", pady=(0, 6))
        combo.bind("<<ComboboxSelected>>", lambda _event: self._emit_change())
        return var

    def _build_bereich_combobox(
        self, label: str, bereich_ids: tuple[str, ...], initial_value: str | None, label_to_id: dict[str, str]
    ) -> ui.StringVar:
        display_values: list[str] = []
        for bereich_id in bereich_ids:
            title = self._bereich_title(bereich_id)
            label_to_id[title] = bereich_id
            display_values.append(title)
        initial_title = next((title for title, bid in label_to_id.items() if bid == initial_value), _ALLE)

        widgets.Label(self.frame, text=label).pack(anchor="w")
        var = ui.StringVar(value=initial_title)
        combo = widgets.Combobox(self.frame, textvariable=var, values=[_ALLE, *display_values], state="readonly")
        combo.pack(anchor="w", fill="x", pady=(0, 6))
        combo.bind("<<ComboboxSelected>>", lambda _event: self._emit_change())
        return var

    def _emit_change(self) -> None:
        self._on_change(self.current_filter())

    @staticmethod
    def _optional_str(var: ui.StringVar) -> str | None:
        value = var.get()
        return None if value == _ALLE else value

    @staticmethod
    def _optional_int(var: ui.StringVar) -> int | None:
        value = var.get()
        if value == _ALLE or not value.strip():
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def current_filter(self) -> KompetenzGraphFilter:
        """Baut den aktuellen `KompetenzGraphFilter` aus dem Zustand aller Widgets zusammen."""
        selected_subjects = frozenset(subject for subject, var in self._subject_vars.items() if var.get())
        return KompetenzGraphFilter(
            subjects=selected_subjects or None,
            jahrgang=self._optional_int(self._jahrgang_var),
            schulform=self._optional_str(self._schulform_var),
            bundesland=self._optional_str(self._bundesland_var),
            niveau=self._optional_str(self._niveau_var),
            status=self._optional_str(self._status_var),
            anforderung=self._optional_str(self._anforderung_var),
            inhaltsbereich_id=self._inhaltsbereich_label_to_id.get(self._inhaltsbereich_var.get()),
            prozessbereich_id=self._prozessbereich_label_to_id.get(self._prozessbereich_var.get()),
            kontexttiefe=max(_KONTEXTTIEFE_MIN, min(_KONTEXTTIEFE_MAX, int(self._kontexttiefe_var.get() or 0))),
        )
