from kursplaner.adapters.gui.shortcut_guide import load_shortcut_guide_entries
from kursplaner.adapters.gui.toolbar_viewmodel import TOOLBAR_ACTIONS


def test_toolbar_shortcuts_avoid_shift_modifier():
    entries = load_shortcut_guide_entries()

    violating = [
        entry.display_shortcut
        for entry in entries
        if entry.intent.startswith("toolbar.") and "Shift" in entry.key_sequence
    ]

    assert violating == []


def test_export_shortcut_is_ctrl_p():
    entries = load_shortcut_guide_entries()
    export_entries = [entry for entry in entries if entry.intent == "toolbar.export_as"]

    assert len(export_entries) == 1
    export_entry = export_entries[0]
    assert export_entry.key_sequence == "<Control-p>"
    assert export_entry.display_shortcut == "Strg+P"


def test_column_visibility_shortcut_is_ctrl_l():
    entries = load_shortcut_guide_entries()
    visibility_entries = [entry for entry in entries if entry.intent == "detail.open_column_visibility_settings"]

    assert len(visibility_entries) == 1
    visibility_entry = visibility_entries[0]
    assert visibility_entry.key_sequence == "<Control-l>"
    assert visibility_entry.display_shortcut == "Strg+L"


def test_every_toolbar_button_has_ctrl_shortcut_mapping():
    entries = load_shortcut_guide_entries()
    entry_by_intent = {entry.intent: entry for entry in entries if entry.display_shortcut.startswith("Strg+")}

    intent_by_action_key = {
        "new": "toolbar.new",
        "refresh": "toolbar.refresh",
        "export_as": "toolbar.export_as",
        "extend_to_vacation": "toolbar.extend_to_vacation",
        "undo": "toolbar.undo",
        "redo": "toolbar.redo",
        "plan": "toolbar.plan",
        "ausfall": "toolbar.ausfall",
        "hospitation": "toolbar.hospitation",
        "lzk": "toolbar.lzk",
        "lzk_expected_horizon": "toolbar.lzk",
        "mark_ub": "detail.toggle_resume_or_ub",
        "copy": "shortcut.copy",
        "paste": "shortcut.paste",
        "find": "toolbar.find",
        "clear": "toolbar.clear",
        "rename": "toolbar.rename",
        "split": "toolbar.split",
        "merge": "toolbar.merge",
        "move_left": "toolbar.move_columns",
        "move_right": "toolbar.move_columns",
    }

    missing: list[str] = []
    for action in TOOLBAR_ACTIONS:
        mapped_intent = intent_by_action_key.get(action.key, "")
        if not mapped_intent or mapped_intent not in entry_by_intent:
            missing.append(action.key)

    assert missing == []


def test_lzk_and_lzk_expected_horizon_share_ctrl_k_shortcut():
    entries = load_shortcut_guide_entries()
    lzk_entries = [entry for entry in entries if entry.intent == "toolbar.lzk"]

    assert len(lzk_entries) == 1
    entry = lzk_entries[0]
    assert entry.key_sequence == "<Control-k>"
    assert entry.display_shortcut == "Strg+K"
