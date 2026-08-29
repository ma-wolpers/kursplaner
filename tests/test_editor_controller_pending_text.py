"""Tests für `MainWindowEditorController.save_cell()`s neues `pending_cell_text`-
Clearing (Kursplaner Item 4, Stufe 4).

`pending_cell_text` wird ausschließlich bei einem erfolgreichen echten
Commit gelöscht -- nie durch Scrollen. Isoliert per `object.__new__()`, mit
`apply_value` direkt überschrieben (kein `gui_dependencies`-Stack nötig, da
nicht deren Persistenzlogik, sondern nur `save_cell()`s eigene
Dirty-Check-/Clearing-Logik getestet wird).
"""

from __future__ import annotations

from types import SimpleNamespace

from kursplaner.adapters.gui.editor_controller import MainWindowEditorController
from tests.day_column_factory import make_day_column


class _CellWidgetStub:
    def __init__(self, text: str):
        self._text = text

    def get(self, _start, _end):
        return self._text


def _controller(*, widget_text: str, domain_value: str, pending_cell_text: dict, apply_raises: bool = False):
    controller = object.__new__(MainWindowEditorController)
    day = make_day_column(row_index=0)
    controller.app = SimpleNamespace(
        _is_rebuilding_grid=False,
        current_table=object(),
        cell_widgets={("Stundenthema", 0): _CellWidgetStub(widget_text)},
        day_columns=[day],
        row_display_mode_usecase=SimpleNamespace(is_editable=lambda _fk, _day, _settings: True),
        row_filter_settings=SimpleNamespace(),
        _field_value=lambda _day, _field_key: domain_value,
        pending_cell_text=pending_cell_text,
        _collect_day_columns=lambda _changed: None,
        _update_grid_column=lambda _day_index: None,
        _update_selected_lesson_metrics=lambda: None,
        action_controller=SimpleNamespace(update_action_controls=lambda: None),
    )
    if apply_raises:
        def _raise(_field_key, _day_index, _value):
            raise RuntimeError("boom")

        controller.apply_value = _raise
    else:
        controller.apply_value = lambda _field_key, _day_index, _value: None
    return controller


def test_successful_commit_clears_pending_cell_text_entry():
    controller = _controller(
        widget_text="Neuer Wert",
        domain_value="Alter Wert",
        pending_cell_text={("Stundenthema", 0): "Neuer Wert"},
    )

    result = controller.save_cell("Stundenthema", 0)

    assert result is True
    assert ("Stundenthema", 0) not in controller.app.pending_cell_text


def test_noop_commit_when_widget_matches_domain_also_clears_stale_pending_entry():
    """Wert wurde auf den Domain-Wert zurückgeaendert (z.B. Edit rueckgaengig

    gemacht) -- save_cell() gibt fruehzeitig True zurueck, ein evtl. noch
    vorhandener veralteter pending_cell_text-Eintrag muss trotzdem verschwinden.
    """
    controller = _controller(
        widget_text="Gleicher Wert",
        domain_value="Gleicher Wert",
        pending_cell_text={("Stundenthema", 0): "Alter, veralteter Pending-Text"},
    )

    result = controller.save_cell("Stundenthema", 0)

    assert result is True
    assert ("Stundenthema", 0) not in controller.app.pending_cell_text


def test_failed_apply_value_leaves_pending_cell_text_untouched(monkeypatch):
    """Schlaegt der eigentliche Save fehl, bleibt ein pending_cell_text-Eintrag

    bestehen -- sonst waere der ungespeicherte Text nirgends mehr vermerkt.
    """
    from kursplaner.adapters.gui import editor_controller as editor_controller_module

    monkeypatch.setattr(editor_controller_module.messagebox, "showerror", lambda *a, **kw: None)

    controller = _controller(
        widget_text="Neuer Wert",
        domain_value="Alter Wert",
        pending_cell_text={("Stundenthema", 0): "Neuer Wert"},
        apply_raises=True,
    )

    result = controller.save_cell("Stundenthema", 0)

    assert result is False
    assert controller.app.pending_cell_text[("Stundenthema", 0)] == "Neuer Wert"


def test_commit_for_unrelated_cell_does_not_touch_other_pending_entries():
    controller = _controller(
        widget_text="Neuer Wert",
        domain_value="Alter Wert",
        pending_cell_text={("Oberthema", 5): "unabhaengiger Eintrag"},
    )

    controller.save_cell("Stundenthema", 0)

    assert controller.app.pending_cell_text == {("Oberthema", 5): "unabhaengiger Eintrag"}
