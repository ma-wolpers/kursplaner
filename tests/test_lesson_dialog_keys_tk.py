"""Echte Tastatur-/Klick-Kette der Unterrichts-Dialoge (``LessonDialogKeysMixin``).

Dialoge an einem echten Tk-Root mit bw-gui-Router (``create_root``), nur synthetische
Optionen. Tasten laufen über ``bw_gui.testing.keys.press_key`` (alle bw-gui-Dispatcher
in Bindtag-Reihenfolge, ohne OS-Fokus; native Klassenbindungen werden nicht
simuliert). Abgesichert: Overlay-Pfeile/Enter im Feld, Strg+Enter (auch Ziffernblock),
exakte Tab-Varianten, die Nach-Phase des Filterfelds (setzt die Auswahl nach ↓ nicht
mehr zurück), Schließen des Overlays bei Klick außerhalb und das Ende des
Klick-Beobachters mit dem Dialog.
"""

from __future__ import annotations

import tkinter

import pytest

from bw_gui.runtime import create_root, ui, widgets
from bw_gui.runtime.key_router import router_for
from bw_gui.testing.keys import press_key

from kursplaner.adapters.gui.lesson_builder_dialog import LessonBuilderDialog, LessonKompetenzenSelectionDialog

SHIFT, CONTROL = 0x0001, 0x0004
OPTIONS = ["# Bereich", "Kompetenz A", "Kompetenz B", "Kompetenz C"]


@pytest.fixture(scope="module")
def root():
    """Eigener Root mit Router (der Session-Root aus conftest hat keinen)."""
    for attempt in range(3):
        try:
            instance = create_root()
            break
        except tkinter.TclError as exc:
            if not any(m in str(exc) for m in ("usable", "tcl_findLibrary", "init.tcl")) or attempt == 2:
                raise
    instance.withdraw()
    yield instance
    instance.destroy()


@pytest.fixture(scope="module")
def host(root):
    """Sichtbarer Master: Dialoge sind ``transient`` -- unter Windows bleibt ein transientes
    Fenster eines versteckten Masters (hier der Root) selbst versteckt."""
    window = ui.Toplevel(root)
    window.geometry("200x100+40+40")
    window.update()
    yield window
    window.destroy()


@pytest.fixture
def kompetenzen(host):
    dialog = LessonKompetenzenSelectionDialog(host, date_label="01.01.", kompetenzen_options=list(OPTIONS))
    dialog.update()
    yield dialog
    if dialog.winfo_exists():
        dialog.destroy()


def _open(dialog, field: str, text) -> None:
    """Fokus ins Feld (wie beim Klick), dann Overlay öffnen -- sonst schließt der
    Fokuswechsel des Modal-Fokus-Helfers (``after_idle``) das Overlay gleich wieder."""
    text.focus_force()
    dialog.update()
    dialog.overlay_controller.open(field, text)
    dialog.update()


def test_overlay_arrows_and_enter_pick_in_field(kompetenzen):
    text = kompetenzen.kompetenzen_field.text
    _open(kompetenzen, "kompetenzen", text)
    assert press_key(text, "Down") is True
    assert press_key(text, "Down", state=SHIFT) is True  # Shift toleriert wie früher
    assert kompetenzen.overlay_controller.listbox.curselection() == (2,)
    assert press_key(text, "Up") is True
    assert press_key(text, "Return", char="\r") is True
    assert kompetenzen.kompetenzen_field.get() == "Kompetenz A"


def test_enter_runs_on_when_overlay_closed_and_ctrl_down_is_native(kompetenzen):
    text = kompetenzen.kompetenzen_field.text
    kompetenzen.overlay_controller.close()
    assert press_key(text, "Return", char="\r") is False  # Text fügt den Umbruch ein
    assert press_key(text, "Down", state=CONTROL) is False  # exakte Modifier: native Textbewegung


def test_tab_variants_are_exact(kompetenzen):
    text = kompetenzen.kompetenzen_field.text
    assert press_key(text, "Tab") is True
    assert press_key(text, "Tab", state=SHIFT) is True
    assert press_key(text, "ISO_Left_Tab", state=SHIFT) is True
    assert press_key(text, "Tab", state=CONTROL) is False


def test_ctrl_enter_accepts_from_field_and_keypad(host):
    for keysym in ("Return", "KP_Enter"):
        dialog = LessonKompetenzenSelectionDialog(
            host, date_label="01.01.", kompetenzen_options=list(OPTIONS), kompetenzen_initial=["Kompetenz B"]
        )
        dialog.update()
        assert press_key(dialog.kompetenzen_field.text, keysym, char="\r", state=CONTROL) is True
        assert dialog.result is not None and dialog.result.kompetenzen_refs == ["Kompetenz B"]
        assert not dialog.winfo_exists()


def test_click_outside_closes_overlay_and_observer_ends_with_dialog(root, kompetenzen):
    text = kompetenzen.kompetenzen_field.text
    outside = widgets.Label(kompetenzen.content, text="aussen")
    outside.pack()
    _open(kompetenzen, "kompetenzen", text)
    kompetenzen.update()
    assert kompetenzen.overlay_controller.is_open
    outside.event_generate("<ButtonPress-1>", x=1, y=1)
    kompetenzen.update()
    assert not kompetenzen.overlay_controller.is_open
    subscription = kompetenzen._overlay_click_subscription
    kompetenzen.destroy()
    assert not subscription.active
    assert router_for(root).verify() == []


def test_filter_field_keeps_selection_after_down_and_refilters_after_typing(host):
    dialog = LessonBuilderDialog(
        host,
        date_label="01.01.",
        topic_initial="Thema",
        oberthema_initial="",
        kompetenzen_options=[],
        stundenziel_options=[],
        inhalte_options=["Inhalt Alpha", "Inhalt Beta", "Inhalt Gamma"],
        methodik_options=[],
    )
    try:
        dialog.update()
        text = dialog.inhalte_query_field.text
        _open(dialog, "inhalte", text)
        assert press_key(text, "Down") is True
        # Früher: KeyRelease -> refresh() -> Auswahl wieder Zeile 0.
        assert dialog.overlay_controller.listbox.curselection() == (1,)
        dialog.inhalte_query_field.set("gam")  # vom Text-Widget eingefügt (Klasse nicht simuliert)
        assert press_key(text, "m", char="m") is False  # Nach-Phase filtert, verbraucht nicht
        assert dialog.overlay_controller.items == ["Inhalt Gamma"]
    finally:
        dialog.destroy()
