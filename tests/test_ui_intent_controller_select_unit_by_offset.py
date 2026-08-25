"""Gating-Tests für `SHORTCUT_SELECT_UNIT_BY_OFFSET` (Zifferntasten 0-9).

Der Shortcut darf nur im Spaltenauswahl-Modus der Detailansicht wirken --
insbesondere NICHT während Zell-Textbearbeitung (`SELECTION_LEVEL_CELL`/
`SELECTION_LEVEL_EDIT`) und NICHT in der Kursübersicht.
"""

from __future__ import annotations

from types import SimpleNamespace

from kursplaner.adapters.gui.ui_intent_controller import MainWindowUiIntentController
from kursplaner.adapters.gui.ui_state import MainWindowUiState


def _make_controller(*, is_detail_view: bool, selection_level: str, selected_offset_result: bool = True):
    ui_state = MainWindowUiState()
    ui_state.selection_level = selection_level
    calls: list[int] = []
    selection_controller = SimpleNamespace(
        select_unit_at_offset_from_next=lambda offset: calls.append(offset) or selected_offset_result
    )
    app = SimpleNamespace(is_detail_view=is_detail_view, ui_state=ui_state, selection_controller=selection_controller)
    return MainWindowUiIntentController(app), calls


def test_select_unit_by_offset_fires_in_column_selection_mode():
    controller, calls = _make_controller(
        is_detail_view=True, selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN
    )

    result = controller.intent_select_unit_by_offset(2)

    assert result == "break"
    assert calls == [2]


def test_select_unit_by_offset_is_noop_during_cell_editing():
    controller, calls = _make_controller(is_detail_view=True, selection_level=MainWindowUiState.SELECTION_LEVEL_CELL)

    result = controller.intent_select_unit_by_offset(0)

    assert result is None
    assert calls == []


def test_select_unit_by_offset_is_noop_during_active_text_edit():
    controller, calls = _make_controller(is_detail_view=True, selection_level=MainWindowUiState.SELECTION_LEVEL_EDIT)

    result = controller.intent_select_unit_by_offset(0)

    assert result is None
    assert calls == []


def test_select_unit_by_offset_is_noop_outside_detail_view():
    controller, calls = _make_controller(
        is_detail_view=False, selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN
    )

    result = controller.intent_select_unit_by_offset(0)

    assert result is None
    assert calls == []


def test_select_unit_by_offset_returns_none_when_selection_controller_reports_noop():
    controller, calls = _make_controller(
        is_detail_view=True,
        selection_level=MainWindowUiState.SELECTION_LEVEL_COLUMN,
        selected_offset_result=False,
    )

    result = controller.intent_select_unit_by_offset(9)

    assert result is None
    assert calls == [9]
