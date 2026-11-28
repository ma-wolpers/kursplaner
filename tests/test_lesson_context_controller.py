from types import SimpleNamespace

from kursplaner.adapters.gui.lesson_context_controller import MainWindowLessonContextController
from tests.day_column_factory import make_day_column


def _build_controller():
    app = SimpleNamespace(
        gui_dependencies=SimpleNamespace(
            lesson_context_query=SimpleNamespace(),
            lesson_transfer=SimpleNamespace(),
            rename_linked_file_for_row=None,
        )
    )
    return MainWindowLessonContextController(app)


def test_ub_fields_use_the_same_list_format_as_other_list_fields():
    controller = _build_controller()
    day = make_day_column(yaml={"Baustellen": ["Schritt A", "Schritt B"], "Ressourcen": ["Res 1"]})

    assert controller.field_value(day, "Baustellen") == "Schritt A\n--\nSchritt B"
    assert controller.field_value(day, "Ressourcen") == "Res 1"


def test_other_list_fields_keep_separator_format():
    controller = _build_controller()
    day = make_day_column(yaml={"Kompetenzen": ["K1", "K2"]})

    value = controller.field_value(day, "Kompetenzen")

    assert value == "K1\n--\nK2"


def test_ausfallgrund_returns_header_content_on_cancel_day():
    controller = _build_controller()
    day = make_day_column(thema_ausfall="X Lehrerfortbildung")

    assert controller.field_value(day, "Ausfallgrund") == "Lehrerfortbildung"


def test_ausfallgrund_is_empty_on_non_cancel_day():
    controller = _build_controller()
    day = make_day_column()

    assert controller.field_value(day, "Ausfallgrund") == ""
