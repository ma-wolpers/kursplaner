"""Shortcut binding, runtime context and popup tracking of the main window (ScreenBuilder mixin).

Split out of screen_builder.py (file-size rule); method bodies unchanged."""

from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui  # noqa: E402

from bw_libs.ui_contract.keybinding import (  # noqa: E402
    UI_MODE_DIALOG,
    UI_MODE_EDITOR,
    UI_MODE_GLOBAL,
    UI_MODE_OFFLINE,
    UI_MODE_PREVIEW,
    KeyBindingDefinition,
    KeybindingRuntimeContext,
)
from bw_libs.ui_contract.laufkern import verify_manifest, verify_reachability  # noqa: E402
from kursplaner.adapters.gui.laufkern_manifest_provider import build_runtime_shortcut_manifest  # noqa: E402
from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow  # noqa: E402
from kursplaner.adapters.gui.shortcut_guide import load_shortcut_guide_entries  # noqa: E402
from kursplaner.adapters.gui.tk_sequence_keyspec import tk_sequence_to_keyspec  # noqa: E402
from kursplaner.adapters.gui.ui_intents import UiIntent  # noqa: E402


class ScreenShortcutsMixin:
    """Shortcut binding, runtime context and popup tracking of the main window (ScreenBuilder mixin)."""

    def _bind_shortcuts(self):
        """Registriert globale Tastaturkürzel für die Hauptansicht."""
        shortcut_entries = load_shortcut_guide_entries()
        for index, entry in enumerate(shortcut_entries):
            definition = self._register_runtime_shortcut(
                binding_id=f"guide.{entry.intent}.{index}",
                sequence=entry.key_sequence,
                intent=entry.intent,
                modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW),
                allow_when_text_input=False,
            )
            self.app.bind_all(entry.key_sequence, self._build_shortcut_handler(entry, definition=definition))

        self._bind_runtime_shortcut(
            "<F2>",
            lambda event: self._emit_intent(UiIntent.TOOLBAR_RENAME, from_shortcut=True),
            binding_id="global.rename",
            intent=UiIntent.TOOLBAR_RENAME,
            modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW),
        )
        self._bind_runtime_shortcut(
            "<Return>",
            self._on_grid_enter,
            binding_id="grid.enter",
            intent=UiIntent.GRID_ENTER,
            modes=(UI_MODE_PREVIEW,),
        )
        self._bind_runtime_shortcut(
            "<KP_Enter>",
            self._on_grid_enter,
            binding_id="grid.enter.numpad",
            intent=UiIntent.GRID_ENTER,
            modes=(UI_MODE_PREVIEW,),
        )
        self._bind_runtime_shortcut(
            "<Up>",
            self._on_grid_nav_up,
            binding_id="grid.nav.up",
            intent=UiIntent.GRID_NAV_UP,
            modes=(UI_MODE_PREVIEW,),
            add="+",
        )
        self._bind_runtime_shortcut(
            "<Down>",
            self._on_grid_nav_down,
            binding_id="grid.nav.down",
            intent=UiIntent.GRID_NAV_DOWN,
            modes=(UI_MODE_PREVIEW,),
            add="+",
        )
        self._bind_runtime_shortcut(
            "<Left>",
            self._on_detail_left,
            binding_id="detail.left",
            intent=UiIntent.SHORTCUT_DETAIL_LEFT,
            modes=(UI_MODE_PREVIEW,),
        )
        self._bind_runtime_shortcut(
            "<Right>",
            self._on_detail_right,
            binding_id="detail.right",
            intent=UiIntent.SHORTCUT_DETAIL_RIGHT,
            modes=(UI_MODE_PREVIEW,),
        )
        self._bind_runtime_shortcut(
            "<Alt-Left>",
            self._on_detail_left_all,
            binding_id="detail.left.all",
            intent=UiIntent.SHORTCUT_DETAIL_LEFT_ALL,
            modes=(UI_MODE_PREVIEW,),
        )
        self._bind_runtime_shortcut(
            "<Alt-Right>",
            self._on_detail_right_all,
            binding_id="detail.right.all",
            intent=UiIntent.SHORTCUT_DETAIL_RIGHT_ALL,
            modes=(UI_MODE_PREVIEW,),
        )
        for digit in range(10):
            self._bind_runtime_shortcut(
                f"<Key-{digit}>",
                lambda _event, offset=digit: self._emit_intent(UiIntent.SHORTCUT_SELECT_UNIT_BY_OFFSET, offset=offset),
                binding_id=f"detail.select-unit-offset.{digit}",
                intent=UiIntent.SHORTCUT_SELECT_UNIT_BY_OFFSET,
                modes=(UI_MODE_PREVIEW,),
            )
        self._bind_runtime_shortcut(
            "<Home>", self._on_home, binding_id="grid.home", intent=UiIntent.GRID_HOME, modes=(UI_MODE_PREVIEW,)
        )
        self._bind_runtime_shortcut(
            "<End>", self._on_end, binding_id="grid.end", intent=UiIntent.GRID_END, modes=(UI_MODE_PREVIEW,)
        )
        self._bind_runtime_shortcut(
            "<Delete>",
            self._on_grid_delete,
            binding_id="grid.delete",
            intent=UiIntent.GRID_DELETE_CELL,
            modes=(UI_MODE_PREVIEW,),
        )
        self._bind_runtime_shortcut(
            "<BackSpace>",
            self._on_grid_delete,
            binding_id="grid.delete.backspace",
            intent=UiIntent.GRID_DELETE_CELL,
            modes=(UI_MODE_PREVIEW,),
        )
        self._bind_runtime_shortcut(
            "<Control-Return>",
            self._on_ctrl_enter,
            binding_id="grid.commit.ctrl-enter",
            intent=UiIntent.SHORTCUT_COMMIT_EDIT,
            modes=(UI_MODE_PREVIEW, UI_MODE_EDITOR),
            allow_when_text_input=True,
        )
        self._bind_runtime_shortcut(
            "<Control-KP_Enter>",
            self._on_ctrl_enter,
            binding_id="grid.commit.ctrl-enter-numpad",
            intent=UiIntent.SHORTCUT_COMMIT_EDIT,
            modes=(UI_MODE_PREVIEW, UI_MODE_EDITOR),
            allow_when_text_input=True,
        )
        self._bind_runtime_shortcut(
            "<Shift-Return>",
            self._on_find_previous,
            binding_id="search.find-previous",
            intent=UiIntent.SHORTCUT_FIND_PREVIOUS,
            modes=(UI_MODE_PREVIEW, UI_MODE_EDITOR),
            allow_when_text_input=True,
        )
        self._bind_runtime_shortcut(
            "<Control-f>",
            self._on_search_open,
            binding_id="search.open",
            intent=UiIntent.SEARCH_OPEN,
            modes=(UI_MODE_PREVIEW,),
        )
        self._bind_runtime_shortcut(
            "<Escape>",
            self._on_escape,
            binding_id="global.escape",
            intent=UiIntent.SHORTCUT_ESCAPE,
            modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW, UI_MODE_DIALOG),
            allow_when_text_input=True,
        )
        self._bind_runtime_shortcut(
            "<Button-1>",
            self._on_global_click_commit_cell,
            binding_id="global.click-commit",
            intent=UiIntent.GLOBAL_CLICK_COMMIT_CELL,
            modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW),
            add="+",
        )
        self._bind_runtime_shortcut(
            "<Control-Shift-d>",
            lambda _event: self._open_shortcut_runtime_debug_dialog(),
            binding_id="global.runtime-debug",
            intent="debug.shortcut.runtime",
            modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW, UI_MODE_DIALOG),
            allow_when_text_input=True,
        )
        self._bind_runtime_shortcut(
            "<Control-Shift-o>",
            lambda _event: self._toggle_shortcut_runtime_offline(),
            binding_id="global.runtime-offline",
            intent="debug.shortcut.offline",
            modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW, UI_MODE_DIALOG),
            allow_when_text_input=True,
        )
        self._refresh_intent_help_tooltips()

    def _register_runtime_shortcut(
        self,
        *,
        binding_id: str,
        sequence: str,
        intent: str,
        modes: tuple[str, ...],
        allow_when_text_input: bool,
        allow_when_offline: bool = True,
    ) -> KeyBindingDefinition:
        """Register one runtime shortcut definition in the central resolver."""

        # BAUSTELLE: reine Uebergangsloesung bis zur Migration auf ApplicationShortcutBinder
        # (siehe tk_sequence_keyspec.py); Tk-Sequenzen gehoeren nicht mehr in App-Code.
        keyspec = tk_sequence_to_keyspec(sequence)
        if keyspec is None:
            raise ValueError(f"Shortcut {binding_id!r}: {sequence!r} ist keine Tastatursequenz")
        definition = KeyBindingDefinition(
            binding_id=binding_id,
            keys=(keyspec,),
            intent=intent,
            modes=modes,
            allow_when_text_input=allow_when_text_input,
            allow_when_offline=allow_when_offline,
        )
        self._runtime_shortcuts.register(definition)
        return definition

    def _build_runtime_context(self, event: ui.Event[ui.Misc] | None = None) -> KeybindingRuntimeContext:
        """Build runtime context for mode-aware shortcut evaluation."""

        focus_get = getattr(self.app, "focus_get", None)
        focused_widget = getattr(event, "widget", None)
        if focused_widget is None and callable(focus_get):
            focused_widget = focus_get()
        text_input_focused = self._is_editable_widget(focused_widget)
        self._sync_popup_sessions_from_windows()
        dialog_open = self._popup_registry.has_mode_blocking_popup()
        offline = bool(getattr(self.app, "shortcut_debug_offline", False))

        if offline:
            active_mode = UI_MODE_OFFLINE
        elif dialog_open:
            active_mode = UI_MODE_DIALOG
        elif text_input_focused:
            active_mode = UI_MODE_EDITOR
        elif bool(getattr(self.app, "is_detail_view", False)):
            active_mode = UI_MODE_PREVIEW
        else:
            active_mode = UI_MODE_GLOBAL

        return KeybindingRuntimeContext(
            active_mode=active_mode,
            offline=offline,
            text_input_focused=text_input_focused,
            dialog_open=dialog_open,
        )

    def _bind_runtime_shortcut(
        self,
        sequence: str,
        handler,
        *,
        binding_id: str,
        intent: str,
        modes: tuple[str, ...],
        allow_when_text_input: bool = False,
        allow_when_offline: bool = True,
        add: str | None = None,
    ) -> None:
        """Bind one shortcut through runtime evaluator before handler execution."""

        if tk_sequence_to_keyspec(sequence) is None:
            # Mausereignisse (z. B. <Button-1>) sind keine Keybindings und stehen
            # nicht in der Registry; gegatet wird nur auf Texteingabe-Fokus.
            def _wrapped_pointer(event):
                if not allow_when_text_input and self._build_runtime_context(event).text_input_focused:
                    return None
                return handler(event)

            self.app.bind_all(sequence, _wrapped_pointer, add=add)
            return

        definition = self._register_runtime_shortcut(
            binding_id=binding_id,
            sequence=sequence,
            intent=intent,
            modes=modes,
            allow_when_text_input=allow_when_text_input,
            allow_when_offline=allow_when_offline,
        )

        def _wrapped(event):
            context = self._build_runtime_context(event)
            can_execute, _reason = self._runtime_shortcuts.evaluate_runtime(definition, context)
            if not can_execute:
                return None
            return handler(event)

        if add is None:
            self.app.bind_all(sequence, _wrapped)
            return
        self.app.bind_all(sequence, _wrapped, add=add)

    def _build_shortcut_handler(self, entry, *, definition: KeyBindingDefinition | None = None):
        """Erzeugt Event-Handler fuer einen Shortcut-Guide-Eintrag."""

        effective_definition = definition
        if effective_definition is None:
            effective_definition = KeyBindingDefinition(
                binding_id=f"adhoc.{entry.intent}.{entry.key_sequence}",
                keys=(tk_sequence_to_keyspec(entry.key_sequence),),
                intent=entry.intent,
                modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW),
                allow_when_text_input=True,
            )

        def _handler(event):
            context = self._build_runtime_context(event)
            can_execute, _reason = self._runtime_shortcuts.evaluate_runtime(effective_definition, context)
            if not can_execute:
                return None

            if self._has_active_popup() and UI_MODE_DIALOG not in effective_definition.modes:
                return "break"
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

    def _track_popup_window(self, window: ui.Toplevel, *, policy_id: str = "dialog.modal") -> None:
        """Register a popup immediately in the popup policy registry."""

        popup_id = str(window)
        if popup_id in self._tracked_popup_ids:
            return
        self._popup_registry.open_popup(popup_id=popup_id, title=str(window.title() or ""), policy_id=policy_id)
        self._tracked_popup_ids.add(popup_id)

    def _sync_popup_sessions_from_windows(self) -> None:
        """Synchronize tracked popup sessions with currently visible toplevel windows."""

        winfo_children = getattr(self.app, "winfo_children", None)
        if not callable(winfo_children):
            return

        visible_popup_ids: set[str] = set()
        for child in winfo_children():
            if not isinstance(child, ui.Toplevel):
                continue
            try:
                if not int(child.winfo_exists()):
                    continue
                if str(child.state()).lower() == "withdrawn":
                    continue
            except Exception:
                continue

            popup_id = str(child)
            visible_popup_ids.add(popup_id)
            if popup_id in self._tracked_popup_ids:
                continue
            self._popup_registry.open_popup(popup_id=popup_id, title=str(child.title() or ""), policy_id="dialog.modal")
            self._tracked_popup_ids.add(popup_id)

        stale_ids = self._tracked_popup_ids - visible_popup_ids
        for popup_id in tuple(stale_ids):
            self._popup_registry.close_popup(popup_id)
            self._tracked_popup_ids.discard(popup_id)

    def _has_active_popup(self) -> bool:
        """Return whether any modal popup is currently active."""

        self._sync_popup_sessions_from_windows()
        if self._popup_registry.has_mode_blocking_popup():
            return True
        return ScrollablePopupWindow.has_active_popup()
