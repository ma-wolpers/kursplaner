import re
from types import SimpleNamespace

from kursplaner.adapters.gui.search_controller import MainWindowSearchController
from kursplaner.adapters.gui.search_state import SearchOverlayState
from tests.day_column_factory import make_day_column


class _SelectionControllerSpy:
    def __init__(self):
        self.calls: list[tuple[int, bool]] = []

    def set_single_column_selection(self, day_index: int, *, ensure_visible: bool = False):
        self.calls.append((day_index, ensure_visible))


class _OverlayViewSpy:
    def __init__(self):
        self.show_calls = 0
        self.hide_calls = 0

    def show(self):
        self.show_calls += 1

    def hide(self):
        self.hide_calls += 1


class _GridCanvasSpy:
    def __init__(self):
        self.focus_set_calls = 0

    def focus_set(self):
        self.focus_set_calls += 1


def _make_app(day_columns=None):
    app = SimpleNamespace(
        search_state=SearchOverlayState(),
        day_columns=day_columns if day_columns is not None else [],
        selection_controller=_SelectionControllerSpy(),
        search_overlay_view=_OverlayViewSpy(),
        grid_canvas=_GridCanvasSpy(),
    )
    app.search_controller = MainWindowSearchController(app)
    return app


def test_open_search_resets_state_and_shows_overlay():
    app = _make_app()
    app.search_controller.update_query("alt", re.compile("alt"))

    app.search_controller.open_search()

    assert app.search_state.is_active is True
    assert app.search_state.query == ""
    assert app.search_state.pattern is None
    assert app.search_state.matches == []
    assert app.search_overlay_view.show_calls == 1


def test_close_search_hides_overlay_without_touching_matches():
    app = _make_app(day_columns=[make_day_column(inhalt="Vektoren")])
    app.search_controller.update_query("Vektor", re.compile("Vektor"))

    app.search_controller.close_search()

    assert app.search_state.is_active is False
    assert app.search_state.matches == [0]  # unveraendert
    assert app.search_overlay_view.hide_calls == 1
    assert app.grid_canvas.focus_set_calls == 1


def test_update_query_computes_matches_against_day_columns():
    app = _make_app(
        day_columns=[
            make_day_column(inhalt="Vektoren"),
            make_day_column(inhalt="Stochastik"),
            make_day_column(inhalt="Vektorfeld"),
        ]
    )

    app.search_controller.update_query("Vektor", re.compile("Vektor"))

    assert app.search_state.matches == [0, 2]
    assert app.search_state.is_query_invalid is False


def test_update_query_with_invalid_regex_preserves_previous_matches_and_marks_invalid():
    """Kernregression: ein ungueltiges Regex darf weder abstuerzen noch die zuletzt
    gueltigen Treffer verwerfen -- markiert aber explizit `is_query_invalid`, damit die
    View das ehrlich anzeigen kann (siehe search_overlay_view.py::_refresh_status)."""
    app = _make_app(day_columns=[make_day_column(inhalt="Vektoren")])
    app.search_controller.update_query("Vektor", re.compile("Vektor"))

    app.search_controller.update_query("Vektor[", None)

    assert app.search_state.query == "Vektor["
    assert app.search_state.is_query_invalid is True
    assert app.search_state.pattern is not None  # altes gueltiges Pattern bleibt stehen
    assert app.search_state.matches == [0]  # unveraendert


def test_update_query_with_empty_text_clears_matches_and_is_not_invalid():
    app = _make_app(day_columns=[make_day_column(inhalt="Vektoren")])
    app.search_controller.update_query("Vektor", re.compile("Vektor"))

    app.search_controller.update_query("", None)

    assert app.search_state.matches == []
    assert app.search_state.is_query_invalid is False


def test_find_next_wraps_around_to_first_match():
    app = _make_app(
        day_columns=[make_day_column(inhalt="Vektoren"), make_day_column(inhalt="Vektorfeld")]
    )
    app.search_controller.update_query("Vektor", re.compile("Vektor"))

    app.search_controller.find_next()
    app.search_controller.find_next()
    app.search_controller.find_next()

    assert app.selection_controller.calls == [(0, True), (1, True), (0, True)]


def test_find_previous_wraps_around_to_last_match():
    app = _make_app(
        day_columns=[make_day_column(inhalt="Vektoren"), make_day_column(inhalt="Vektorfeld")]
    )
    app.search_controller.update_query("Vektor", re.compile("Vektor"))

    app.search_controller.find_previous()

    assert app.selection_controller.calls == [(1, True)]


def test_find_next_is_noop_without_matches():
    app = _make_app()

    app.search_controller.find_next()

    assert app.selection_controller.calls == []
