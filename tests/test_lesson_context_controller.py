from types import SimpleNamespace

from kursplaner.adapters.gui.lesson_context_controller import MainWindowLessonContextController


def _build_controller():
    app = SimpleNamespace(
        gui_dependencies=SimpleNamespace(
            lesson_context_query=SimpleNamespace(),
            lesson_transfer=SimpleNamespace(),
            rename_linked_file_for_row=None,
        )
    )
    return MainWindowLessonContextController(app)


def test_ub_fields_are_displayed_without_separator_lines():
    controller = _build_controller()
    day = {
        "yaml": {
            "Professionalisierungsschritte": ["Schritt A", "Schritt B"],
            "Nutzbare Ressourcen": ["Res 1", "Res 2"],
        }
    }

    steps = controller.field_value(day, "Professionalisierungsschritte")
    resources = controller.field_value(day, "Nutzbare Ressourcen")

    assert steps == "Schritt A\nSchritt B"
    assert resources == "Res 1\nRes 2"
    assert "—" not in steps
    assert "—" not in resources


def test_other_list_fields_keep_separator_format():
    controller = _build_controller()
    day = {"yaml": {"Kompetenzen": ["K1", "K2"]}}

    value = controller.field_value(day, "Kompetenzen")

    assert value == "K1\n—\nK2"
