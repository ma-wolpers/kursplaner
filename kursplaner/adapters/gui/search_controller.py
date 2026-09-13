from __future__ import annotations

import re

from kursplaner.core.domain.day_column_search import day_column_matches_query


class MainWindowSearchController:
    """Kapselt die Strg+F-Einheitensuche im Hauptfenster-Grid.

    Ruft für den eigentlichen Sprung ausschließlich das bereits bestehende
    `MainWindowSelectionController.set_single_column_selection()` auf --
    keine neue Selektionslogik. `close_search()` rührt `ui_state`/die
    aktuelle Auswahl bewusst nicht an: "die aktuell markierte Einheit
    bleibt ausgewählt" ergibt sich dadurch von selbst, nicht durch
    zusätzlichen Code.
    """

    def __init__(self, app):
        """Speichert die App-Referenz; der eigentliche Zustand lebt in `app.search_state`."""
        self.app = app

    def open_search(self) -> None:
        """Blendet das Suchfeld ein und setzt die Suche auf einen leeren Anfangszustand."""
        state = self.app.search_state
        state.is_active = True
        state.query = ""
        state.pattern = None
        state.is_query_invalid = False
        state.matches = []
        state.current_match_index = None
        self.app.search_overlay_view.show()

    def close_search(self) -> None:
        """Blendet das Suchfeld aus, OHNE die aktuelle Grid-Auswahl zu verändern."""
        self.app.search_state.is_active = False
        self.app.search_overlay_view.hide()
        self.app.grid_canvas.focus_set()

    def update_query(self, text: str, pattern: re.Pattern[str] | None) -> None:
        """Übernimmt eine neue Sucheingabe -- ein ungültiges, nicht-leeres Regex lässt Treffer/Sprungziel unverändert.

        Dieselbe Grundsemantik wie die Kompetenznetz-Textsuche: kein Absturz, kein stiller
        Substring-Fallback, der zuletzt gültige Trefferzustand (`pattern`/`matches`) bleibt
        bestehen, bis ein neues gültiges Muster eingegeben wird. `query`/`is_query_invalid`
        werden dabei IMMER aktualisiert (unabhängig von Gültigkeit), damit die View den
        aktuellen Tippzustand ehrlich anzeigen kann, ohne den Trefferzustand zu verlieren.
        """
        state = self.app.search_state
        state.query = text
        state.is_query_invalid = pattern is None and bool(text)
        if state.is_query_invalid:
            return

        state.pattern = pattern
        state.current_match_index = None
        if pattern is None:
            state.matches = []
            return

        state.matches = [
            index for index, day in enumerate(self.app.day_columns) if day_column_matches_query(day, pattern)
        ]

    def _jump(self, *, step: int) -> None:
        state = self.app.search_state
        if not state.matches:
            return
        if state.current_match_index is None:
            next_index = 0 if step > 0 else len(state.matches) - 1
        else:
            next_index = (state.current_match_index + step) % len(state.matches)
        state.current_match_index = next_index
        day_index = state.matches[next_index]
        self.app.selection_controller.set_single_column_selection(day_index, ensure_visible=True)

    def find_next(self) -> None:
        """Springt zum nächsten Treffer, mit Wraparound zum Anfang."""
        self._jump(step=1)

    def find_previous(self) -> None:
        """Springt zum vorherigen Treffer, mit Wraparound zum Ende."""
        self._jump(step=-1)
