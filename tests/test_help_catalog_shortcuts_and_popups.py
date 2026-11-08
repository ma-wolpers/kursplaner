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
    assert "nur im Spaltenauswahlmodus" in MAIN_WINDOW_HELP["clear"]


def test_toolbar_help_texts_name_no_keys_the_binding_supplies_them():
    """Die Taste im Tooltip kommt aus der Bindung (`_add_help(intent=…)`), nie aus dem Text."""
    from kursplaner.adapters.gui.toolbar_viewmodel import TOOLBAR_ACTIONS

    for action in TOOLBAR_ACTIONS:
        if action.help_key is not None:
            assert "Strg+" not in MAIN_WINDOW_HELP[action.help_key], action.key
    for key in ("course_overview_new", "toggle_former_courses", "column_visibility", "resume_ausfall"):
        assert "Strg+" not in MAIN_WINDOW_HELP[key]


def test_toolbar_tooltip_keys_follow_payload_and_shortcut_intent():
    from bw_gui.shortcuts import compose_hover_text_for_intent
    from test_menu_labels_from_bindings import _Resolver

    from kursplaner.adapters.gui.shortcut_guide import binding_metadata
    from kursplaner.adapters.gui.toolbar_viewmodel import TOOLBAR_ACTION_BY_KEY

    class _MetaResolver(_Resolver):
        def shortcut_for_intent(self, intent, *, metadata=None, **_kw):
            from kursplaner.adapters.gui.shortcut_guide import load_shortcut_guide_entries

            for entry in load_shortcut_guide_entries():
                if entry.intent == intent and (metadata or {}).items() <= binding_metadata(entry.payload).items():
                    return entry.key
            return None

    def shown(key):
        action = TOOLBAR_ACTION_BY_KEY[key]
        return compose_hover_text_for_intent(
            "x", intent=action.key_intent, shortcuts=_MetaResolver(), metadata=binding_metadata(action.payload)
        )

    assert shown("move_left").endswith("Strg+Links")
    assert shown("move_right").endswith("Strg+Rechts")
    assert shown("copy").endswith("Strg+C")
    assert shown("paste").endswith("Strg+V")


def test_detail_navigation_help_documents_ctrl_up_down_row_expand_collapse():
    assert "Strg+Runter/Strg+Hoch" in MAIN_WINDOW_HELP["detail_navigation"]
