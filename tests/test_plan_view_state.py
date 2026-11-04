"""Manuelles Neuladen: Der Nutzer bleibt im Plan, Auswahl und Scrollposition bleiben.

Früher führte jedes Neuladen zurück zur Kursübersicht. Gemerkt wird über die
Tabellenzeile, weil das Neuladen die gefilterte Spaltenliste neu aufbaut.
"""

from __future__ import annotations

from types import SimpleNamespace

from kursplaner.adapters.gui.action_controller import MainWindowActionController
from kursplaner.adapters.gui.overview_controller import MainWindowOverviewController
from kursplaner.adapters.gui.plan_view_state import PlanViewState, capture_plan_view, restore_plan_view
from kursplaner.adapters.gui.ui_intent_controller import MainWindowUiIntentController
from kursplaner.adapters.gui.ui_intents import UiIntent
from kursplaner.adapters.gui.ui_state import MainWindowUiState
from tests.day_column_factory import make_day_column


class _Selection:
    """Zeichnet Auswahlaufrufe auf; `editable` steuert, ob die Zelle gewählt werden kann."""

    def __init__(self, app, *, editable=True):
        self.app, self.editable = app, editable

    def set_single_column_selection(self, day_index):
        self.app.selected_day_indices = {day_index}

    def set_selected_cell(self, field_key, day_index):
        if self.editable:
            self.app.ui_state.set_selected_cell(field_key, day_index)
        return self.editable


def _app(rows=(5, 7, 9), *, detail=True, table=True, editable=True):
    moved = []
    idle = []
    app = SimpleNamespace(
        is_detail_view=detail,
        current_table=SimpleNamespace(markdown_path="C:/kurse/kurs.md") if table else None,
        ui_state=MainWindowUiState(),
        selected_day_indices=set(),
        day_columns=[make_day_column(row_index=row) for row in rows],
        viewport_sync_h=SimpleNamespace(xview_range=lambda: (0.25, 0.5), xview_moveto=lambda v: moved.append(("x", v))),
        viewport_sync=SimpleNamespace(yview_range=lambda: (0.75, 1.0), yview_moveto=lambda v: moved.append(("y", v))),
        action_controller=SimpleNamespace(update_action_controls=lambda: None),
        after_idle=idle.append,
        moved=moved,
        idle=idle,
    )
    app.selection_controller = _Selection(app, editable=editable)
    return app


class TestCapture:
    def test_no_open_plan_means_nothing_to_keep(self):
        assert capture_plan_view(_app(detail=False)) is None
        assert capture_plan_view(_app(table=False)) is None

    def test_column_is_remembered_by_table_row_not_position(self):
        app = _app()
        app.selected_day_indices = {1}
        assert capture_plan_view(app) == PlanViewState("C:/kurse/kurs.md", 7, None, 0.25, 0.75)

    def test_cell_is_remembered_with_its_field(self):
        app = _app()
        app.ui_state.set_selected_cell("Stundenthema", 2)
        state = capture_plan_view(app)
        assert (state.selected_row, state.selected_field) == (9, "Stundenthema")

    def test_stale_position_counts_as_no_selection(self):
        app = _app()
        app.ui_state.set_selected_cell("Stundenthema", 99)
        state = capture_plan_view(app)
        assert (state.selected_row, state.selected_field) == (None, None)


class TestRestore:
    def test_row_is_found_again_after_hidden_rows_changed(self):
        app = _app(rows=(7, 9))  # Zeile 5 ist jetzt ausgeblendet: Zeile 7 rückt auf Position 0
        restore_plan_view(app, PlanViewState("p", 7, None, 0.0, 0.0))
        assert app.selected_day_indices == {0}
        assert app.ui_state.selection_level == app.ui_state.SELECTION_LEVEL_COLUMN

    def test_cell_is_restored(self):
        app = _app()
        restore_plan_view(app, PlanViewState("p", 9, "Stundenthema", 0.0, 0.0))
        assert (app.ui_state.selected_cell.field_key, app.ui_state.selected_cell.day_index) == ("Stundenthema", 2)
        assert app.ui_state.selection_level == app.ui_state.SELECTION_LEVEL_CELL

    def test_cell_no_longer_editable_keeps_the_column(self):
        app = _app(editable=False)
        restore_plan_view(app, PlanViewState("p", 9, "Stundenthema", 0.0, 0.0))
        assert app.selected_day_indices == {2} and app.ui_state.selected_cell is None

    def test_vanished_column_leaves_no_selection(self):
        app = _app()
        restore_plan_view(app, PlanViewState("p", 42, "Stundenthema", 0.0, 0.0))
        assert app.selected_day_indices == set() and app.ui_state.selected_cell is None

    def test_scroll_waits_for_the_new_layout(self):
        app = _app()
        restore_plan_view(app, PlanViewState("p", None, None, 0.25, 0.75))
        assert app.moved == []
        app.idle[0]()
        assert app.moved == [("x", 0.25), ("y", 0.75)]


class _Tree:
    """Kursliste mit den Einträgen `items`; merkt sich den Fokus."""

    def __init__(self, items, focused=""):
        self.items, self.focused, self.focus_history = list(items), focused, []

    def focus(self, iid=None):
        if iid is None:
            return self.focused
        self.focused = iid
        self.focus_history.append(iid)

    def exists(self, iid):
        return iid in self.items

    def get_children(self):
        return list(self.items)

    def selection(self):
        return ()

    def selection_set(self, *_):
        pass

    def see(self, _iid):
        pass


class TestReloadKeepingView:
    def _controller(self, monkeypatch, *, items, focused="", detail=True):
        controller = object.__new__(MainWindowOverviewController)
        calls = []
        app = _app(detail=detail)
        app.selected_day_indices = {1}
        app.lesson_tree = _Tree(items, focused)

        def _show_overview():
            """Wie `show_course_overview`: Ohne fokussierten Kurs wird der erste gewählt."""
            calls.append("overview")
            controller.ensure_course_selected(prefer_first=True)

        app._show_course_overview = _show_overview
        controller.app = app
        monkeypatch.setattr(controller, "_reload_course_list", lambda: calls.append("list"))
        monkeypatch.setattr(
            controller,
            "load_selected_table",
            lambda _event=None, *, restore=None: calls.append(("load", app.lesson_tree.focused, restore.selected_row)),
        )
        monkeypatch.setattr(controller, "clear_plan_table", lambda _title: calls.append("clear"))
        monkeypatch.setattr(
            "kursplaner.adapters.gui.overview_controller.treeview_selection",
            SimpleNamespace(set=lambda _tree, _items: None),
        )
        return controller, calls

    def test_open_plan_stays_open_and_the_overview_never_shows(self, monkeypatch):
        controller, calls = self._controller(monkeypatch, items=["andere.md", "C:/kurse/kurs.md"])
        controller.reload_keeping_view()
        assert calls == ["list", ("load", "C:/kurse/kurs.md", 7)]
        assert controller.app.ui_state.selection_level == controller.app.ui_state.SELECTION_LEVEL_COURSE

    def test_course_gone_from_the_list_falls_back_to_the_overview(self, monkeypatch):
        controller, calls = self._controller(monkeypatch, items=["andere.md"])
        controller.reload_keeping_view()
        assert calls == ["list", "clear", "overview"]
        assert controller.app.lesson_tree.focused == "andere.md"

    def test_overview_keeps_the_selected_course(self, monkeypatch):
        controller, calls = self._controller(monkeypatch, items=["a.md", "b.md"], focused="b.md", detail=False)
        controller.reload_keeping_view()
        assert calls == ["list", "clear", "overview"]
        assert controller.app.lesson_tree.focused == "b.md"
        # Nie erst den ersten Kurs wählen und dann überschreiben.
        assert "a.md" not in controller.app.lesson_tree.focus_history

    def test_refresh_overview_still_shows_the_overview(self, monkeypatch):
        controller, calls = self._controller(monkeypatch, items=["a.md", "b.md"])
        controller.refresh_overview()
        assert calls == ["list", "clear", "overview"]


def test_undo_and_redo_keep_the_view():
    """Früher sprangen sie zur nächsten Einheit und verloren Auswahl und Scrollposition."""
    calls = []
    controller = object.__new__(MainWindowActionController)
    controller.app = SimpleNamespace(
        overview_controller=SimpleNamespace(reload_keeping_view=lambda: calls.append("reload"))
    )
    controller.update_action_controls = lambda: calls.append("controls")

    controller.refresh_after_file_write()

    assert calls == ["reload", "controls"]


class TestRefreshIntent:
    def _controller(self, *, save_ok):
        controller = object.__new__(MainWindowUiIntentController)
        reloaded = []
        controller.app = SimpleNamespace(
            ui_state=MainWindowUiState(),
            editor_controller=SimpleNamespace(save_cell=lambda _field, _day: save_ok),
            overview_controller=SimpleNamespace(reload_keeping_view=lambda: reloaded.append(True)),
            grid_canvas=SimpleNamespace(focus_set=lambda: None),
        )
        controller.app.ui_state.set_active_editor("Stundenthema", 0)
        return controller, reloaded

    def _refresh(self, controller):
        """Führt nur den Refresh-Zweig aus (die übrigen Prüfungen haben eigene Tests)."""
        controller._hsm_contract = SimpleNamespace(validate_intent=lambda _intent: (True, ""))
        controller._should_block_toolbar_shortcut = lambda _intent, _payload: False
        controller.handle_intent(UiIntent.TOOLBAR_REFRESH)

    def test_open_editor_is_saved_before_the_reload(self):
        controller, reloaded = self._controller(save_ok=True)
        self._refresh(controller)
        assert reloaded == [True] and controller.app.ui_state.active_editor is None

    def test_failed_save_keeps_the_text_and_skips_the_reload(self):
        controller, reloaded = self._controller(save_ok=False)
        self._refresh(controller)
        assert reloaded == [] and controller.app.ui_state.active_editor is not None
