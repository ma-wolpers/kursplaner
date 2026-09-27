"""Gemeinsame pytest-Fixtures für die Kursplaner-Testsuite."""

from __future__ import annotations

import tkinter as tk

import pytest

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
# Tk-Testfenster geben den OS-Vordergrund sofort an das Fenster des Entwicklers
# zurück (keine "geklauten" Tastendrücke während eines Testlaufs); mit
# TK_FOCUS_TESTS=1 deaktiviert. Siehe bw-gui docs/KEYBINDING_CONTRACT.md.
from bw_gui.testing.background_windows import pytest_configure, pytest_unconfigure  # noqa: E402,F401


@pytest.fixture(scope="session")
def tk_root():
    """Ein einziger, off-screen positionierter Tk-Root für die gesamte Testsuite.

    Tkinter erlaubt zuverlässig nur EINEN `tk.Tk()`-Root pro Prozess -- ein
    zweiter, nach dem `destroy()` eines vorherigen erzeugter Root, schlägt
    unzuverlässig mit `TclError: Can't find a usable init.tcl`/"tk wasn't
    installed properly" fehl (Tcl/Tk-Bibliothekszustand wird beim ersten
    `destroy()` nicht sauber zurückgesetzt). Session-Scope statt je einem
    modul-lokalen Root pro Testdatei behebt das, indem es diese Situation
    von vornherein ausschließt.

    Bewusst NICHT `withdraw()`t (lässt `winfo_width()`/`winfo_height()` bei
    1 hängen, da das Fenster nie eine echte Geometrie bekommt), sondern weit
    außerhalb des sichtbaren Bildschirmbereichs positioniert.
    """
    root = tk.Tk()
    root.geometry("400x300+3000+3000")
    yield root
    root.destroy()
