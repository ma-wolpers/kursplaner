"""Auswahl-Listener von `MainWindowUiState` (SSOT-Haken für Auswahlwechsel).

Gemeldet wird genau bei echten Änderungen von markierten Spalten oder
markierter Zelle; gleiche Werte melden nichts. Ein Guardrail stellt sicher,
dass die Auswahl im Paket nur über die Setter geschrieben wird – sonst
verpassten Beobachter (Einheitsvorschau) still einen Wechsel.
"""

from __future__ import annotations

import re
from pathlib import Path

from kursplaner.adapters.gui.ui_state import MainWindowUiState

_PACKAGE = Path(__file__).resolve().parents[1] / "kursplaner"
# Erlaubt bleibt ``app.selected_day_indices = …`` (Property-Setter des Hauptfensters
# delegiert an `set_selected_day_indices`); verboten sind direkte Zustandsattribute.
_DIRECT_WRITE = re.compile(r"(ui_state\.selected_day_indices|\.selected_cell)\s*=(?!=)")
_ALLOWED = {"adapters/gui/ui_state.py"}


def _counting_state() -> tuple[MainWindowUiState, list[int]]:
    state = MainWindowUiState()
    calls: list[int] = []
    state.add_selection_listener(lambda: calls.append(1))
    return state, calls


def test_column_selection_change_notifies_once_and_same_value_not_again():
    state, calls = _counting_state()
    state.set_selected_day_indices({2})
    state.set_selected_day_indices([2])
    assert calls == [1]
    assert state.selected_day_indices == {2}


def test_cell_selection_change_and_clear_notify_only_on_change():
    state, calls = _counting_state()
    state.set_selected_cell("Inhalt", 1)
    state.set_selected_cell("Inhalt", 1)
    state.set_selected_cell("Inhalt", 2)
    state.clear_selected_cell()
    state.clear_selected_cell()
    assert len(calls) == 3


def test_removed_listener_is_not_called():
    state = MainWindowUiState()
    calls: list[int] = []
    remove = state.add_selection_listener(lambda: calls.append(1))
    remove()
    remove()
    state.set_selected_day_indices({0})
    assert calls == []


def test_selection_is_written_only_through_setters():
    offenders = []
    for path in _PACKAGE.rglob("*.py"):
        relative = path.relative_to(_PACKAGE).as_posix()
        if relative in _ALLOWED:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _DIRECT_WRITE.search(line):
                offenders.append(f"{relative}:{number}: {line.strip()}")
    assert offenders == []
