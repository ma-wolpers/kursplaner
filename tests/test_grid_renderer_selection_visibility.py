"""Tests für `GridRenderer._clear_selection_if_selected_cell_no_longer_visible()`
(Kursplaner Item 4 Vorarbeit -- Architektur-Smell-Audit, Fix 2026-08-29).

Ersetzt eine `(field_key, day_index) not in cell_widgets`-Prüfung durch eine
Domain-Sichtbarkeits-Prüfung (`_field_is_visible_for_day()`). Widget-Präsenz
ist heute (ohne Virtualisierung) zufällig äquivalent dazu, ist aber die
falsche Quelle der Wahrheit -- sobald `cell_widgets` durch Viewport-
Virtualisierung nur noch die sichtbaren Zellen enthält, würde die alte
Prüfung fälschlich auch eine weiterhin gültige, nur gerade nicht gemountete
Auswahl löschen.

Isoliert getestet nach demselben `object.__new__(GridRenderer)`-Muster wie
`test_grid_renderer_column_fast_path.py` -- kein echter Tk-Root nötig, da nur
diese eine Methode geprüft wird.
"""

from __future__ import annotations

from types import SimpleNamespace

from kursplaner.adapters.gui.grid_renderer import GridRenderer
from kursplaner.adapters.gui.ui_state import MainWindowUiState
from tests.day_column_factory import make_day_column


def _renderer_with_selection(
    *, selected_field_key: str, selected_day_index: int, field_is_visible: bool, day_count: int = 1
) -> GridRenderer:
    renderer = object.__new__(GridRenderer)
    ui_state = MainWindowUiState()
    ui_state.set_selected_cell(selected_field_key, selected_day_index)
    renderer.app = SimpleNamespace(
        ui_state=ui_state,
        day_columns=[make_day_column(row_index=i) for i in range(day_count)],
        row_display_mode_usecase=SimpleNamespace(
            is_linked_day=lambda _day: True,
            field_is_relevant_for_day=lambda _field_key, _day, _settings: field_is_visible,
        ),
        row_filter_settings=SimpleNamespace(),
    )
    return renderer


def test_keeps_selection_when_field_still_visible_for_day():
    renderer = _renderer_with_selection(
        selected_field_key="Stundenthema", selected_day_index=0, field_is_visible=True
    )

    renderer._clear_selection_if_selected_cell_no_longer_visible()

    assert renderer.app.ui_state.selected_cell is not None
    assert renderer.app.ui_state.selection_level == MainWindowUiState.SELECTION_LEVEL_CELL


def test_clears_selection_and_downgrades_level_when_field_no_longer_visible():
    renderer = _renderer_with_selection(
        selected_field_key="Kompetenzen", selected_day_index=0, field_is_visible=False
    )

    renderer._clear_selection_if_selected_cell_no_longer_visible()

    assert renderer.app.ui_state.selected_cell is None
    assert renderer.app.ui_state.selection_level == MainWindowUiState.SELECTION_LEVEL_COLUMN


def test_clears_selection_when_day_index_out_of_range_after_rebuild():
    """z.B. nach dem Entfernen der letzten Tage einer Sequenz -- die
    ausgewaehlte Spalte existiert nach dem Rebuild schlicht nicht mehr."""
    renderer = _renderer_with_selection(
        selected_field_key="Stundenthema", selected_day_index=5, field_is_visible=True, day_count=1
    )

    renderer._clear_selection_if_selected_cell_no_longer_visible()

    assert renderer.app.ui_state.selected_cell is None


def test_leaves_column_level_selection_untouched_when_field_no_longer_visible():
    """Der Level-Downgrade greift nur, wenn tatsaechlich SELECTION_LEVEL_CELL
    aktiv war -- set_selected_cell() setzt das immer, dieser Test belegt
    explizit, dass eine bereits vorhandene Spaltenauswahl (Level COLUMN)
    nicht faelschlich auf COLUMN "downgegradet" wird, obwohl sie es schon ist."""
    renderer = _renderer_with_selection(
        selected_field_key="Kompetenzen", selected_day_index=0, field_is_visible=False
    )
    renderer.app.ui_state.set_selection_level(MainWindowUiState.SELECTION_LEVEL_COLUMN)

    renderer._clear_selection_if_selected_cell_no_longer_visible()

    assert renderer.app.ui_state.selected_cell is None
    assert renderer.app.ui_state.selection_level == MainWindowUiState.SELECTION_LEVEL_COLUMN


def test_noop_when_nothing_selected():
    renderer = object.__new__(GridRenderer)
    ui_state = MainWindowUiState()
    renderer.app = SimpleNamespace(ui_state=ui_state, day_columns=[])

    renderer._clear_selection_if_selected_cell_no_longer_visible()  # kein Zugriff auf day_columns/row_display_mode_usecase noetig

    assert renderer.app.ui_state.selected_cell is None
