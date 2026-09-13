from __future__ import annotations

import re
from collections.abc import Callable

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets

from kursplaner.adapters.gui.regex_entry_field import RegexEntryField
from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphFilter


class KompetenzGraphTextSearchPanel:
    """Baut das Textsuche-Feld (Regex + 4 Toggles + "Suchen"-Button) der Kompetenznetz-Sidebar.

    Aktualisiert bewusst NICHT live bei jedem Tastendruck -- `on_search`
    wird ausschließlich auf Klick des "Suchen"-Buttons oder Enter im
    Suchfeld aufgerufen, damit Beispiel-/Rest-des-Dokuments-Treffer (die
    einen Markdown-Body-Zugriff erfordern) nie pro Tastendruck neu gelesen
    werden -- siehe Implementierungsplan, Teil B. Entscheidet dabei
    ausschließlich über GUI-Zustand (Text, kompiliertes Pattern, Toggle-
    Zustände) und reicht das gebündelt weiter; die eigentliche
    Übernahme in den Filter bzw. Fehlerbehandlung bei ungültigem Regex
    liegt beim Aufrufer (`kompetenzgraph_dialog.py`).
    """

    def __init__(
        self,
        parent,
        *,
        initial_filter: KompetenzGraphFilter,
        on_search: Callable[[str, re.Pattern[str] | None, bool, bool, bool, bool], None],
    ):
        self._on_search = on_search

        self.frame = widgets.Frame(parent, padding=(10, 10))
        widgets.Label(self.frame, text="Textsuche", font=("Segoe UI", 9, "bold")).pack(anchor="w")

        self._field = RegexEntryField(self.frame, initial=initial_filter.text_query)
        self._field.pack(fill="x", pady=(0, 6))
        self._field.bind("<Return>", lambda _event: self._trigger_search())

        self._kc_var = ui.BooleanVar(value=initial_filter.text_search_kc_verweis)
        self._titel_var = ui.BooleanVar(value=initial_filter.text_search_titel)
        self._beispiel_var = ui.BooleanVar(value=initial_filter.text_search_beispiel)
        self._rest_var = ui.BooleanVar(value=initial_filter.text_search_rest)
        widgets.Checkbutton(self.frame, text="KC-Verweis", variable=self._kc_var).pack(anchor="w")
        widgets.Checkbutton(self.frame, text="Kompetenzname", variable=self._titel_var).pack(anchor="w")
        widgets.Checkbutton(self.frame, text="Beispiel", variable=self._beispiel_var).pack(anchor="w")
        widgets.Checkbutton(self.frame, text="Rest des Dokuments", variable=self._rest_var).pack(anchor="w")

        widgets.Button(self.frame, text="Suchen", command=self._trigger_search).pack(anchor="w", pady=(6, 0))

    def _trigger_search(self, *_args) -> None:
        self._on_search(
            self._field.get_text(),
            self._field.get_compiled_pattern(),
            self._kc_var.get(),
            self._titel_var.get(),
            self._beispiel_var.get(),
            self._rest_var.get(),
        )
