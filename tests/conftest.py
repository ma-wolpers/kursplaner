"""Gemeinsame pytest-Fixtures für die Kursplaner-Testsuite."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

import pytest

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import create_root  # noqa: E402

# Tk-Testfenster geben den OS-Vordergrund sofort an das Fenster des Entwicklers
# zurück (keine "geklauten" Tastendrücke während eines Testlaufs); mit
# TK_FOCUS_TESTS=1 deaktiviert. Siehe bw-gui docs/KEYBINDING_CONTRACT.md.
from bw_gui.testing.background_windows import pytest_configure, pytest_unconfigure  # noqa: E402,F401

_TK_ROOT_ATTEMPTS = 3


def _create_tk_root(factory: Callable[[], tk.Tk]) -> tk.Tk:
    """Erzeugt einen Tk-Root und wiederholt den Versuch bei einem Tcl-Startfehler.

    Ein weiterer Root im selben Prozess schlägt unter Windows gelegentlich beim Einlesen
    der Tcl-Bibliothek fehl (``init.tcl``, ``auto.tcl``, wechselnde Meldungen). Beim
    Erzeugen läuft noch kein Testcode, darum gilt jeder ``TclError`` als dieser Fehler.

    Args:
        factory: Erzeugt den Root.

    Returns:
        Der erzeugte Root.
    """
    for _ in range(_TK_ROOT_ATTEMPTS - 1):
        try:
            return factory()
        except tk.TclError:
            pass
    return factory()


@pytest.fixture(scope="session")
def tk_root():
    """Off-screen positionierter Tk-Root ohne Tastatur-Router, geteilt von der ganzen Testsuite.

    Für Tests, die nur Widgets brauchen. Bewusst NICHT `withdraw()`t (lässt
    `winfo_width()`/`winfo_height()` bei 1 hängen, da das Fenster nie eine echte
    Geometrie bekommt), sondern weit außerhalb des sichtbaren Bildschirmbereichs
    positioniert.
    """
    root = _create_tk_root(tk.Tk)
    root.geometry("400x300+3000+3000")
    yield root
    root.destroy()


@pytest.fixture(scope="module")
def root():
    """Versteckter Tk-Root mit bw-gui-Tastatur-Router, je Testdatei ein eigener.

    Nicht geteilt: Testdateien hängen hier Tastenkürzel und Attribute an, die sonst in
    andere Dateien durchschlagen würden.
    """
    instance = _create_tk_root(create_root)
    instance.withdraw()
    yield instance
    instance.destroy()
