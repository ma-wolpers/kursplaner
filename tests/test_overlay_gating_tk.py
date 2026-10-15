"""Charakterisierung: früherer Popup-Scan gegen bw-gui-Overlay-Stack + Preset (echtes Tk).

Bis 2026-10-15 bestimmte ``ScreenBuilder._sync_popup_sessions_from_windows`` die
Popup-Sperre der Hauptfenster-Kürzel: jedes sichtbare (nicht ``withdrawn``) direkte
Kind-Toplevel des Hauptfensters galt als blockierend, außer es war per
``_track_popup_window(..., "dialog.non_blocking")`` als nicht blockierend markiert.
:func:`_former_scan_blocks` konserviert genau diesen Algorithmus als Referenz.

Jetzt liest ``_shortcut_dialog_open`` den Overlay-Stack mit
``blocking(include_menus=True)``. Für jede Popup-Art aus dem Inventar
(``OVERLAY_STACK_CONTRACT.md``, Kursplaner-Abschnitt) und für Kombinationen müssen beide
übereinstimmen; zusätzlich darf kein sichtbares Fenster unangemeldet sein
(``unregistered_visible_toplevels``). Nur synthetische Fenster, keine App-Daten.
"""

from __future__ import annotations

import tkinter

import pytest
from bw_gui.menu.custom_menu_bar import CustomMenuBar
from bw_gui.menu.menu_types import MenuItem
from bw_gui.runtime import create_root, ui, widgets
from bw_gui.runtime.overlay_stack import OverlayCategory, unregistered_visible_toplevels

from kursplaner.adapters.gui.hover_tooltip import HoverTooltip
from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.adapters.gui.screen_builder import ScreenBuilder
from kursplaner.adapters.gui.selection_overlay_controller import SelectionOverlayController


def _former_scan_blocks(app, non_blocking_ids: set[str]) -> bool:
    """Referenz: der frühere Scan (sichtbare direkte Kind-Toplevels, ohne ``non_blocking``)."""
    for child in app.winfo_children():
        if not isinstance(child, ui.Toplevel):
            continue
        if str(child.state()).lower() == "withdrawn":
            continue
        if str(child) not in non_blocking_ids:
            return True
    return False


@pytest.fixture(scope="module")
def app():
    """Sichtbarer Root als Hauptfenster (transiente Popups eines versteckten Masters blieben versteckt)."""
    for attempt in range(3):
        try:
            instance = create_root()
            break
        except tkinter.TclError as exc:
            if not any(m in str(exc) for m in ("usable", "tcl_findLibrary", "init.tcl")) or attempt == 2:
                raise
    instance.geometry("300x200+30+30")
    instance.update()
    yield instance
    instance.destroy()


@pytest.fixture
def scene(app):
    """Öffnet Popup-Arten auf Abruf und räumt sie wieder ab."""
    builder = ScreenBuilder(app)
    opened: list[object] = []
    non_blocking: set[str] = set()

    class Scene:
        def modal(self):
            popup = ScrollablePopupWindow(app, title="Modal", geometry="200x120", minsize=(100, 80))
            opened.append(popup)
            return popup

        def tool_window(self):
            """Wie der Kompetenznetz-Dialog: ScrollablePopupWindow, nicht blockierend."""
            popup = ScrollablePopupWindow(
                app, title="Werkzeug", geometry="200x120", minsize=(100, 80),
                overlay_category=OverlayCategory.NON_MODAL_POPUP,
            )
            non_blocking.add(str(popup))
            opened.append(popup)
            return popup

        def raw_hint(self):
            """Wie Ladehinweis / Shortcut-Debug: rohes Toplevel am Hauptfenster."""
            window = ui.Toplevel(app)
            builder._register_non_modal_window(window)
            non_blocking.add(str(window))
            opened.append(window)
            return window

        def menu(self):
            bar = CustomMenuBar(app, (), theme_key="mono_day")
            anchor = ui.Frame(app, width=40, height=20)
            anchor.place(x=10, y=10)
            app.update_idletasks()
            # Der Fokus-Watchdog schliesst Popups, sobald Testfenster den Fokus zurueckholen;
            # fuer die Dauer der Szene bleibt er ausgesetzt (wie in bw-gui test_menu_popup_placement).
            suspended = bar._focus_watchdog_suspended()
            suspended.__enter__()
            bar.open_popup(anchor, (MenuItem(type="command", label="Eins"),), 0, "datei")
            opened.append((bar, anchor, suspended))
            return bar

        def tooltip(self):
            label = widgets.Label(app, text="Hover")
            label.pack()
            tip = HoverTooltip(label, "Hilfe")
            app.update()
            tip._show()
            opened.append(label)
            return tip

        def selection_overlay(self, owner):
            controller = SelectionOverlayController(
                owner, get_items=lambda _f: ["A", "B"], on_pick=lambda *_a: None, is_heading=lambda _i: False
            )
            anchor = widgets.Label(owner.content, text="Feld")
            anchor.pack()
            controller.open("feld", anchor)
            return controller

        def check(self):
            app.update()
            assert builder._shortcut_dialog_open() is _former_scan_blocks(app, non_blocking)
            assert unregistered_visible_toplevels(app) == []
            return builder._shortcut_dialog_open()

    yield Scene()
    for item in reversed(opened):
        try:
            if isinstance(item, tuple):
                bar, anchor, suspended = item
                bar.close_popups_from_level(0)
                suspended.__exit__(None, None, None)
                anchor.destroy()
            else:
                item.destroy()
        except tkinter.TclError:
            pass
    app.update()


def test_nothing_open(scene):
    assert scene.check() is False


def test_modal_popup_blocks(scene):
    scene.modal()
    assert scene.check() is True


def test_tool_window_and_raw_hint_do_not_block(scene):
    scene.tool_window()
    assert scene.check() is False
    scene.raw_hint()
    assert scene.check() is False


def test_menu_popup_blocks_like_the_former_scan(scene):
    scene.menu()
    assert scene.check() is True


def test_tooltip_never_blocks(scene):
    tip = scene.tooltip()
    assert scene.check() is False
    assert tip._tip is not None and tip._tip.winfo_viewable()  # der Tooltip war wirklich sichtbar


def test_selection_overlay_inside_a_tool_window_never_blocks(scene):
    controller = scene.selection_overlay(scene.tool_window())
    assert scene.check() is False
    assert controller.is_open  # das Overlay war wirklich sichtbar


def test_combinations(scene):
    scene.tool_window()
    scene.raw_hint()
    modal = scene.modal()
    assert scene.check() is True
    modal.destroy()
    assert scene.check() is False
    scene.menu()
    assert scene.check() is True


def test_closed_popups_unblock(scene):
    popup = scene.modal()
    assert scene.check() is True
    popup._request_close()
    assert scene.check() is False
