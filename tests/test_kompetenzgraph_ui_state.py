"""Regression: das Kompetenznetz-Popup öffnet standardmäßig in der Ansicht "Fort-/Voraussetzung"."""

from kursplaner.adapters.gui.kompetenzgraph_ui_state import KompetenzGraphUiState
from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphFilter
from kursplaner.core.domain.kompetenzgraph_view_mode import MODE_ABHAENGIGKEITEN, MODE_FORT_VORAUS


def test_default_view_mode_is_fort_voraus():
    state = KompetenzGraphUiState(filter=KompetenzGraphFilter())

    assert state.view_mode == MODE_FORT_VORAUS


def test_explicit_view_mode_still_overrides_default():
    state = KompetenzGraphUiState(filter=KompetenzGraphFilter(), view_mode=MODE_ABHAENGIGKEITEN)

    assert state.view_mode == MODE_ABHAENGIGKEITEN
