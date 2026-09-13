from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import widgets

from kursplaner.adapters.gui.regex_entry_field import RegexEntryField
from kursplaner.adapters.gui.ui_intents import UiIntent


class SearchOverlayView:
    """Schwebendes Suchfeld der Strg+F-Einheitensuche -- reine View ohne eigene Entscheidungslogik.

    Zeigt Text an, verwaltet den Fokus, zeigt die Trefferzahl an und leitet
    Tastendrücke ausschließlich als Intents weiter. Ruft niemals eine
    Sprung- oder Selection-Mutator-Methode des Suchcontrollers direkt auf --
    ob Enter vorwärts oder Umschalt+Enter rückwärts bedeutet, entscheidet
    ausschließlich `SelectionLayerStack` (über `app._handle_ui_intent`),
    siehe Implementierungsplan, Teil C. Abgesichert durch
    `tests/test_search_architecture_guardrails.py`.
    """

    def __init__(self, app, parent):
        self.app = app
        self.frame = widgets.Frame(parent, padding=6, relief="raised", borderwidth=1)
        # `_status_label` muss VOR `RegexEntryField` existieren: dessen Konstruktor ruft
        # synchron `on_change` auf (Initial-Kompilierung fuer die Rahmenfarbe), was hier bis
        # zu `_refresh_status()` durchschlaegt. Nur das Erzeugen, nicht das Packen, muss vorher
        # passieren -- die sichtbare Reihenfolge (Feld links, Status rechts) bleibt ueber die
        # Pack-Reihenfolge unten erhalten.
        self._status_label = widgets.Label(self.frame, text="")
        self._field = RegexEntryField(self.frame, on_change=self._on_text_changed)
        self._field.pack(side="left", fill="x", expand=True)
        self._field.bind("<Return>", self._on_return)
        self._field.bind("<Shift-Return>", self._on_shift_return)
        self._status_label.pack(side="left", padx=(8, 0))

    def show(self) -> None:
        """Blendet das Suchfeld über der rechten oberen Ecke des Grids ein und fokussiert es."""
        self.frame.place(relx=1.0, rely=0.0, anchor="ne", x=-12, y=8)
        self._field.set_text("")
        self._status_label.configure(text="")
        self._field.focus_set()

    def hide(self) -> None:
        """Blendet das Suchfeld aus."""
        self.frame.place_forget()

    def _on_text_changed(self, text: str, pattern) -> None:
        self.app.search_controller.update_query(text, pattern)
        self._refresh_status()

    def _on_return(self, _event) -> str:
        self.app._handle_ui_intent(UiIntent.GRID_ENTER)
        self._refresh_status()
        return "break"

    def _on_shift_return(self, _event) -> str:
        self.app._handle_ui_intent(UiIntent.SHORTCUT_FIND_PREVIOUS)
        self._refresh_status()
        return "break"

    def _refresh_status(self) -> None:
        state = self.app.search_state
        if state.is_query_invalid:
            self._status_label.configure(text="Ungültiger Ausdruck")
        elif not state.query:
            self._status_label.configure(text="")
        elif not state.matches:
            self._status_label.configure(text="Kein Treffer")
        elif state.current_match_index is None:
            self._status_label.configure(text=f"{len(state.matches)} Treffer")
        else:
            self._status_label.configure(text=f"{state.current_match_index + 1}/{len(state.matches)} Treffer")
