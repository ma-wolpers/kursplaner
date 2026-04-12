from types import SimpleNamespace

from kursplaner.adapters.gui.lesson_builder_dialog import (
    LessonBuilderDialog,
    LessonKompetenzenSelectionDialog,
    LessonStundenzielSelectionDialog,
)
from kursplaner.adapters.gui.wrapped_text_field import WrappedTextField


class _Focusable:
    def __init__(self):
        self.focus_calls = 0

    def focus_set(self):
        self.focus_calls += 1


def test_wrapped_text_field_left_delete_span_deletes_previous_word_and_spaces():
    assert WrappedTextField._left_delete_span("Hallo Welt") == 4
    assert WrappedTextField._left_delete_span("Hallo Welt   ") == 7


def test_wrapped_text_field_right_delete_span_deletes_next_word_and_spaces():
    assert WrappedTextField._right_delete_span("Welt hier") == 4
    assert WrappedTextField._right_delete_span("   Welt hier") == 7


def test_lesson_builder_tab_focus_moves_forward_without_wrap():
    dialog = LessonBuilderDialog.__new__(LessonBuilderDialog)
    first = _Focusable()
    second = _Focusable()
    dialog.__dict__["_tab_order"] = [first, second]

    result = LessonBuilderDialog._move_tab_focus(dialog, first, +1)

    assert result == "break"
    assert second.focus_calls == 1


def test_lesson_builder_tab_focus_stops_at_last_field():
    dialog = LessonBuilderDialog.__new__(LessonBuilderDialog)
    first = _Focusable()
    second = _Focusable()
    dialog.__dict__["_tab_order"] = [first, second]

    result = LessonBuilderDialog._move_tab_focus(dialog, second, +1)

    assert result == "break"
    assert first.focus_calls == 0
    assert second.focus_calls == 0


def test_kompetenzen_dialog_tab_focus_single_field_no_wrap():
    dialog = LessonKompetenzenSelectionDialog.__new__(LessonKompetenzenSelectionDialog)
    only = _Focusable()
    dialog.__dict__["_tab_order"] = [only]

    result = LessonKompetenzenSelectionDialog._move_tab_focus(dialog, only, +1)

    assert result == "break"
    assert only.focus_calls == 0


def test_stundenziel_dialog_tab_focus_single_field_no_wrap():
    dialog = LessonStundenzielSelectionDialog.__new__(LessonStundenzielSelectionDialog)
    only = _Focusable()
    dialog.__dict__["_tab_order"] = [only]

    result = LessonStundenzielSelectionDialog._move_tab_focus(dialog, only, -1)

    assert result == "break"
    assert only.focus_calls == 0


def test_lesson_builder_stundenziel_overlay_pick_keeps_overlay_open():
    dialog = LessonBuilderDialog.__new__(LessonBuilderDialog)
    set_calls: list[str] = []
    close_calls = {"count": 0}

    dialog.__dict__["stundenziel_field"] = SimpleNamespace(set=lambda value: set_calls.append(value))
    dialog.__dict__["overlay_controller"] = SimpleNamespace(
        close=lambda: close_calls.__setitem__("count", close_calls["count"] + 1)
    )

    LessonBuilderDialog._on_overlay_pick(dialog, "stundenziel", "Ziel A")

    assert set_calls == ["Ziel A"]
    assert close_calls["count"] == 0


def test_lesson_builder_format_ub_list_with_entries():
    formatted = LessonBuilderDialog._format_ub_list(["Punkt A", " Punkt B "])

    assert formatted == "- Punkt A\n- Punkt B"


def test_lesson_builder_format_ub_list_empty_returns_placeholder():
    formatted = LessonBuilderDialog._format_ub_list([" ", ""])

    assert formatted == "- Keine Einträge vorhanden."
