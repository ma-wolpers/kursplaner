from kursplaner.adapters.gui.lesson_builder_dialog import (
    LessonKompetenzenSelectionDialog,
    LessonStundenzielSelectionDialog,
)


def test_kompetenzen_dialog_escape_closes_like_cancel():
    dialog = LessonKompetenzenSelectionDialog.__new__(LessonKompetenzenSelectionDialog)
    calls = {"request_close": 0}

    def _request_close():
        calls["request_close"] += 1
        return "break"

    dialog._request_close = _request_close

    result = LessonKompetenzenSelectionDialog._on_escape(dialog)

    assert result == "break"
    assert calls["request_close"] == 1


def test_stundenziel_dialog_escape_closes_like_cancel():
    dialog = LessonStundenzielSelectionDialog.__new__(LessonStundenzielSelectionDialog)
    calls = {"request_close": 0}

    def _request_close():
        calls["request_close"] += 1
        return "break"

    dialog._request_close = _request_close

    result = LessonStundenzielSelectionDialog._on_escape(dialog)

    assert result == "break"
    assert calls["request_close"] == 1
