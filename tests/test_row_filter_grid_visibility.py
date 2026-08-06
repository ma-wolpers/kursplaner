from pathlib import Path
from types import SimpleNamespace

from kursplaner.adapters.gui.grid_renderer import GridRenderer
from kursplaner.core.usecases.row_display_mode_usecase import RowDisplayModeUseCase, RowFilterSettings


def _make_app(hidden_fields: frozenset[str] = frozenset()) -> SimpleNamespace:
    return SimpleNamespace(
        row_filter_settings=RowFilterSettings(hidden_fields=hidden_fields),
        row_display_mode_usecase=RowDisplayModeUseCase(),
    )


def _linked_day(tmp_path) -> dict[str, object]:
    link = tmp_path / "abc123.md"
    link.write_text("---\nStundentyp: Unterricht\nDauer: 2\nStundenthema: Thema\n---\n", encoding="utf-8")
    return {"link": link, "is_cancel": False, "is_hospitation": False, "is_lzk": False}


def _unlinked_day() -> dict[str, object]:
    return {"link": None}


def _unlinked_ausfall_day() -> dict[str, object]:
    return {"link": None, "is_cancel": True}


def test_unlinked_day_only_shows_inhalt_stunden_and_oberthema():
    app = _make_app()
    renderer = GridRenderer(app)
    day = _unlinked_day()

    assert renderer._field_is_visible_for_day("inhalt", day) is True
    assert renderer._field_is_visible_for_day("stunden", day) is True
    assert renderer._field_is_visible_for_day("Oberthema", day) is True
    assert renderer._field_is_visible_for_day("Stundenthema", day) is False


def test_unlinked_day_respects_row_filter(tmp_path):
    app = _make_app(hidden_fields=frozenset({"inhalt"}))
    renderer = GridRenderer(app)
    day = _unlinked_day()

    assert renderer._field_is_visible_for_day("inhalt", day) is False


def test_hidden_field_invisible_on_linked_day(tmp_path):
    app = _make_app(hidden_fields=frozenset({"Oberthema"}))
    renderer = GridRenderer(app)
    day = _linked_day(tmp_path)

    assert renderer._field_is_visible_for_day("Oberthema", day) is False


def test_visible_field_matching_mode_is_shown(tmp_path):
    app = _make_app()
    renderer = GridRenderer(app)
    day = _linked_day(tmp_path)

    assert renderer._field_is_visible_for_day("Stundenthema", day) is True


def test_field_not_in_mode_is_hidden_regardless_of_filter(tmp_path):
    app = _make_app()
    renderer = GridRenderer(app)
    day = _linked_day(tmp_path)

    assert renderer._field_is_visible_for_day("Vertretungsmaterial", day) is False


def test_filter_hides_field_even_when_mode_would_show_it(tmp_path):
    app = _make_app(hidden_fields=frozenset({"Stundenthema"}))
    renderer = GridRenderer(app)
    day = _linked_day(tmp_path)

    assert renderer._field_is_visible_for_day("Stundenthema", day) is False


def test_filter_does_not_hide_other_fields(tmp_path):
    app = _make_app(hidden_fields=frozenset({"Oberthema"}))
    renderer = GridRenderer(app)
    day = _linked_day(tmp_path)

    assert renderer._field_is_visible_for_day("Stundenthema", day) is True


def test_oberthema_is_editable_on_unlinked_unterricht_day():
    use_case = RowDisplayModeUseCase()
    day = _unlinked_day()

    assert use_case.is_editable("Oberthema", day) is True


def test_oberthema_is_not_editable_on_unlinked_ausfall_day():
    use_case = RowDisplayModeUseCase()
    day = _unlinked_ausfall_day()

    assert use_case.is_editable("Oberthema", day) is False
