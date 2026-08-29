"""Tests für `GridRenderer._grow_row_minsize_for_cell()` (Kursplaner Item 2, Perf-Fix 2026-08-29).

`update_column(day_index)` aktualisiert seit diesem Fix nur noch die Zellen
der einen betroffenen Spalte (strukturell selbstverständlich: die Schleife
verwendet ausschließlich den übergebenen `day_index`, nie andere Tage —
kein dedizierter Test nötig, um zu beweisen, dass ein Structural-Loop-Body
nur das tut, was er syntaktisch tun kann). Was tatsächlich Testabdeckung
braucht, ist die neue "nur vergrößern, nie verkleinern"-Logik für die
Zeilenhöhe, die den vorherigen vollständigen `winfo_reqheight()`-Sweep über
alle Tage ersetzt.

Nutzt dasselbe `object.__new__(GridRenderer)`-Muster wie
`test_grid_renderer_next_unit_header.py`, um ohne echten Tk-Root nur die
eine zu testende Methode zu isolieren.
"""

from __future__ import annotations

from types import SimpleNamespace

from kursplaner.adapters.gui.grid_renderer import GridRenderer


class _RowConfigurableStub:
    """Minimaler Tk-Grid-Stub: nur `grid_rowconfigure()` als Query+Setter."""

    def __init__(self) -> None:
        self._minsize_by_row: dict[int, int] = {}

    def grid_rowconfigure(self, row_idx: int, minsize: int | None = None) -> dict:
        if minsize is not None:
            self._minsize_by_row[row_idx] = minsize
            return {}
        return {"minsize": self._minsize_by_row.get(row_idx, 0)}


class _LabelStub:
    def __init__(self, row_idx: int) -> None:
        self._row_idx = row_idx

    def grid_info(self) -> dict:
        return {"row": self._row_idx}


class _CellStub:
    def __init__(self, req_height: int) -> None:
        self._req_height = req_height

    def winfo_reqheight(self) -> int:
        return self._req_height


def _renderer_for_row(field_key: str, row_idx: int) -> tuple[GridRenderer, _RowConfigurableStub]:
    renderer = object.__new__(GridRenderer)
    grid_stub = _RowConfigurableStub()
    renderer.app = SimpleNamespace(
        row_labels={field_key: _LabelStub(row_idx)},
        fixed_inner=grid_stub,
        grid_inner=grid_stub,
    )
    return renderer, grid_stub


def test_grow_row_minsize_increases_when_cell_needs_more_space():
    renderer, grid_stub = _renderer_for_row("Stundenthema", row_idx=2)
    grid_stub.grid_rowconfigure(2, minsize=30)

    renderer._grow_row_minsize_for_cell("Stundenthema", _CellStub(req_height=80))

    assert grid_stub.grid_rowconfigure(2)["minsize"] == 80


def test_grow_row_minsize_never_shrinks_an_existing_row():
    """Bewusste Design-Entscheidung: eine einzelne Spalten-Zelle darf die

    Zeile nicht verkleinern, auch wenn ihr eigener Inhalt kleiner ist als
    zuvor -- eine andere (nicht betroffene) Spalte könnte die Zeile
    weiterhin auf ihrer bisherigen Höhe brauchen. Ein vollständiger
    `refresh_grid_content()` würde das korrekt neu vermessen.
    """
    renderer, grid_stub = _renderer_for_row("Stundenthema", row_idx=2)
    grid_stub.grid_rowconfigure(2, minsize=120)

    renderer._grow_row_minsize_for_cell("Stundenthema", _CellStub(req_height=40))

    assert grid_stub.grid_rowconfigure(2)["minsize"] == 120  # unveraendert, nicht auf 40 geschrumpft


def test_grow_row_minsize_is_noop_for_unknown_field():
    renderer, grid_stub = _renderer_for_row("Stundenthema", row_idx=2)

    renderer._grow_row_minsize_for_cell("Unbekanntes Feld", _CellStub(req_height=999))

    assert grid_stub._minsize_by_row == {}  # kein Eintrag angelegt, kein Fehler
