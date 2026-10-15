"""Regressionstest: Grid-Pfeilnavigation feuert nur ohne Strg (exakte Modifier im bw-gui-Contract).

Früher prüfte ``_control_or_unknown_modifiers`` im Handler, ob Strg gehalten wurde oder
der Zustand unbekannt war. Mit ``KeySpec``-Matching erreicht Strg+Pfeil bzw. ein
unbekannter Zustand die Definition gar nicht erst; NumLock spielt keine Rolle.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from bw_gui.contracts import TkBackend
from bw_gui.contracts.key_event import RawKey, classify_key
from bw_gui.contracts.key_spec import matches

from kursplaner.adapters.gui.screen_builder import ScreenBuilder

SHIFT, NUMLOCK, CONTROL = 0x0001, 0x0008, 0x0004


@pytest.mark.parametrize(
    ("state", "fires"),
    [(0, True), (NUMLOCK, True), (SHIFT, True), (CONTROL, False), (CONTROL | NUMLOCK, False), ("??", False)],
)
def test_grid_nav_up_matches_only_without_ctrl(state, fires):
    rows = {row.binding_id: row for row in ScreenBuilder(SimpleNamespace())._shortcut_rows()}
    identity = classify_key(RawKey("Up", "", state), TkBackend.WIN32)[1]
    assert matches(rows["grid.nav.up"].keys, identity) is fires
