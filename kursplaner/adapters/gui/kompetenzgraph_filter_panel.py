from __future__ import annotations

from collections.abc import Callable

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets
from bw_gui.widgets import Switch

from kursplaner.adapters.gui.help_catalog import KOMPETENZGRAPH_HELP
from kursplaner.adapters.gui.hover_tooltip import HoverTooltip
from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphFilter
from kursplaner.core.domain.kompetenzgraph_filter_options import BereichFilterOption, compute_filter_options
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot

_ALLE = "(alle)"
_KONTEXTTIEFE_MIN = 0
_KONTEXTTIEFE_MAX = 5


class KompetenzGraphFilterPanel:
    """Baut und verwaltet die Filter-Sidebar des Kompetenzgraph-Popups.

    Fach ist eine echte Mehrfachauswahl (Switch-Liste, analog dem
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

        self.frame = widgets.Frame(parent, padding=(10, 10))
        self._build(initial_filter)

    def _build(self, initial: KompetenzGraphFilter) -> None:
        widgets.Label(self.frame, text="Fach", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        initial_subjects = initial.subjects or frozenset()
        for subject in self._options.subjects:
            var = ui.BooleanVar(value=subject in initial_subjects)
            self._subject_vars[subject] = var
            # Switch: the graph re-filters immediately (effect via on_change, not a trace).
            Switch(self.frame, text=subject, variable=var, on_change=lambda _on: self._emit_change()).pack(anchor="w")
        if not self._options.subjects:
            widgets.Label(self.frame, text="(kein strukturiertes Fach gefunden)", foreground="gray").pack(anchor="w")

        self._jahrgang_var = self._build_combobox(
            "Jahrgang",
            [str(jahrgang) for jahrgang in self._options.jahrgaenge],
            str(initial.jahrgang) if initial.jahrgang is not None else None,
        )
        self._schulform_var = self._build_combobox("Schulform", list(self._options.schulformen), initial.schulform)
        self._bundesland_var = self._build_combobox("Bundesland", list(self._options.bundeslaender), initial.bundesland)
        self._niveau_var = self._build_combobox("Niveau", list(self._options.niveaus), initial.niveau)
        self._status_var = self._build_combobox("Status", list(self._options.status_werte), initial.status)
        self._anforderung_var = self._build_combobox(
            "Anforderung", list(self._options.anforderungen), initial.anforderung
        )
        self._inhaltsbereich_combo, self._inhaltsbereich_ids = self._build_bereich_combobox(
            "Inhaltsbereich", self._options.inhaltsbereiche, initial.inhaltsbereich_id
        )
        self._prozessbereich_combo, self._prozessbereich_ids = self._build_bereich_combobox(
            "Prozessbereich", self._options.prozessbereiche, initial.prozessbereich_id
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
        self._kontexttiefe_tooltips = [
            HoverTooltip(kontexttiefe_label, tooltip_text),
            HoverTooltip(spinbox, tooltip_text),
        ]

    def _build_combobox(self, label: str, options: list[str], initial_value: str | None) -> ui.StringVar:
        widgets.Label(self.frame, text=label).pack(anchor="w")
        var = ui.StringVar(value=initial_value if initial_value is not None else _ALLE)
        combo = widgets.Combobox(self.frame, textvariable=var, values=[_ALLE, *options], state="readonly")
        combo.pack(anchor="w", fill="x", pady=(0, 6))
        combo.bind("<<ComboboxSelected>>", lambda _event: self._emit_change())
        return var

    def _build_bereich_combobox(
        self, label: str, options: tuple[BereichFilterOption, ...], initial_value: str | None
    ) -> tuple[widgets.Combobox, list[str | None]]:
        """Baut eine Bereichs-Combobox, deren Auswahl über den Index (nicht den Anzeigetext) aufgelöst wird.

        Die parallele ID-Liste ist index-gleich zu den Combobox-Werten
        (Index 0 = "(alle)" → `None`). Dadurch bleibt die Zuordnung
        Anzeige → Bereichs-ID auch dann korrekt, wenn zwei Bereiche denselben
        Anzeigetext haben (Daten-Drift in den Bereichs-Dateien).

        Args:
            label: Überschrift über der Combobox.
            options: Sortierte Filteroptionen aus `compute_filter_options()`.
            initial_value: Vorauszuwählende Bereichs-ID. Existiert sie im
                Snapshot nicht (mehr), wird "(alle)" gewählt.

        Returns:
            `(combobox, ids)` -- `ids[combobox.current()]` ist die gewählte
            Bereichs-ID oder `None`.
        """
        ids: list[str | None] = [None, *(option.id for option in options)]
        display_values = [_ALLE, *(option.label for option in options)]

        widgets.Label(self.frame, text=label).pack(anchor="w")
        combo = widgets.Combobox(self.frame, values=display_values, state="readonly")
        combo.current(ids.index(initial_value) if initial_value in ids else 0)
        combo.pack(anchor="w", fill="x", pady=(0, 6))
        combo.bind("<<ComboboxSelected>>", lambda _event: self._emit_change())
        return combo, ids

    @staticmethod
    def _selected_bereich_id(combo: widgets.Combobox, ids: list[str | None]) -> str | None:
        """Löst die aktuelle Combobox-Auswahl über ihren Index auf die Bereichs-ID auf (`None` = alle)."""
        index = combo.current()
        return ids[index] if 0 <= index < len(ids) else None

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
            inhaltsbereich_id=self._selected_bereich_id(self._inhaltsbereich_combo, self._inhaltsbereich_ids),
            prozessbereich_id=self._selected_bereich_id(self._prozessbereich_combo, self._prozessbereich_ids),
            kontexttiefe=max(_KONTEXTTIEFE_MIN, min(_KONTEXTTIEFE_MAX, int(self._kontexttiefe_var.get() or 0))),
        )
