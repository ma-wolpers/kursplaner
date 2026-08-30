"""Gemeinsame pytest-Fixtures für die Kursplaner-Testsuite."""

from __future__ import annotations

import tkinter as tk

import pytest


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
