from kursplaner.adapters.gui.keybinding_registry import (
    UI_MODE_DIALOG,
    UI_MODE_EDITOR,
    UI_MODE_GLOBAL,
    UI_MODE_OFFLINE,
    UI_MODE_PREVIEW,
    KeyBindingDefinition,
    KeybindingRegistry,
    KeybindingRuntimeContext,
)


def test_evaluate_runtime_reason_matrix() -> None:
    registry = KeybindingRegistry()

    global_binding = KeyBindingDefinition(
        binding_id="global.save",
        sequence="<Control-s>",
        intent="save",
        modes=(UI_MODE_GLOBAL,),
        allow_when_text_input=False,
        allow_when_offline=False,
    )
    dialog_binding = KeyBindingDefinition(
        binding_id="dialog.confirm",
        sequence="<Return>",
        intent="dialog.confirm",
        modes=(UI_MODE_DIALOG,),
        allow_when_text_input=True,
    )
    preview_binding = KeyBindingDefinition(
        binding_id="preview.right",
        sequence="<Right>",
        intent="preview.right",
        modes=(UI_MODE_PREVIEW,),
        allow_when_text_input=False,
    )

    registry.register_many((global_binding, dialog_binding, preview_binding))

    context = KeybindingRuntimeContext(active_mode=UI_MODE_EDITOR, text_input_focused=True, dialog_open=False)
    can_execute, reason = registry.evaluate_runtime(global_binding, context)
    assert can_execute is False
    assert reason == "text-input-focus"

    context = KeybindingRuntimeContext(active_mode=UI_MODE_OFFLINE, offline=True)
    can_execute, reason = registry.evaluate_runtime(global_binding, context)
    assert can_execute is False
    assert reason == "offline-disabled"

    context = KeybindingRuntimeContext(active_mode=UI_MODE_PREVIEW, dialog_open=True)
    can_execute, reason = registry.evaluate_runtime(preview_binding, context)
    assert can_execute is False
    assert reason == "dialog-priority"

    context = KeybindingRuntimeContext(active_mode=UI_MODE_DIALOG, dialog_open=True)
    can_execute, reason = registry.evaluate_runtime(dialog_binding, context)
    assert can_execute is True
    assert reason == "active"


def test_active_for_mode_filters_offline_and_text_input() -> None:
    registry = KeybindingRegistry()
    registry.register(
        KeyBindingDefinition(
            binding_id="global.search",
            sequence="<Control-f>",
            intent="search",
            modes=(UI_MODE_GLOBAL,),
            allow_when_text_input=False,
            allow_when_offline=True,
        )
    )
    registry.register(
        KeyBindingDefinition(
            binding_id="editor.commit",
            sequence="<Control-Return>",
            intent="commit",
            modes=(UI_MODE_EDITOR,),
            allow_when_text_input=True,
            allow_when_offline=False,
        )
    )

    active_editor = registry.active_for_mode(UI_MODE_EDITOR, offline=False, text_input_focused=True)
    assert [item.binding_id for item in active_editor] == ["editor.commit"]

    active_offline = registry.active_for_mode(UI_MODE_EDITOR, offline=True, text_input_focused=False)
    assert [item.binding_id for item in active_offline] == ["global.search"]
