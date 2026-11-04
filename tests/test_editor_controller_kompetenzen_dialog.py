"""Kompetenz-Auswahldialog im Grid: mehrere gewählte Kompetenzen werden mehrere Listeneinträge.

Früher wurden sie mit ``" | "`` zu einem Text verbunden, den der Listenvertrag
(`list_cell_text.parse_list_cell`) nicht trennt – sie landeten als *ein* Eintrag
in der Einheit. Isoliert per `object.__new__()` wie `test_editor_controller_pending_text.py`.
"""

from __future__ import annotations

from types import SimpleNamespace

from kursplaner.adapters.gui import editor_controller as editor_module
from kursplaner.adapters.gui.editor_controller import MainWindowEditorController
from kursplaner.core.domain.list_cell_text import parse_list_cell
from tests.day_column_factory import make_day_column


def _controller(applied: list):
    controller = object.__new__(MainWindowEditorController)
    controller.app = SimpleNamespace(
        current_table=object(),
        day_columns=[make_day_column(row_index=0)],
        row_display_mode_usecase=SimpleNamespace(is_editable=lambda _fk, _day, _settings: True),
        row_filter_settings=SimpleNamespace(),
        lesson_conversion_controller=SimpleNamespace(resolve_kompetenz_options=lambda: ((), (), "")),
        _field_value=lambda _day, _field_key: "",
        theme_var=SimpleNamespace(get=lambda: "slate_indigo"),
        grid_canvas=SimpleNamespace(focus_set=lambda: None),
    )
    controller.apply_value = lambda field_key, day_index, value: applied.append((field_key, day_index, value))
    controller._refresh_after_cell_write = lambda _day_index: None
    return controller


def test_each_selected_competence_becomes_its_own_list_entry(monkeypatch):
    refs = ("P 1.1 zerlegen Problemstellungen", "[[Inf-SM-1|Zerlegen Problemstellungen]]")
    monkeypatch.setattr(
        editor_module, "ask_lesson_kompetenzen_selection", lambda **_kwargs: SimpleNamespace(kompetenzen_refs=refs)
    )
    applied: list = []

    assert _controller(applied).handle_editor_focus_in("Kompetenzen", 0) is True

    ((field_key, day_index, value),) = applied
    assert (field_key, day_index) == ("Kompetenzen", 0)
    assert parse_list_cell(value) == list(refs)


def test_entries_violating_the_list_contract_are_refused_not_merged(monkeypatch):
    monkeypatch.setattr(
        editor_module, "ask_lesson_kompetenzen_selection", lambda **_kwargs: SimpleNamespace(kompetenzen_refs=("a; b",))
    )
    errors: list = []
    monkeypatch.setattr(editor_module.messagebox, "showerror", lambda *args, **kwargs: errors.append(args))
    applied: list = []

    assert _controller(applied).handle_editor_focus_in("Kompetenzen", 0) is True
    assert applied == [] and len(errors) == 1
