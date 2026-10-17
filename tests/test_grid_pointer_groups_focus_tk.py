"""Fokus der Rasterzellen über die gemeinsame Fokus-Gruppe: erst Commit, dann Fokus verlassen (echtes Tk)."""

from __future__ import annotations

import tkinter

import pytest

from bw_gui.runtime import create_root, ui

from kursplaner.adapters.gui.grid_pointer_groups import GridPointerGroups
from kursplaner.adapters.gui.ui_intents import UiIntent


@pytest.fixture(scope="module")
def root():
    for attempt in range(3):
        try:
            instance = create_root()
            break
        except tkinter.TclError as exc:
            if not any(m in str(exc) for m in ("usable", "tcl_findLibrary", "init.tcl")) or attempt == 2:
                raise
    instance.withdraw()
    yield instance
    instance.destroy()


class _App:
    def __init__(self):
        self.intents: list[tuple[str, dict]] = []

    def _handle_ui_intent(self, intent, **payload):
        self.intents.append((intent, payload))


def test_cell_focus_order_and_payload(root):
    app = _App()
    groups = GridPointerGroups(app)
    top = ui.Toplevel(root)  # sichtbar: an ungemappte Fenster stellt Tk erzeugte Ereignisse nicht zu
    cell, seq = ui.Text(top, height=2), ui.Text(top, height=2)
    cell.pack()
    seq.pack()
    top.update()
    groups.focus_cell(cell, field_key="inhalt", day_index=3)
    groups.focus_sequence_cell(seq, field_key="Leitkompetenzen", row_index=1)
    cell.event_generate("<FocusIn>")
    cell.event_generate("<FocusOut>")
    seq.event_generate("<FocusOut>")
    assert app.intents == [
        (UiIntent.GRID_EDITOR_FOCUS_IN, {"field_key": "inhalt", "day_index": 3}),
        (UiIntent.GRID_COMMIT_CELL, {"field_key": "inhalt", "day_index": 3}),
        (UiIntent.GRID_EDITOR_FOCUS_OUT, {"field_key": "inhalt", "day_index": 3}),
        (UiIntent.GRID_COMMIT_SEQUENCE_FIELD, {"sequence_field_key": "Leitkompetenzen", "sequence_row_index": 1}),
        (UiIntent.GRID_SEQUENCE_FIELD_FOCUS_OUT, {"sequence_field_key": "Leitkompetenzen", "sequence_row_index": 1}),
    ]
    top.destroy()
