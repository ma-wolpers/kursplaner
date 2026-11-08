"""Einziger Umschaltweg der Hauptansicht: Kursliste ↔ Detailansicht, Grid ↔ Sequenzleiter.

Vorbild ist die Tisch-/Dokuansicht des Kartographen: zwei unabhängige Zustände –
`is_detail_view` (Kursliste oder geöffneter Kurs) und `ui_state.detail_surface` (welche
Oberfläche der geöffnete Kurs zeigt, gemerkt über Kurswechsel und Neuladen) – und genau
eine Stelle, die Panes und Frames ein- und ausblendet und den Fokus vergibt.

Die Detailansicht hat zwei Plätze, die beide Oberflächen belegen: die Toolbar-Zeile über
der gemeinsamen Kopfzeile (Kursname, „Zur Kursliste“) und den Inhalt darunter. Die
Pack-Optionen je Platz stehen nur in `_SLOT_PACK`.
"""

from __future__ import annotations

from typing import Any

from kursplaner.adapters.gui.detail_surface import DetailSurface

_SLOT_PACK: dict[str, dict[str, Any]] = {
    "toolbar": {"fill": "x", "pady": (0, 2)},
    "body": {"fill": "both", "expand": True},
}
"""Pack-Optionen der beiden Plätze der Detailansicht (gleich für Grid und Leiter)."""


class MainViewSwitcher:
    """Schaltet Kursliste, Grid und Sequenzleiter um (eine Instanz am Hauptfenster)."""

    def __init__(self, app) -> None:
        """Bindet den Umschalter an das Hauptfenster (Frames kommen aus `ScreenBuilder`)."""
        self.app = app

    # -- Kursliste ↔ Detailansicht ---------------------------------------------------

    def show_overview(self) -> None:
        """Zeigt nur die Kursliste und blendet die Detailansicht aus."""
        pane = self.app.main_paned
        panes = {str(item) for item in pane.panes()}
        if str(self.app.detail_panel) in panes:
            pane.forget(self.app.detail_panel)
        if str(self.app.course_panel) not in {str(item) for item in pane.panes()}:
            pane.add(self.app.course_panel, weight=1)
        self.app.is_detail_view = False
        self.app.screen_builder.refresh_course_overview_toolbar()
        self.app.overview_controller.ensure_course_selected(prefer_first=True)
        self.app.after_idle(self.app.lesson_tree.focus_set)

    def show_detail(self) -> None:
        """Zeigt nur die Detailansicht – mit der zuletzt gewählten Oberfläche."""
        pane = self.app.main_paned
        if str(self.app.course_panel) in {str(item) for item in pane.panes()}:
            pane.forget(self.app.course_panel)
        if str(self.app.detail_panel) not in {str(item) for item in pane.panes()}:
            pane.add(self.app.detail_panel, weight=1)
        self.app.is_detail_view = True
        self._apply_surface()

    # -- Grid ↔ Sequenzleiter ----------------------------------------------------------

    def show_surface(self, surface: DetailSurface, *, sequence=None) -> None:
        """Wählt die Oberfläche des geöffneten Kurses (*sequence*: Leiter dieser Sequenzdatei)."""
        self.app.ui_state.detail_surface = surface
        if bool(getattr(self.app, "is_detail_view", False)):
            self._apply_surface(sequence=sequence)

    def toggle_ladder(self) -> None:
        """Strg+Shift+L / Menüschalter: Grid ↔ Sequenzleiter."""
        current = self.app.ui_state.detail_surface
        self.show_surface(DetailSurface.GRID if current is DetailSurface.LADDER else DetailSurface.LADDER)

    def _frames(self, surface: DetailSurface) -> dict[str, Any]:
        if surface is DetailSurface.LADDER:
            panel = self.app.sequence_ladder_panel
            return {"toolbar": panel.toolbar, "body": panel.body}
        return {"toolbar": self.app.toolbar_frame, "body": self.app.grid_body}

    def _apply_surface(self, *, sequence=None) -> None:
        surface = self.app.ui_state.detail_surface
        hidden = DetailSurface.GRID if surface is DetailSurface.LADDER else DetailSurface.LADDER
        for frame in self._frames(hidden).values():
            frame.pack_forget()
        for slot, frame in self._frames(surface).items():
            frame.pack(**_SLOT_PACK[slot])
        if surface is DetailSurface.LADDER:
            self.app.sequence_ladder_host.on_shown(sequence)
        else:
            self.app.after_idle(self.app.grid_canvas.focus_set)
