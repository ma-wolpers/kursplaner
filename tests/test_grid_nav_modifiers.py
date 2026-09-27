"""Regressionstest: Grid-Pfeilnavigation wertet Modifier über den bw-gui-Contract aus."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import bw_gui.contracts.key_modifiers as key_modifiers
from kursplaner.adapters.gui.screen_builder import ScreenBuilder

NUMLOCK, CONTROL = 0x0008, 0x0004


@pytest.fixture(autouse=True)
def _win32_backend(monkeypatch):
    """Live gemessene win32-Werte; Backend fixiert, damit der Test überall gleich prüft."""
    monkeypatch.setattr(key_modifiers.sys, "platform", "win32")


@pytest.mark.parametrize(
    ("state", "blocked"),
    [(0, False), (NUMLOCK, False), (CONTROL, True), (CONTROL | NUMLOCK, True), ("??", True)],
)
def test_ctrl_or_unknown_state_blocks_grid_navigation(state, blocked):
    assert ScreenBuilder._control_or_unknown_modifiers(SimpleNamespace(state=state)) is blocked
