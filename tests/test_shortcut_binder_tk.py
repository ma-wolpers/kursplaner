"""Echte Tastatur-Kette des Hauptfensters: ``ScreenBuilder._bind_shortcuts`` an einem echten Tk-Root.

Ohne App-Daten: Der Root (mit bw-gui-Router, ``create_root``) bekommt nur die Attribute,
die die Shortcut-Handler lesen; ``_handle_ui_intent`` zeichnet die Intents auf. Tasten
laufen über ``bw_gui.testing.keys.press_key`` (kein OS-Fokus). Abgesichert: Guide- und
Festkürzel hängen am ``ApplicationShortcutBinder`` (``all``-Router statt ``bind_all``),
exakte Modifier, ``Ctrl+Shift+E`` ohne Feststelltaste, Ziffernblock-Enter, Popup-Sperre
und der globale Klick-Beobachter (nie bei Texteingabe).
"""

from __future__ import annotations

import tkinter

import pytest

from bw_gui.runtime import create_root, ui
from bw_gui.runtime.key_router import router_for
from bw_gui.testing.keys import press_key

from kursplaner.adapters.gui.screen_builder import ScreenBuilder
from kursplaner.adapters.gui.ui_intents import UiIntent

SHIFT, CONTROL, ALT = 0x0001, 0x0004, 0x20000


@pytest.fixture(scope="module")
def root():
    """Eigener Root mit Router (der Session-Root aus conftest hat keinen)."""
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


@pytest.fixture(scope="module")
def wired(root):
    intents: list[str] = []

    def _record(intent, **_payload):
        intents.append(intent)
        return None

    root._handle_ui_intent = _record
    root.is_detail_view = True
    builder = ScreenBuilder(root)
    builder._bind_shortcuts()
    return builder, intents


@pytest.fixture
def intents(wired, monkeypatch):
    builder, recorded = wired
    recorded.clear()
    monkeypatch.setattr(builder, "_has_active_popup", lambda: False)
    monkeypatch.setattr(builder, "_shortcut_dialog_open", lambda: False)
    return recorded


def test_router_has_no_foreign_all_bindings(root, wired):
    assert router_for(root).verify() == []


def test_grid_navigation_is_exact(root, intents):
    press_key(root, "Up")
    press_key(root, "Up", state=SHIFT)
    press_key(root, "Up", state=CONTROL)  # Guide: Ctrl+Up = Zeile einklappen, nicht Navigation
    assert intents[:2] == [UiIntent.GRID_NAV_UP, UiIntent.GRID_NAV_UP]
    assert intents[2] == UiIntent.SHORTCUT_COLLAPSE_SELECTED_ROW


def test_keypad_enter_and_shift_enter(root, intents):
    press_key(root, "KP_Enter", char="\r")
    press_key(root, "Return", char="\r", state=SHIFT)
    assert intents == [UiIntent.GRID_ENTER, UiIntent.SHORTCUT_FIND_PREVIOUS]


def test_ctrl_shift_e_works_without_capslock_and_ctrl_alt_is_not_ctrl(root, intents):
    press_key(root, "E", state=CONTROL | SHIFT)
    press_key(root, "n", state=CONTROL | ALT)
    assert intents == [UiIntent.COURSE_TOGGLE_SHOW_FORMER]


def test_popup_blocks_guide_shortcuts(root, wired, intents, monkeypatch):
    builder, _recorded = wired
    monkeypatch.setattr(builder, "_has_active_popup", lambda: True)
    assert press_key(root, "n", state=CONTROL) is True  # verbraucht, kein Intent
    assert intents == []


def test_global_click_observer_skips_text_input(root, wired, intents, monkeypatch):
    builder, _recorded = wired
    clicks: list[object] = []
    monkeypatch.setattr(builder, "_on_global_click_commit_cell", lambda event: clicks.append(event.widget))
    top = ui.Toplevel(root)
    canvas, entry = ui.Canvas(top), ui.Entry(top)
    canvas.pack()
    entry.pack()
    top.update()
    try:
        canvas.event_generate("<ButtonPress-1>", x=2, y=2)
        entry.event_generate("<ButtonPress-1>", x=2, y=2)
        top.update()
        assert clicks == [canvas]
    finally:
        top.destroy()


def test_timetable_dialog_undo_is_local_and_gone_after_close(root, wired, tmp_path):
    """Bug 2: Strg+Z des Stundenplan-Dialogs hing per bind_all global und blieb nach dem Schliessen."""
    from types import SimpleNamespace

    from kursplaner.adapters.gui.timetable_change_dialog import TimetableChangeDialog
    from kursplaner.core.domain.plan_table import PlanTableData

    table = PlanTableData(
        markdown_path=tmp_path / "plan.md", headers=["Datum"], rows=[], start_line=0, end_line=0,
        source_lines=[], had_trailing_newline=True, metadata={},
    )
    dialog = TimetableChangeDialog(
        root,
        table=table,
        day_columns=[],
        calendar_dir=tmp_path,
        timetable_change_uc=SimpleNamespace(),
        on_accept=lambda *_a: None,
    )
    try:
        assert press_key(dialog, "z", state=CONTROL) is True  # Fenster-Binder des Dialogs
        assert str(root.tk.call("bind", "all", "<Control-Key-z>")) == ""
        assert router_for(root).verify() == []
    finally:
        dialog.destroy()
