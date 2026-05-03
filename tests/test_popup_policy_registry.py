from kursplaner.adapters.gui.popup_policy import POPUP_KIND_MODAL, POPUP_KIND_NON_MODAL, PopupPolicy, PopupPolicyRegistry


def test_popup_registry_tracks_active_stack() -> None:
    registry = PopupPolicyRegistry()
    registry.register_policy(PopupPolicy(policy_id="dialog.modal", kind=POPUP_KIND_MODAL))

    session_a = registry.open_popup("popup-a", "A", "dialog.modal")
    session_b = registry.open_popup("popup-b", "B", "dialog.modal")

    assert session_a.popup_id == "popup-a"
    assert session_b.popup_id == "popup-b"
    assert registry.has_active_popup() is True
    assert registry.active_popup() is not None
    assert registry.active_popup().popup_id == "popup-b"

    assert registry.close_popup("popup-b") is True
    assert registry.active_popup() is not None
    assert registry.active_popup().popup_id == "popup-a"

    assert registry.close_popup("popup-a") is True
    assert registry.has_active_popup() is False
    assert registry.active_popup() is None


def test_popup_manifest_contains_registered_policy_and_stack_ids() -> None:
    registry = PopupPolicyRegistry()
    registry.register_policy(PopupPolicy(policy_id="dialog.modal", kind=POPUP_KIND_MODAL))
    registry.open_popup("popup-debug", "Debug", "dialog.modal")

    manifest = registry.popup_manifest()
    assert manifest["policies"] == ["dialog.modal"]
    assert manifest["active_stack"] == ["popup-debug"]


def test_mode_blocking_popup_respects_policy_flag() -> None:
    registry = PopupPolicyRegistry()
    registry.register_policy(PopupPolicy(policy_id="dialog.modal", kind=POPUP_KIND_MODAL))
    registry.register_policy(
        PopupPolicy(
            policy_id="dialog.non_blocking",
            kind=POPUP_KIND_NON_MODAL,
            affects_mode=False,
            trap_focus=False,
        )
    )

    registry.open_popup("runtime", "Runtime", "dialog.non_blocking")
    assert registry.has_active_popup() is True
    assert registry.has_mode_blocking_popup() is False

    registry.open_popup("modal", "Modal", "dialog.modal")
    assert registry.has_mode_blocking_popup() is True
