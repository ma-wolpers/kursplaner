"""Tests für den Spalten-Selektions-Fast-Path (Kursplaner Item 2, Perf-Fix 2026-08-29).

`toggle_column_selection()`/`set_single_column_selection()` riefen bisher
unbedingt `refresh_header_styles()` (alle Header) und `_refresh_grid_content()`
(kompletter Grid-Sweep) auf, obwohl eine Spaltenselektion nur das Header-
Styling der betroffenen Spalte(n) ändert — Zellstile hängen ausschließlich
von `ui_state.selected_cell`, nicht von `selected_day_indices` ab
(`_border_thickness()`/`_apply_cell_selection_style()` lesen `selected_day_indices`
nirgends). Diese Tests beweisen: nur die tatsächlich betroffenen Header
werden neu gestylt, `_refresh_grid_content()` wird nicht mehr aufgerufen,
solange das Grid bereits aufgebaut ist.

Nutzt dieselben Stub-Klassen wie `test_selection_controller.py` (importiert,
nicht dupliziert).
"""

from __future__ import annotations

from kursplaner.adapters.gui.selection_controller import MainWindowSelectionController
from tests.day_column_factory import make_day_column
from tests.test_selection_controller import _SelectionAppStub


class _HeaderLabelStub:
    def __init__(self) -> None:
        self.configure_calls: list[dict] = []

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(kwargs)


def _app_with_headers(num_columns: int) -> _SelectionAppStub:
    app = _SelectionAppStub(
        day_columns=[make_day_column(row_index=i, datum=f"2026-03-{27 + i:02d}") for i in range(num_columns)],
        row_defs=[("Stundenthema", "Thema")],
        editable_cells={("Stundenthema", i) for i in range(num_columns)},
    )
    app.header_labels = {i: _HeaderLabelStub() for i in range(num_columns)}
    # Fast Path in set_selected_cell()/clear_selected_cell() prueft cell_widgets
    # nicht-leer + kein laufender Rebuild -- fuer diese Tests soll das Grid als
    # "bereits aufgebaut" gelten.
    app.cell_widgets[("Stundenthema", 0)] = object()
    return app


def test_set_single_column_selection_only_restyles_the_newly_selected_header():
    app = _app_with_headers(3)
    controller = MainWindowSelectionController(app)

    controller.set_single_column_selection(1)

    assert app.header_labels[1].configure_calls  # neu selektiert -> gestylt
    assert not app.header_labels[0].configure_calls  # unberuehrt
    assert not app.header_labels[2].configure_calls  # unberuehrt
    assert app.refresh_calls == 0  # kein voller Grid-Sweep


def test_set_single_column_selection_restyles_both_old_and_new_header():
    app = _app_with_headers(3)
    controller = MainWindowSelectionController(app)
    controller.set_single_column_selection(0)
    for label in app.header_labels.values():
        label.configure_calls.clear()

    controller.set_single_column_selection(2)

    assert app.header_labels[0].configure_calls  # abgewaehlt -> muss zurueckgestylt werden
    assert app.header_labels[2].configure_calls  # neu ausgewaehlt
    assert not app.header_labels[1].configure_calls  # nie beteiligt
    assert app.refresh_calls == 0


def test_toggle_column_selection_only_restyles_the_toggled_header():
    app = _app_with_headers(2)
    controller = MainWindowSelectionController(app)

    controller.toggle_column_selection(0)  # an
    assert app.header_labels[0].configure_calls
    app.header_labels[0].configure_calls.clear()

    controller.toggle_column_selection(0)  # wieder aus

    assert app.header_labels[0].configure_calls
    assert not app.header_labels[1].configure_calls
    assert app.refresh_calls == 0


def test_clear_selected_cell_only_restyles_the_previously_selected_cell():
    app = _app_with_headers(1)
    controller = MainWindowSelectionController(app)
    controller.set_selected_cell("Stundenthema", 0)
    grid_renderer_stub = app.grid_renderer
    grid_renderer_stub.style_calls.clear()

    controller.clear_selected_cell()

    assert grid_renderer_stub.style_calls == [("Stundenthema", 0)]
    assert app.refresh_calls == 0
    assert app.ui_state.selected_cell is None


def test_clear_selected_cell_is_noop_when_nothing_was_selected():
    app = _app_with_headers(1)
    controller = MainWindowSelectionController(app)

    controller.clear_selected_cell()  # darf nicht abstuerzen, nichts zu tun

    assert app.refresh_calls == 0
    assert app.grid_renderer.style_calls == []


def test_column_selection_falls_back_to_full_refresh_when_grid_not_built():
    """Wenn `cell_widgets` leer ist (Grid noch nicht aufgebaut), muss der volle

    `refresh_header_styles()`-Sweep laufen statt des Fast Path -- erkennbar
    daran, dass ALLE Header (nicht nur die betroffene Spalte) gestylt werden.
    """
    app = _app_with_headers(2)
    app.cell_widgets = {}  # simuliert: Grid noch nicht aufgebaut
    controller = MainWindowSelectionController(app)

    controller.set_single_column_selection(0)

    assert app.header_labels[0].configure_calls  # betroffene Spalte
    assert app.header_labels[1].configure_calls  # UNBETROFFENE Spalte -- nur der volle Sweep stylt auch sie


def test_column_selection_falls_back_to_full_refresh_when_rebuilding():
    app = _app_with_headers(2)
    app._is_rebuilding_grid = True
    controller = MainWindowSelectionController(app)

    # Darf nicht abstuerzen, auch wenn cell_widgets nicht leer ist aber ein
    # Rebuild laeuft -- derselbe Guard wie beim bestehenden Zell-Fast-Path.
    controller.set_single_column_selection(1)

    assert app.selected_day_indices == {1}
