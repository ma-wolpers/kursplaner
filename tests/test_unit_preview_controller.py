"""Einheitsvorschau: Event-Layout (rein) und `UnitPreviewController` (echtes Tk, synthetisch).

Controller: Strg+D-Umschalten reserviert/gibt die rechte Spalte frei, die
Vorschau folgt der Auswahl über den Auswahl-Listener (gleiche Datei → kein
erneutes Lesen), eine Plan-Neuberechnung liest neu, Platzhalter für „keine
Auswahl“/„nicht verknüpft“, ×-Knopf schließt, Breite/Zoom werden gemerkt.
Kein Zugriff auf echte Kurse oder die echte `ui_preferences.json`.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from bw_gui.runtime import ui
from bw_gui.widgets import ListItemEvent, ParagraphEvent, TextRun

import kursplaner.adapters.gui.unit_preview_controller as module
from kursplaner.adapters.gui.ui_state import MainWindowUiState
from kursplaner.adapters.gui.unit_preview_controller import PREVIEW_COLUMN, UnitPreviewController
from kursplaner.adapters.gui.unit_preview_events import (
    NO_UNIT_DOCUMENT,
    NO_UNIT_SELECTED,
    field_events,
    preview_events,
)
from kursplaner.core.config.ui_preferences_store import UnitPreviewSettings
from kursplaner.core.usecases.unit_preview_usecase import UnitPreview
from tests.day_column_factory import make_day_column


def test_field_events_are_compact_bold_key_lines_with_spacer():
    events = field_events((("Stundenthema", ("Brüche",)), ("Kompetenzen", ("A", "B"))))
    assert events[0] == ListItemEvent(runs=(TextRun("Stundenthema: ", bold=True), TextRun("Brüche")), ordered=False)
    assert events[1].runs[1] == TextRun("A · B")
    assert events[-1] == ParagraphEvent(runs=())


def test_preview_events_error_and_raw_text_fallback():
    assert preview_events(UnitPreview(title="x", error="kaputt"))[0].runs[0].text == "kaputt"
    raw = preview_events(UnitPreview(title="x", body_html=None, body_text="# Roh"))
    assert raw == [ParagraphEvent(runs=(TextRun("# Roh"),))]


class _FakeUseCase:
    def __init__(self) -> None:
        self.paths: list[Path] = []

    def execute(self, path: Path) -> UnitPreview:
        self.paths.append(path)
        return UnitPreview(
            title=path.stem, fields=(("Stundentyp", ("Unterricht",)),), body_html=f"<p>Inhalt {path.stem}</p>"
        )


@pytest.fixture
def setup(tk_root, monkeypatch):
    saved: list[UnitPreviewSettings] = []
    monkeypatch.setattr(module, "load_unit_preview_settings", lambda: UnitPreviewSettings(width=260, zoom=10))
    monkeypatch.setattr(module, "save_unit_preview_settings", saved.append)
    host = ui.Frame(tk_root, width=400, height=300)
    # place() verträgt sich mit den grid/pack-Kindern anderer Tests am geteilten Root.
    host.place(x=0, y=0, relwidth=1.0, relheight=1.0)
    host.lift()
    ui.Frame(host).grid(row=0, column=1, sticky="nsew")
    host.columnconfigure(1, weight=1)
    columns = [
        make_day_column(row_index=0, datum="10-11-26", link=Path("Einheiten/Brüche 1.md")),
        make_day_column(row_index=1, datum="12-11-26", link=None),
    ]
    usecase = _FakeUseCase()
    app = SimpleNamespace(
        ui_state=MainWindowUiState(),
        day_columns=columns,
        after_idle=tk_root.after_idle,
        gui_dependencies=SimpleNamespace(load_unit_preview_usecase=usecase),
    )
    app.selection_controller = SimpleNamespace(
        single_selected=lambda: (
            next(iter(app.ui_state.selected_day_indices), None) if len(app.ui_state.selected_day_indices) == 1 else None
        )
    )
    controller = UnitPreviewController(app, host)
    tk_root.update()
    yield SimpleNamespace(app=app, controller=controller, usecase=usecase, host=host, saved=saved, root=tk_root)
    host.destroy()


def _text(env) -> str:
    env.root.update()
    return env.controller._doc.text.get("1.0", "end").strip()


def test_toggle_opens_with_placeholder_and_reserves_column(setup):
    setup.controller.toggle()
    assert setup.controller.is_open
    assert _text(setup) == NO_UNIT_SELECTED
    assert int(setup.host.grid_columnconfigure(PREVIEW_COLUMN)["minsize"]) >= 240
    setup.controller.toggle()
    assert not setup.controller.is_open
    assert int(setup.host.grid_columnconfigure(PREVIEW_COLUMN)["minsize"]) == 0


def test_preview_follows_selection_and_skips_same_file(setup):
    setup.controller.open()
    setup.app.ui_state.set_selected_cell("Inhalt", 0)
    assert _text(setup).endswith("Inhalt Brüche 1") and "Stundentyp: Unterricht" in _text(setup)
    setup.app.ui_state.set_selected_cell("Stundenziel", 0)
    _text(setup)
    assert setup.usecase.paths == [Path("Einheiten/Brüche 1.md")]
    setup.app.ui_state.set_selected_cell("Inhalt", 1)
    assert _text(setup) == NO_UNIT_DOCUMENT


def test_column_selection_and_plan_change_reload(setup):
    setup.controller.open()
    setup.app.ui_state.set_selected_day_indices({0})
    _text(setup)
    setup.controller.on_plan_changed()
    _text(setup)
    assert len(setup.usecase.paths) == 2


def test_close_button_closes_and_selection_no_longer_loads(setup):
    setup.controller.open()
    setup.root.update()
    setup.controller._overlay.close_button.invoke()
    setup.app.ui_state.set_selected_cell("Inhalt", 0)
    setup.root.update()
    assert not setup.controller.is_open
    assert setup.usecase.paths == []


def test_zoom_and_width_are_remembered(setup):
    setup.controller.open()
    setup.controller._doc.set_base_size(13)
    setup.controller._remember_width(300)
    assert setup.saved[-1] == UnitPreviewSettings(width=300, zoom=13)
