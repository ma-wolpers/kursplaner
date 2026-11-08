"""Grid ↔ Sequenzleiter: ein Zustand, ein Tor, ein Umschaltweg (synthetisch, ohne Tk)."""

from __future__ import annotations

from types import SimpleNamespace

from kursplaner.adapters.gui.detail_surface import LADDER_SURFACE_INTENTS, DetailSurface, intent_allowed
from kursplaner.adapters.gui.main_view_switcher import MainViewSwitcher
from kursplaner.adapters.gui.selection_layer_stack import SelectionLayerStack
from kursplaner.adapters.gui.ui_intent_controller import MainWindowUiIntentController, _known_ui_intents
from kursplaner.adapters.gui.ui_intents import UiIntent
from kursplaner.adapters.gui.ui_state import MainWindowUiState


def test_every_grid_intent_is_inert_in_the_ladder():
    """Das Tor weist jeden nicht freigegebenen Intent ab, bevor er irgendetwas am Fenster anfasst."""
    state = MainWindowUiState(detail_surface=DetailSurface.LADDER)
    app = SimpleNamespace(is_detail_view=True, ui_state=state)  # jedes weitere Attribut fehlt absichtlich
    controller = MainWindowUiIntentController(app)
    blocked = [intent for intent in _known_ui_intents() if intent not in LADDER_SURFACE_INTENTS]
    assert UiIntent.TOOLBAR_AUSFALL in blocked and UiIntent.GRID_NAV_UP in blocked
    for intent in blocked:
        assert controller.handle_intent(intent) is None, intent


def test_grid_allows_everything_and_ladder_list_contains_the_way_back():
    assert intent_allowed(DetailSurface.GRID, UiIntent.TOOLBAR_AUSFALL)
    assert intent_allowed(DetailSurface.LADDER, UiIntent.TOGGLE_SEQUENCE_LADDER_VIEW)
    assert intent_allowed(DetailSurface.LADDER, UiIntent.SHORTCUT_ESCAPE)
    assert intent_allowed(DetailSurface.LADDER, UiIntent.TOOLBAR_UNDO)
    assert not intent_allowed(DetailSurface.LADDER, UiIntent.SHORTCUT_COPY)


def test_escape_in_the_ladder_returns_to_the_grid():
    shown = []
    app = SimpleNamespace(
        is_detail_view=True,
        ui_state=MainWindowUiState(detail_surface=DetailSurface.LADDER),
        main_view_switcher=SimpleNamespace(show_surface=shown.append),
    )
    stack = SelectionLayerStack(SimpleNamespace(app=app))
    stack.on_escape()
    assert shown == [DetailSurface.GRID]


class _Frame:
    def __init__(self, name, log):
        self.name, self.log = name, log

    def pack(self, **options):
        self.log.append(("pack", self.name, tuple(sorted(options))))

    def pack_forget(self):
        self.log.append(("forget", self.name))


def _switcher_app():
    log, shown = [], []
    app = SimpleNamespace(
        is_detail_view=True,
        ui_state=MainWindowUiState(),
        toolbar_frame=_Frame("grid-toolbar", log),
        grid_body=_Frame("grid-body", log),
        sequence_ladder_panel=SimpleNamespace(toolbar=_Frame("ladder-toolbar", log), body=_Frame("ladder-body", log)),
        sequence_ladder_host=SimpleNamespace(on_shown=shown.append),
        grid_canvas=SimpleNamespace(focus_set=lambda: None),
        after_idle=lambda callback: callback(),
    )
    return app, log, shown


def test_toggle_swaps_both_slots_and_hands_over_to_the_ladder():
    app, log, shown = _switcher_app()
    switcher = MainViewSwitcher(app)
    switcher.toggle_ladder()
    assert app.ui_state.detail_surface is DetailSurface.LADDER
    assert [entry[:2] for entry in log] == [
        ("forget", "grid-toolbar"),
        ("forget", "grid-body"),
        ("pack", "ladder-toolbar"),
        ("pack", "ladder-body"),
    ]
    assert shown == [None]
    log.clear()
    switcher.toggle_ladder()
    assert app.ui_state.detail_surface is DetailSurface.GRID
    assert [entry[:2] for entry in log][-2:] == [("pack", "grid-toolbar"), ("pack", "grid-body")]


def test_surface_is_remembered_while_the_course_list_is_shown():
    app, log, shown = _switcher_app()
    app.is_detail_view = False
    MainViewSwitcher(app).show_surface(DetailSurface.LADDER, sequence="a.md")
    assert app.ui_state.detail_surface is DetailSurface.LADDER and log == [] and shown == []
