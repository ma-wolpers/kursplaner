"""Tests für `KompetenzGraphViewModeToggle` -- zyklisches Umschalten (`next_mode()`) und Tooltip-Wiring.

Nutzt einen echten Tk-Parent (`tk_root`-Fixture) statt eines Fakes, da die
Klasse echte `bw_gui`-Widgets (`widgets.Frame`/`widgets.Button`) erzeugt --
ein nicht existierender ttk-Style (`Segmented.TButton` ist hier ungesetzt)
fällt in Tk stillschweigend auf den Default-Style zurück, es wird also kein
Theme-Setup benötigt.
"""

from __future__ import annotations

import tkinter as tk

from kursplaner.adapters.gui.kompetenzgraph_view_mode_toggle import KompetenzGraphViewModeToggle
from kursplaner.core.domain.kompetenzgraph_view_mode import MODE_ABHAENGIGKEITEN, MODE_FORT_VORAUS, MODE_OBER_TEIL


def _build_toggle(tk_root, *, initial_mode: str = MODE_OBER_TEIL, **kwargs) -> KompetenzGraphViewModeToggle:
    """Baut die Toggle-Control in einem eigenen `Toplevel`, nicht direkt in der session-weiten `tk_root`.

    Andere Testdateien packen/gridden ggf. bereits direkt in `tk_root` --
    Tk erlaubt pro Container nur EINEN Geometrie-Manager gleichzeitig
    (`pack` vs. `grid`), ein gemeinsam genutzter Root würde daher je nach
    Testreihenfolge mit `TclError` kollidieren.
    """
    toplevel = tk.Toplevel(tk_root)
    return KompetenzGraphViewModeToggle(
        toplevel, initial_mode=initial_mode, on_mode_selected=kwargs.pop("on_mode_selected", lambda _mode: None), **kwargs
    )


def test_next_mode_cycles_through_all_three_modes_with_wraparound(tk_root):
    toggle = _build_toggle(tk_root, initial_mode=MODE_OBER_TEIL)

    assert toggle.next_mode() == MODE_FORT_VORAUS

    toggle.refresh(MODE_FORT_VORAUS)
    assert toggle.next_mode() == MODE_ABHAENGIGKEITEN

    toggle.refresh(MODE_ABHAENGIGKEITEN)
    assert toggle.next_mode() == MODE_OBER_TEIL  # Wraparound zurück zum ersten Eintrag


def test_clicking_a_button_invokes_on_mode_selected_callback(tk_root):
    selected: list[str] = []
    toggle = _build_toggle(tk_root, initial_mode=MODE_OBER_TEIL, on_mode_selected=selected.append)

    toggle._buttons[MODE_ABHAENGIGKEITEN].invoke()

    assert selected == [MODE_ABHAENGIGKEITEN]


def test_tooltip_is_bound_only_for_mode_with_help_text(tk_root):
    """Nur `MODE_ABHAENGIGKEITEN` bekommt in der Praxis einen Hilfetext -- die anderen beiden Modi
    sind über ihr Label bereits selbsterklärend und bekommen bewusst KEINEN `HoverTooltip`."""
    toggle = _build_toggle(
        tk_root,
        initial_mode=MODE_OBER_TEIL,
        mode_help_text={MODE_ABHAENGIGKEITEN: "Erklärt Teilkompetenz vs. Voraussetzung."},
    )

    assert len(toggle._tooltips) == 1


def test_no_tooltip_bound_when_mode_help_text_is_none(tk_root):
    toggle = _build_toggle(tk_root, initial_mode=MODE_OBER_TEIL)

    assert toggle._tooltips == []
