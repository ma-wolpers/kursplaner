"""Tests für `GridRenderer._reconcile_column_mounts()` (Kursplaner Item 4,
Stufe 3 -- HOT/WARM-Mounting via `grid()`/`grid_remove()`).

Kein `destroy()` in dieser Stufe: Widgets bleiben immer am Leben, nur ihre
Layout-Sichtbarkeit wechselt. Deshalb kann bei dieser Stufe nichts verloren
gehen -- der Stub unten enthält absichtlich KEINE `save_cell`/
`editor_controller`-Attribute; würde die Methode versehentlich einen Save
auslösen, crasht der Test mit `AttributeError` statt still zu bestehen (die
harte Anforderung "Scrollen speichert nie" ist damit nicht nur behauptet,
sondern strukturell erzwungen).

Stub-Stil (`winfo_manager()`/`grid()`/`grid_remove()`) nach dem Vorbild von
`test_toolbar_geometry_guard.py`, `object.__new__(GridRenderer)`-Isolation
nach dem Vorbild von `test_grid_renderer_column_fast_path.py`.
"""

from __future__ import annotations

from types import SimpleNamespace

from kursplaner.adapters.gui.grid_renderer import GridRenderer


class _CellSlotStub:
    def __init__(self, manager: str = "grid"):
        self._manager = manager
        self.calls: list[str] = []

    def winfo_manager(self) -> str:
        return self._manager

    def grid(self):
        self.calls.append("grid")
        self._manager = "grid"

    def grid_remove(self):
        self.calls.append("grid_remove")
        self._manager = ""


def _renderer(*, cell_widgets, mounted_range, is_rebuilding: bool = False) -> GridRenderer:
    renderer = object.__new__(GridRenderer)
    renderer.app = SimpleNamespace(
        cell_widgets=cell_widgets,
        _is_rebuilding_grid=is_rebuilding,
        viewport_sync_h=SimpleNamespace(mounted_day_index_range=lambda: mounted_range),
    )
    return renderer


def test_cells_inside_window_are_gridded():
    cells = {
        ("Stundenthema", 1): _CellSlotStub(manager=""),  # zuvor ausgeblendet
        ("Stundenthema", 2): _CellSlotStub(manager="grid"),  # bereits sichtbar
    }
    renderer = _renderer(cell_widgets=cells, mounted_range=(1, 3))

    renderer._reconcile_column_mounts()

    assert cells[("Stundenthema", 1)].calls == ["grid"]
    assert cells[("Stundenthema", 2)].calls == ["grid"]  # idempotent, kein Fehler bei erneutem grid()


def test_cells_outside_window_are_grid_removed():
    cells = {
        ("Stundenthema", 0): _CellSlotStub(manager="grid"),
        ("Stundenthema", 8): _CellSlotStub(manager="grid"),
    }
    renderer = _renderer(cell_widgets=cells, mounted_range=(1, 3))

    renderer._reconcile_column_mounts()

    assert cells[("Stundenthema", 0)].calls == ["grid_remove"]
    assert cells[("Stundenthema", 8)].calls == ["grid_remove"]


def test_widget_objects_are_never_replaced_only_toggled():
    """Beweist Widget-Identitaet ueber die Reconciliation hinweg (kein

    Destroy/Recreate an dieser Stelle) -- direkte Objektidentitaets-Pruefung,
    nicht nur unveraendertes Verhalten.
    """
    original = _CellSlotStub(manager="grid")
    cells = {("Stundenthema", 5): original}
    renderer = _renderer(cell_widgets=cells, mounted_range=(0, 2))  # Tag 5 liegt ausserhalb

    renderer._reconcile_column_mounts()

    assert cells[("Stundenthema", 5)] is original
    assert original.calls == ["grid_remove"]


def test_noop_when_mounted_range_is_none():
    cell = _CellSlotStub(manager="grid")
    renderer = _renderer(cell_widgets={("Stundenthema", 0): cell}, mounted_range=None)

    renderer._reconcile_column_mounts()

    assert cell.calls == []  # weder grid() noch grid_remove() aufgerufen


def test_noop_while_rebuild_is_in_progress():
    cell = _CellSlotStub(manager="grid")
    renderer = _renderer(
        cell_widgets={("Stundenthema", 0): cell}, mounted_range=(5, 7), is_rebuilding=True
    )  # Tag 0 waere ausserhalb -> wuerde ohne Guard grid_remove() ausloesen

    renderer._reconcile_column_mounts()

    assert cell.calls == []


def test_reconciliation_never_touches_persistence():
    """Der App-Stub hat bewusst KEIN `save_cell`/`editor_controller` -- ein

    versehentlicher Save-Aufruf wuerde hier mit AttributeError crashen statt
    still durchzulaufen. Mehrere Zellen in wechselnden In-/Out-of-Window-
    Zustaenden, um jeden Codepfad der Methode einmal zu durchlaufen.
    """
    cells = {
        ("Stundenthema", 0): _CellSlotStub(manager="grid"),
        ("Stundenthema", 1): _CellSlotStub(manager=""),
        ("Oberthema", 2): _CellSlotStub(manager="grid"),
        ("Oberthema", 9): _CellSlotStub(manager="grid"),
    }
    renderer = _renderer(cell_widgets=cells, mounted_range=(1, 2))

    renderer._reconcile_column_mounts()  # crasht, falls irgendein Persistenzpfad beruehrt wird

    assert cells[("Stundenthema", 0)].calls == ["grid_remove"]
    assert cells[("Stundenthema", 1)].calls == ["grid"]
    assert cells[("Oberthema", 2)].calls == ["grid"]
    assert cells[("Oberthema", 9)].calls == ["grid_remove"]
