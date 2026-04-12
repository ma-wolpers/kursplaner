from kursplaner.adapters.gui.help_catalog import LESSON_BUILDER_HELP, MAIN_WINDOW_HELP


def test_popup_help_texts_document_escape_as_cancel():
    assert "Esc entspricht Abbrechen" in LESSON_BUILDER_HELP["kompetenzen"]
    assert "Esc entspricht Abbrechen" in LESSON_BUILDER_HELP["stundenziel"]


def test_lesson_builder_help_includes_teilziele_didactic_frame():
    assert "Am Ende dieser Einheit können die Lernenden auch" in LESSON_BUILDER_HELP["teilziele"]


def test_main_window_help_texts_document_strict_shortcut_contexts():
    assert "nicht im Textfeld" in MAIN_WINDOW_HELP["undo"]
    assert "nicht im Textfeld" in MAIN_WINDOW_HELP["redo"]
    assert "Spaltenauswahl" in MAIN_WINDOW_HELP["copy"]
    assert "Zellauswahl" in MAIN_WINDOW_HELP["copy"]
    assert "Spaltenauswahl" in MAIN_WINDOW_HELP["paste"]
    assert "Zellauswahl" in MAIN_WINDOW_HELP["paste"]
    assert "nicht-leerer Zwischenablage" in MAIN_WINDOW_HELP["paste"]
    assert "Strg+X" in MAIN_WINDOW_HELP["cut"]
    assert "nur im Spaltenauswahlmodus" in MAIN_WINDOW_HELP["clear"]


def test_detail_navigation_help_documents_ctrl_up_down_row_expand_collapse():
    assert "Strg+Runter/Strg+Hoch" in MAIN_WINDOW_HELP["detail_navigation"]
