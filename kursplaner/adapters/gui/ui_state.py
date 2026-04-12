from __future__ import annotations

from dataclasses import dataclass, field


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
        self.selected_cell = SelectedCellState(field_key=field_key, day_index=day_index)
        self.selection_level = self.SELECTION_LEVEL_CELL

    def clear_selected_cell(self) -> None:
        self.selected_cell = None

    def set_selection_level(self, level: str) -> None:
        self.selection_level = str(level)
