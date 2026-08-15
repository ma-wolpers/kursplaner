from types import SimpleNamespace

from kursplaner.adapters.gui.grid_renderer import GridRenderer
from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.usecases.row_display_mode_usecase import RowDisplayModeUseCase, RowFilterSettings
from tests.day_column_factory import make_day_column


def _make_app(field_mode_overrides: dict[str, frozenset[str]] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        row_filter_settings=RowFilterSettings(field_mode_overrides=field_mode_overrides or {}),
        row_display_mode_usecase=RowDisplayModeUseCase(),
    )


def _linked_day(tmp_path) -> DayColumn:
    lesson_dir = tmp_path / "Einheiten"
    lesson_dir.mkdir(exist_ok=True)
    link = lesson_dir / "abc123.md"
    link.write_text("---\nStundentyp: Unterricht\nDauer: 2\nStundenthema: Thema\n---\n", encoding="utf-8")
    return make_day_column(link=link, yaml={"Stundentyp": "Unterricht", "Stundenthema": "Thema"})


def _unlinked_day() -> DayColumn:
    return make_day_column()


def _unlinked_ausfall_day() -> DayColumn:
    return make_day_column(thema_ausfall="X Ausfall")


def _linked_ausfall_day(tmp_path) -> DayColumn:
    lesson_dir = tmp_path / "Einheiten"
    lesson_dir.mkdir(exist_ok=True)
    link = lesson_dir / "abc123.md"
    link.write_text("---\nStundentyp: Unterricht\nDauer: 2\nStundenthema: Thema\n---\n", encoding="utf-8")
    return make_day_column(link=link, thema_ausfall="X Ausfall", yaml={"Stundentyp": "Unterricht"})


def test_unlinked_day_only_shows_inhalt_stunden_startzeit_and_oberthema():
    app = _make_app()
    renderer = GridRenderer(app)
    day = _unlinked_day()

    assert renderer._field_is_visible_for_day("inhalt", day) is True
    assert renderer._field_is_visible_for_day("stunden", day) is True
    assert renderer._field_is_visible_for_day("startzeit", day) is True
    assert renderer._field_is_visible_for_day("Oberthema", day) is True
    assert renderer._field_is_visible_for_day("Stundenthema", day) is False


def test_unlinked_day_respects_row_filter(tmp_path):
    app = _make_app(field_mode_overrides={"inhalt": frozenset()})
    renderer = GridRenderer(app)
    day = _unlinked_day()

    assert renderer._field_is_visible_for_day("inhalt", day) is False


def test_hidden_field_invisible_on_linked_day(tmp_path):
    app = _make_app(field_mode_overrides={"Oberthema": frozenset()})
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
    app = _make_app(field_mode_overrides={"Stundenthema": frozenset()})
    renderer = GridRenderer(app)
    day = _linked_day(tmp_path)

    assert renderer._field_is_visible_for_day("Stundenthema", day) is False


def test_filter_does_not_hide_other_fields(tmp_path):
    app = _make_app(field_mode_overrides={"Oberthema": frozenset()})
    renderer = GridRenderer(app)
    day = _linked_day(tmp_path)

    assert renderer._field_is_visible_for_day("Stundenthema", day) is True


def test_field_can_be_added_to_a_mode_it_is_not_part_of_by_default(tmp_path):
    """Vier-Checkboxen-Feature: ein Feld kann per Override zusätzlich in einem
    Modus gezeigt werden, in dem es standardmäßig nicht vorkommt."""
    app = _make_app(field_mode_overrides={"Stundenziel": frozenset({RowDisplayModeUseCase.MODE_AUSFALL})})
    renderer = GridRenderer(app)
    day = _linked_ausfall_day(tmp_path)

    assert renderer._field_is_visible_for_day("Stundenziel", day) is True


def test_ausfallgrund_visible_on_ausfall_day_but_not_unterricht_day(tmp_path):
    app = _make_app()
    renderer = GridRenderer(app)
    ausfall_day = _linked_ausfall_day(tmp_path)
    unterricht_day = _linked_day(tmp_path)

    assert renderer._field_is_visible_for_day("Ausfallgrund", ausfall_day) is True
    assert renderer._field_is_visible_for_day("Ausfallgrund", unterricht_day) is False


def test_oberthema_is_editable_on_unlinked_unterricht_day():
    use_case = RowDisplayModeUseCase()
    day = _unlinked_day()

    assert use_case.is_editable("Oberthema", day) is True


def test_oberthema_is_not_editable_on_unlinked_ausfall_day():
    use_case = RowDisplayModeUseCase()
    day = _unlinked_ausfall_day()

    assert use_case.is_editable("Oberthema", day) is False


def test_ausfallgrund_is_never_editable():
    use_case = RowDisplayModeUseCase()
    day = _unlinked_ausfall_day()

    assert use_case.is_editable("Ausfallgrund", day) is False
