from __future__ import annotations

from typing import Protocol

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui


class SelectionLayer(Protocol):
    """Eine der fünf Auswahlebenen (COURSE/COLUMN/CELL/EDIT/SEARCH), aus Sicht von Enter/Escape."""

    def on_enter(self) -> str | None: ...
    def on_escape(self) -> str | None: ...
    def on_find_previous(self) -> str | None: ...


class _CourseLayer:
    """Kursauswahl (`is_detail_view == False`) -- wörtliche Verlagerung aus `intent_grid_enter`/`intent_escape`."""

    def __init__(self, controller):
        self._controller = controller

    def on_enter(self) -> str | None:
        return self._controller.intent_course_confirm_selection(None)

    def on_escape(self) -> str | None:
        app = self._controller.app
        if isinstance(app.focus_get(), ui.Text):
            app.grid_canvas.focus_set()
            return "break"
        return None

    def on_find_previous(self) -> str | None:
        return None


class _ColumnLayer:
    """`SELECTION_LEVEL_COLUMN` (auch Basisfall für den inkonsistenten Edge-Case COURSE+is_detail_view=True)."""

    def __init__(self, controller):
        self._controller = controller

    def on_enter(self) -> str | None:
        moved = self._controller.app.selection_controller.select_first_editable_in_selected_column()
        return "break" if moved else None

    def on_escape(self) -> str | None:
        self._controller.app.overview_controller.close_detail_view()
        return "break"

    def on_find_previous(self) -> str | None:
        return None


class _CellLayer:
    """`SELECTION_LEVEL_CELL`."""

    def __init__(self, controller):
        self._controller = controller

    def on_enter(self) -> str | None:
        app = self._controller.app
        selected_cell = app.ui_state.selected_cell
        if selected_cell is None:
            return None
        widget = app.cell_widgets.get((selected_cell.field_key, selected_cell.day_index))
        if widget is None:
            return None
        widget.focus_set()
        widget.mark_set("insert", "end-1c")
        widget.see("insert")
        return "break"

    def on_escape(self) -> str | None:
        app = self._controller.app
        app.selection_controller.clear_selected_cell()
        app.ui_state.set_selection_level(app.ui_state.SELECTION_LEVEL_COLUMN)
        app.grid_canvas.focus_set()
        return "break"

    def on_find_previous(self) -> str | None:
        return None


class _EditLayer:
    """`SELECTION_LEVEL_EDIT` (oder Fokus auf einem Zell-Text-Widget)."""

    def __init__(self, controller):
        self._controller = controller

    def on_enter(self) -> str | None:
        return None

    def on_escape(self) -> str | None:
        self._controller._leave_edit_mode_to_cell(set_grid_focus=True)
        return "break"

    def on_find_previous(self) -> str | None:
        return None


class _SearchLayer:
    """Strg+F-Einheitensuche aktiv (`app.search_state.is_active`) -- gewinnt gegenüber allen Basisebenen."""

    def __init__(self, controller):
        self._controller = controller

    def on_enter(self) -> str | None:
        self._controller.app.search_controller.find_next()
        return "break"

    def on_escape(self) -> str | None:
        self._controller.app.search_controller.close_search()
        return "break"

    def on_find_previous(self) -> str | None:
        self._controller.app.search_controller.find_previous()
        return "break"


class SelectionLayerStack:
    """Einzige Quelle der Wahrheit, welche Auswahlebene Enter/Escape/Umschalt+Enter aktuell erhält.

    Ersetzt die vorher verstreuten Prüfungen in `intent_grid_enter()`/
    `intent_escape()` (if/elif-Ketten auf `selection_level`, HSM-
    Prioritätsauflösung für Escape) durch eine einzige `top()`-Methode plus
    fünf dünne Layer-Adapter, die ausschließlich an bereits bestehende,
    unveränderte Mutator-/Controller-Funktionen delegieren -- siehe
    Implementierungsplan, Teil C. Enthält bewusst KEINE eigene
    Businesslogik, keine Spiegelung von `ui_state` (liest es nur), keine
    Suchalgorithmik (bleibt in `search_controller.py`).

    Kein echter Push/Pop-Stack für COURSE/COLUMN/CELL/EDIT: deren Tiefe wird
    weiterhin ausschließlich aus `ui_state.selection_level`/`is_detail_view`
    abgeleitet (unverändert die einzige Quelle für diese vier Ebenen, auch
    von Maus-/Ziffern-Navigation aktualisiert) -- nur SEARCH ist ein echtes
    An/Aus (`search_state.is_active`), das in `top()` immer zuerst gewinnt.
    """

    def __init__(self, controller):
        """Baut die fünf Layer-Adapter; `controller` ist der besitzende `MainWindowUiIntentController`."""
        self._controller = controller
        self._course = _CourseLayer(controller)
        self._column = _ColumnLayer(controller)
        self._cell = _CellLayer(controller)
        self._edit = _EditLayer(controller)
        self._search = _SearchLayer(controller)

    def top(self) -> SelectionLayer:
        """Liefert die aktuell aktive Auswahlebene -- die einzige Stelle, die das entscheidet."""
        app = self._controller.app
        search_state = getattr(app, "search_state", None)
        if search_state is not None and search_state.is_active:
            return self._search
        if not bool(getattr(app, "is_detail_view", False)):
            return self._course
        level = app.ui_state.selection_level
        if level == app.ui_state.SELECTION_LEVEL_EDIT or isinstance(app.focus_get(), ui.Text):
            return self._edit
        if level == app.ui_state.SELECTION_LEVEL_CELL:
            return self._cell
        return self._column

    def on_enter(self) -> str | None:
        return self.top().on_enter()

    def on_escape(self) -> str | None:
        return self.top().on_escape()

    def on_find_previous(self) -> str | None:
        return self.top().on_find_previous()
