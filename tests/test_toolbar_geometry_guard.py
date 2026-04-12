from types import SimpleNamespace

import pytest

from kursplaner.adapters.gui.action_controller import MainWindowActionController


class _SlotStub:
    def __init__(self, manager: str = ""):
        self._manager = manager
        self.calls: list[str] = []

    def winfo_manager(self) -> str:
        return self._manager

    def grid(self):
        self.calls.append("grid")
        self._manager = "grid"

    def grid_remove(self):
        self.calls.append("grid_remove")


def _controller_with_slot(slot_key: str, slot: _SlotStub) -> MainWindowActionController:
    controller = MainWindowActionController.__new__(MainWindowActionController)
    controller.app = SimpleNamespace(toolbar_slots={slot_key: slot})
    return controller


def test_set_slot_visibility_uses_grid_for_existing_grid_managed_slots():
    slot = _SlotStub(manager="grid")
    controller = _controller_with_slot("new", slot)

    controller._set_slot_visibility("new", True)
    controller._set_slot_visibility("new", False)

    assert slot.calls == ["grid", "grid_remove"]


def test_set_slot_visibility_ignores_unmanaged_slots_until_layout_assigns_grid():
    slot = _SlotStub(manager="")
    controller = _controller_with_slot("new", slot)

    controller._set_slot_visibility("new", True)

    assert slot.calls == []


def test_set_slot_visibility_raises_for_pack_managed_toolbar_slot():
    slot = _SlotStub(manager="pack")
    controller = _controller_with_slot("new", slot)

    with pytest.raises(RuntimeError, match="unexpected geometry manager 'pack'"):
        controller._set_slot_visibility("new", True)
