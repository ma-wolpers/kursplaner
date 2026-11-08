"""Oberfläche der Detailansicht (Grid oder Sequenzleiter) und das eine Intent-Tor der Leiter.

`MainWindowUiState.detail_surface` ist die einzige Quelle, welche Oberfläche ein geöffneter
Kurs zeigt (gemerkt über Kurswechsel und Neuladen, wie die Tisch-/Dokuansicht im
Kartograph); `is_detail_view` bleibt die Quelle für „Kurs offen“. Umgeschaltet wird nur in
`MainViewSwitcher`.

`LADDER_SURFACE_INTENTS` ist die einzige Liste der Intents, die in der Leiter-Ansicht
wirken; `MainWindowUiIntentController.handle_intent` weist alle anderen ab (Positivliste:
neue Grid-Aktionen sind in der Leiter damit automatisch wirkungslos).
"""

from __future__ import annotations

from enum import Enum

from kursplaner.adapters.gui.ui_intents import UiIntent


class DetailSurface(str, Enum):
    """Oberfläche eines geöffneten Kurses."""

    GRID = "grid"
    LADDER = "ladder"


LADDER_SURFACE_INTENTS: frozenset[str] = frozenset(
    {
        UiIntent.TOGGLE_SEQUENCE_LADDER_VIEW,
        UiIntent.SHORTCUT_ESCAPE,
        UiIntent.CLOSE_DETAIL_VIEW,
        UiIntent.TOOLBAR_UNDO,
        UiIntent.TOOLBAR_REDO,
        UiIntent.EDIT_UNDO_TO_RECENT_INDEX,
        UiIntent.TOOLBAR_REFRESH,
        UiIntent.TOOLBAR_NEW,
        UiIntent.OPEN_SETTINGS,
        UiIntent.REBUILD_LESSON_INDEX,
        UiIntent.SHOW_SHADOW_LESSONS,
        UiIntent.SHOW_KOMPETENZGRAPH,
        UiIntent.SHOW_SHORTCUT_OVERVIEW,
        UiIntent.SHOW_UB_ACHIEVEMENTS,
        UiIntent.OPEN_TIMETABLE_CHANGE,
    }
)
"""Intents, die in der Leiter-Ansicht wirken: kursweite Aktionen, Dialoge, Undo/Redo, Wechsel."""


def intent_allowed(surface: DetailSurface, intent: str) -> bool:
    """Wirkt *intent* auf der Oberfläche *surface*? (Grid: alle; Leiter: nur die Positivliste.)"""
    return surface is DetailSurface.GRID or intent in LADDER_SURFACE_INTENTS
