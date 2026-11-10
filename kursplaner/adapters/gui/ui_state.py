"""Expliziter UI-Zustand des Hauptfensters (Auswahl, Editor, Oberfläche).

Die Grid-Auswahl (markierte Spalten, markierte Zelle) wird ausschließlich über
`set_selected_day_indices`, `set_selected_cell` und `clear_selected_cell`
geschrieben; nur diese drei melden eine echte Änderung an die
Auswahl-Listener (`add_selection_listener`). Damit sieht ein Beobachter (z. B.
die Einheitsvorschau) jeden Auswahlwechsel – auch die Wege, die am
`SelectionController` vorbeilaufen (Fokus, Rebuild, Spalten-Umordnung …).
`test_ui_state_selection_listeners.py` verbietet direkte Attribut-Zuweisungen.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from kursplaner.adapters.gui.detail_surface import DetailSurface


@dataclass(frozen=True)
class ActiveEditorState:
    """Beschreibt die aktuell aktive Grid-Textzelle."""

    field_key: str
    day_index: int


@dataclass(frozen=True)
class SelectedCellState:
    """Beschreibt die aktuell markierte Grid-Zelle im Navigationsmodus."""

    field_key: str
    day_index: int


@dataclass
class MainWindowUiState:
    """Expliziter UI-Zustand fuer MainWindow-Orchestrierung."""

    SELECTION_LEVEL_COURSE = "course"
    SELECTION_LEVEL_COLUMN = "column"
    SELECTION_LEVEL_CELL = "cell"
    SELECTION_LEVEL_EDIT = "edit"

    selected_day_indices: set[int] = field(default_factory=set)
    is_detail_view: bool = False
    active_editor: ActiveEditorState | None = None
    selected_cell: SelectedCellState | None = None
    selection_level: str = SELECTION_LEVEL_COURSE
    visible_toolbar_actions: set[str] = field(default_factory=set)
    detail_surface: DetailSurface = DetailSurface.GRID
    """Oberfläche eines geöffneten Kurses (Grid/Leiter); umgeschaltet nur in `MainViewSwitcher`."""
    _selection_listeners: list[Callable[[], object]] = field(default_factory=list, repr=False, compare=False)

    def add_selection_listener(self, listener: Callable[[], object]) -> Callable[[], None]:
        """Meldet ``listener()`` nach jeder echten Auswahländerung; liefert die Abmeldefunktion."""
        self._selection_listeners.append(listener)

        def _remove() -> None:
            if listener in self._selection_listeners:
                self._selection_listeners.remove(listener)

        return _remove

    def _notify_selection_changed(self) -> None:
        for listener in tuple(self._selection_listeners):
            listener()

    def set_selected_day_indices(self, indices: Iterable[int]) -> None:
        """Setzt die markierten Grid-Spalten (immer als eigene Kopie)."""
        new_indices = set(indices)
        changed = new_indices != self.selected_day_indices
        self.selected_day_indices = new_indices
        if changed:
            self._notify_selection_changed()

    def set_active_editor(self, field_key: str, day_index: int) -> None:
        self.active_editor = ActiveEditorState(field_key=field_key, day_index=day_index)
        self.selection_level = self.SELECTION_LEVEL_EDIT

    def clear_active_editor_if_matches(self, field_key: str, day_index: int) -> None:
        active = self.active_editor
        if active is None:
            return
        if active.field_key == field_key and active.day_index == day_index:
            self.active_editor = None

    def clear_active_editor(self) -> None:
        self.active_editor = None

    def set_selected_cell(self, field_key: str, day_index: int) -> None:
        """Markiert eine Grid-Zelle (Navigationsmodus) und meldet einen echten Wechsel."""
        new_cell = SelectedCellState(field_key=field_key, day_index=day_index)
        changed = new_cell != self.selected_cell
        self.selected_cell = new_cell
        self.selection_level = self.SELECTION_LEVEL_CELL
        if changed:
            self._notify_selection_changed()

    def clear_selected_cell(self) -> None:
        """Hebt die Zellmarkierung auf und meldet das, falls eine Zelle markiert war."""
        if self.selected_cell is None:
            return
        self.selected_cell = None
        self._notify_selection_changed()

    def set_selection_level(self, level: str) -> None:
        self.selection_level = str(level)
