from types import SimpleNamespace

from kursplaner.adapters.gui.lesson_builder_dialog import LessonBuilderDialog


class _FocusSpy:
    def __init__(self):
        self.calls = 0

    def focus_set(self):
        self.calls += 1


def test_move_tab_focus_recovers_when_focus_not_in_tab_order():
    first = _FocusSpy()
    second = _FocusSpy()
    fake_dialog = SimpleNamespace(_tab_order=[first, second])

    result = LessonBuilderDialog._move_tab_focus(fake_dialog, current_widget=object(), direction=+1)

    assert result == "break"
    assert first.calls == 1
    assert second.calls == 0


def test_move_tab_focus_wraps_to_last_on_reverse_from_outside():
    first = _FocusSpy()
    second = _FocusSpy()
    fake_dialog = SimpleNamespace(_tab_order=[first, second])

    result = LessonBuilderDialog._move_tab_focus(fake_dialog, current_widget=object(), direction=-1)

    assert result == "break"
    assert first.calls == 0
    assert second.calls == 1
