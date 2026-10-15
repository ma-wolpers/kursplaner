"""Shortcut table, binder setup, runtime context and popup gating of the main window (ScreenBuilder mixin).

Shortcuts go through one bw-gui ``ApplicationShortcutBinder`` (``all`` router, where
the former ``bind_all`` sat): keys are ``KeySpec``s, handlers return ``EventResult``,
gating (mode, dialog, text input, offline) is the binder's. Modifiers are exact --
the former ``bind_all`` sequences also fired with extra held modifiers (Tk's
minimum-set matching); named keys tolerate Shift where no own Shift variant exists.

Popup gating reads the bw-gui overlay stack (``OVERLAY_STACK_CONTRACT.md``) with the
preset ``blocking(include_menus=True)``: modal popups and menu popups block the
guide shortcuts, non-modal tool windows (Kompetenznetz, loading hint, shortcut debug
window) do not. This reproduces the former scan, which counted every visible direct
child toplevel of the main window (menu popups included) unless it had been tracked
as non-blocking.
"""

from __future__ import annotations

from typing import NamedTuple

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.contracts import EventResult, KeySpec  # noqa: E402
from bw_gui.runtime import ApplicationShortcutBinder, accepts_text_input, on_global_click  # noqa: E402
from bw_gui.runtime.overlay_stack import OverlayCategory, blocking, register_overlay  # noqa: E402

from bw_libs.ui_contract.keybinding import (  # noqa: E402
    UI_MODE_DIALOG,
    UI_MODE_EDITOR,
    UI_MODE_GLOBAL,
    UI_MODE_PREVIEW,
    KeybindingRuntimeContext,
)
from bw_libs.ui_contract.laufkern import verify_manifest, verify_reachability  # noqa: E402
from kursplaner.adapters.gui.laufkern_manifest_provider import build_runtime_shortcut_manifest  # noqa: E402
from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow  # noqa: E402
from kursplaner.adapters.gui.shortcut_guide import load_shortcut_guide_entries  # noqa: E402
from kursplaner.adapters.gui.ui_intents import UiIntent  # noqa: E402

_k = KeySpec.parse
_P = (UI_MODE_PREVIEW,)
_PE = (UI_MODE_PREVIEW, UI_MODE_EDITOR)
_ALL = (UI_MODE_GLOBAL, UI_MODE_PREVIEW, UI_MODE_DIALOG)


class ShortcutRow(NamedTuple):
    """One main-window shortcut declaration (binder input, also read by tests)."""

    keys: object
    handler: object
    binding_id: str
    intent: str
    modes: tuple[str, ...]
    allow_when_text_input: bool = False


class ScreenShortcutsMixin:
    """Shortcut table, binder setup, runtime context and popup gating of the main window (ScreenBuilder mixin)."""

    def _shortcut_rows(self) -> tuple[ShortcutRow, ...]:
        """The fixed main-window shortcuts (the guide entries from ``shortcut_guide.json`` come on top).

        Enter (main and keypad, one ``Key.ENTER``) is exact because Shift+Enter (find
        previous) and Ctrl+Enter (commit) are own definitions; Left/Right are exact
        because of Alt+Left/Right and the guide's Ctrl+Left/Right. Ctrl+Shift+D/O
        formerly read ``<Control-Shift-d>`` and only fired with CapsLock on.
        """
        rename = lambda _e: self._emit_intent(UiIntent.TOOLBAR_RENAME, from_shortcut=True)  # noqa: E731
        rows = [
            ShortcutRow(_k("F2 (tolerate: Shift)"), rename, "global.rename", UiIntent.TOOLBAR_RENAME, (UI_MODE_GLOBAL, UI_MODE_PREVIEW)),
            ShortcutRow(_k("Enter"), self._on_grid_enter, "grid.enter", UiIntent.GRID_ENTER, _P),
            ShortcutRow(_k("Up (tolerate: Shift)"), self._on_grid_nav_up, "grid.nav.up", UiIntent.GRID_NAV_UP, _P),
            ShortcutRow(_k("Down (tolerate: Shift)"), self._on_grid_nav_down, "grid.nav.down", UiIntent.GRID_NAV_DOWN, _P),
            ShortcutRow(_k("Left"), self._on_detail_left, "detail.left", UiIntent.SHORTCUT_DETAIL_LEFT, _P),
            ShortcutRow(_k("Right"), self._on_detail_right, "detail.right", UiIntent.SHORTCUT_DETAIL_RIGHT, _P),
            ShortcutRow(_k("Alt+Left (tolerate: Shift)"), self._on_detail_left_all, "detail.left.all",
                        UiIntent.SHORTCUT_DETAIL_LEFT_ALL, _P),
            ShortcutRow(_k("Alt+Right (tolerate: Shift)"), self._on_detail_right_all, "detail.right.all",
                        UiIntent.SHORTCUT_DETAIL_RIGHT_ALL, _P),
            ShortcutRow(_k("Home (tolerate: Shift)"), self._on_home, "grid.home", UiIntent.GRID_HOME, _P),
            ShortcutRow(_k("End (tolerate: Shift)"), self._on_end, "grid.end", UiIntent.GRID_END, _P),
            ShortcutRow([_k("Delete (tolerate: Shift)"), _k("Backspace (tolerate: Shift)")], self._on_grid_delete,
                        "grid.delete", UiIntent.GRID_DELETE_CELL, _P),
            ShortcutRow(_k("Ctrl+Enter (tolerate: Shift)"), self._on_ctrl_enter, "grid.commit.ctrl-enter",
                        UiIntent.SHORTCUT_COMMIT_EDIT, _PE, True),
            ShortcutRow(_k("Shift+Enter"), self._on_find_previous, "search.find-previous",
                        UiIntent.SHORTCUT_FIND_PREVIOUS, _PE, True),
            ShortcutRow(_k("Ctrl+F"), self._on_search_open, "search.open", UiIntent.SEARCH_OPEN, _P),
            ShortcutRow(_k("Escape (tolerate: Shift)"), self._on_escape, "global.escape", intent=UiIntent.SHORTCUT_ESCAPE,
                        modes=_ALL, allow_when_text_input=True),
            ShortcutRow(_k("Ctrl+Shift+D"), lambda _e: self._open_shortcut_runtime_debug_dialog(), "global.runtime-debug",
                        "debug.shortcut.runtime", _ALL, True),
            ShortcutRow(_k("Ctrl+Shift+O"), lambda _e: self._toggle_shortcut_runtime_offline(), "global.runtime-offline",
                        "debug.shortcut.offline", _ALL, True),
        ]
        rows += [
            ShortcutRow(KeySpec.char(str(digit)),
                        lambda _e, offset=digit: self._emit_intent(UiIntent.SHORTCUT_SELECT_UNIT_BY_OFFSET, offset=offset),
                        f"detail.select-unit-offset.{digit}", UiIntent.SHORTCUT_SELECT_UNIT_BY_OFFSET, _P)
            for digit in range(10)
        ]
        return tuple(rows)

    def _bind_shortcuts(self):
        """Registriert alle Tastaturkürzel der Hauptansicht am Application-Binder und den globalen Klick-Commit."""
        binder = ApplicationShortcutBinder(
            self.app,
            registry=self._runtime_shortcuts,
            dialog_open=self._shortcut_dialog_open,
            offline=lambda: bool(getattr(self.app, "shortcut_debug_offline", False)),
            mode_provider=lambda: UI_MODE_PREVIEW if bool(getattr(self.app, "is_detail_view", False)) else UI_MODE_GLOBAL,
        )
        for index, entry in enumerate(load_shortcut_guide_entries()):
            binder.bind(entry.key, self._build_shortcut_handler(entry), binding_id=f"guide.{entry.intent}.{index}",
                        intent=entry.intent, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW))
        for row in self._shortcut_rows():
            binder.bind(row.keys, row.handler, binding_id=row.binding_id, intent=row.intent, modes=row.modes,
                        allow_when_text_input=row.allow_when_text_input)
        self._shortcut_binder = binder
        # Globaler Klick: Beobachter am all-Router (frueher bind_all("<Button-1>")); nie bei Texteingabe.
        on_global_click(
            self.app,
            lambda event: None if accepts_text_input(event.widget) else self._on_global_click_commit_cell(event),
        )
        self._refresh_intent_help_tooltips()

    def _shortcut_dialog_open(self) -> bool:
        """Meldet, ob ein modales Popup oder ein Menue-Popup offen ist (Overlay-Stack-Preset)."""
        return blocking(self.app, include_menus=True)()

    def _build_runtime_context(self) -> KeybindingRuntimeContext:
        """Gating-Kontext für die Diagnose (dieselben Quellen wie der Binder)."""
        return self._shortcut_binder.build_context()

    def _build_shortcut_handler(self, entry):
        """Erzeugt den Handler eines Shortcut-Guide-Eintrags (``KeyEvent`` -> ``EventResult``)."""

        def _handler(event):
            if self._has_active_popup():
                return EventResult.HANDLED
            if entry.intent.startswith("toolbar.") and self._is_editable_widget(getattr(event, "widget", None)):
                return None
            payload = dict(entry.payload)
            if entry.from_shortcut:
                payload["from_shortcut"] = True
            if entry.intent in (
                UiIntent.SHORTCUT_EXPAND_SELECTED_ROW,
                UiIntent.SHORTCUT_COLLAPSE_SELECTED_ROW,
                UiIntent.SHORTCUT_CUT,
                UiIntent.SHORTCUT_COPY,
                UiIntent.SHORTCUT_PASTE,
                UiIntent.TOOLBAR_UNDO,
                UiIntent.TOOLBAR_REDO,
            ):
                payload["event"] = event
            return self._emit_intent(entry.intent, **payload)

        return _handler

    def _build_laufkern_manifest(self):
        """Build one declarative LaufKern manifest from registered runtime shortcuts."""

        return build_runtime_shortcut_manifest(self._runtime_shortcuts)

    def _summarize_laufkern_reachability(self, *, context: KeybindingRuntimeContext) -> str:
        """Return compact LaufKern reachability summary for current runtime state."""

        manifest = self._build_laufkern_manifest()
        manifest_ok, manifest_errors = verify_manifest(manifest)
        if not manifest_ok:
            return f"LaufKern manifest-errors={len(manifest_errors)}"

        results = verify_reachability(manifest=manifest, context=context)
        reachable = sum(1 for result in results if result.reachable)
        return f"LaufKern intents {reachable}/{len(results)} erreichbar"

    def _register_non_modal_window(self, window) -> None:
        """Meldet ein eigenes, nicht blockierendes Werkzeugfenster im bw-gui-Overlay-Stack an.

        Fuer rohe ``Toplevel``-Fenster am Hauptfenster (Ladehinweis, Shortcut-Debug);
        ``ScrollablePopupWindow``-Dialoge melden sich selbst an (``overlay_category``).
        Die Anmeldung endet mit dem ``<Destroy>`` des Fensters.
        """
        register_overlay(window, OverlayCategory.NON_MODAL_POPUP, toplevel=window)

    def _has_active_popup(self) -> bool:
        """Return whether a blocking overlay or any ``ScrollablePopupWindow`` is open.

        Stricter than the binder's ``dialog_open``: the handlers also stand still while a
        non-modal popup such as the Kompetenznetz is open (unchanged from the former scan).
        """
        return self._shortcut_dialog_open() or ScrollablePopupWindow.has_active_popup()
