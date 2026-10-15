"""Kursplaner-Guardrails: GUI-Contract-Checks (Shortcuts und Popup-Gating, Shared-UI, neue GUI-Einstiege, LaufKern-Bruecke)."""

from __future__ import annotations

import ast

from guardrail_config import (  # noqa: E402
    FUTURE_GUI_ENTRY_BASELINES,
    FUTURE_GUI_REQUIRED_SHARED_SNIPPETS,
    GUI_MIGRATION_BACKLOG_PATH,
    LAUFKERN_FALLBACK_SCAN_ROOTS,
    LEGACY_UI_BASECLASS_ALLOWLIST,
    SCREEN_BUILDER_PATH,
    SHARED_PRIMITIVE_CLASS_ALLOWLIST,
    SHARED_PRIMITIVE_CLASS_NAMES,
)
from guardrail_support import (  # noqa: E402
    _contains_direct_tkinter_import,
    _forbid_substring,
    _iter_future_gui_entry_candidates,
    _iter_python_files_under,
    _iter_repo_gui_python_files,
    _local_ui_bases,
    _parse_module,
    _read,
    _read_screen_builder_family,
    _require_substring,
)


def _check_runtime_shortcut_integration(errors: list[str]) -> None:
    """Validate ScreenBuilder runtime shortcut integration and popup gating.

    Popup gating reads the bw-gui overlay stack (``OVERLAY_STACK_CONTRACT.md``) with the
    preset ``blocking(include_menus=True)``; raw main-window tool windows register as
    ``NON_MODAL_POPUP``. Until 2026-10-15 this rule required the former toplevel scan
    (``_sync_popup_sessions_from_windows`` + ``PopupPolicyRegistry``), which the overlay
    stack replaced (characterised in ``tests/test_overlay_gating_tk.py``).
    """

    screen_builder = _read_screen_builder_family()
    for snippet in (
        "from bw_gui.runtime.overlay_stack import OverlayCategory, blocking, register_overlay",
        "self._runtime_shortcuts.evaluate_runtime(",
        "return blocking(self.app, include_menus=True)()",
        "register_overlay(window, OverlayCategory.NON_MODAL_POPUP, toplevel=window)",
    ):
        _require_substring(screen_builder, snippet, "screen_builder.py", errors)
    for stale in ("_sync_popup_sessions_from_windows", "PopupPolicyRegistry()"):
        if stale in screen_builder:
            errors.append(f"screen_builder.py: former popup scan is back ({stale}); use the overlay stack")


def _check_shared_ui_contract_hardening(errors: list[str]) -> None:
    """Erzwingt Shared-UI-Vertraege in ScreenBuilder/MainWindow und HoverTooltip-Bridge.

    Das Menue wird seit KursplanerApp.build_menu() (main_window.py) zentral von
    BwBaseWindow via bw_gui.menu.CustomMenuBar aufgebaut, nicht mehr lokal in
    ScreenBuilder (siehe docs/DEVELOPMENT_LOG.md). Die Pruefung verifiziert
    diese Verdrahtung an ihrem tatsaechlichen Ort statt an der 2026-07-26
    absichtlich entfernten Stelle.
    """

    screen_builder = _read_screen_builder_family()
    for snippet in (
        "from bw_gui.menu import MenuItem as SharedMenuItem",
        "from bw_gui.shortcuts import compose_hover_text_for_intent as compose_shared_hover_text_for_intent",
        "from kursplaner.adapters.gui.hover_tooltip import HoverTooltip",
        "rendered_text = compose_shared_hover_text_for_intent(",
        "tooltip = HoverTooltip(widget, rendered_text)",
    ):
        _require_substring(screen_builder, snippet, "kursplaner/adapters/gui/screen_builder.py", errors)

    for snippet in (
        "except ModuleNotFoundError",
        "def _build_native_menu(",
        "if SharedCustomMenuBar is None",
        "if compose_shared_hover_text_for_intent is None",
        "self._shared_menu_bar = SharedCustomMenuBar(",
    ):
        _forbid_substring(screen_builder, snippet, "kursplaner/adapters/gui/screen_builder.py", errors)

    main_window = _read("kursplaner/adapters/gui/main_window.py")
    for snippet in (
        "from bw_gui.menu import section_spec",
        "class KursplanerApp(BwBaseWindow)",
        "def build_menu(self)",
    ):
        _require_substring(main_window, snippet, "kursplaner/adapters/gui/main_window.py", errors)

    hover_tooltip = _read("kursplaner/adapters/gui/hover_tooltip.py")
    _require_substring(
        hover_tooltip,
        "from bw_gui.widgets.hover_tooltip import HoverTooltip as HoverTooltip",
        "kursplaner/adapters/gui/hover_tooltip.py",
        errors,
    )
    _forbid_substring(
        hover_tooltip,
        "class HoverTooltip",
        "kursplaner/adapters/gui/hover_tooltip.py",
        errors,
    )


def _check_future_gui_entry_contracts(errors: list[str]) -> None:
    """Erzwingt Shared-GUI-Bootstrap fuer neue GUI-Entrypoint-Dateien."""

    for rel_path in _iter_future_gui_entry_candidates():
        if rel_path in FUTURE_GUI_ENTRY_BASELINES:
            continue

        text = _read_screen_builder_family() if rel_path.replace("\\", "/") == SCREEN_BUILDER_PATH else _read(rel_path)
        for snippet in FUTURE_GUI_REQUIRED_SHARED_SNIPPETS:
            _require_substring(text, snippet, rel_path, errors)

        _forbid_substring(text, "import tkinter", rel_path, errors)
        _forbid_substring(text, "from tkinter import", rel_path, errors)


def _check_repo_wide_gui_contracts(errors: list[str]) -> None:
    """Erzwingt repo-weit: keine direkten tkinter-Imports und keine neuen lokalen UI-Basisklassen."""

    for rel_path in _iter_repo_gui_python_files():
        module = _parse_module(rel_path, errors)
        if module is None:
            continue

        if _contains_direct_tkinter_import(module):
            errors.append(
                f"{rel_path}: direct tkinter/ttk import is forbidden; use bw_gui.runtime and shared bw_gui modules"
            )

        for node in ast.walk(module):
            if not isinstance(node, ast.ClassDef):
                continue

            if node.name in SHARED_PRIMITIVE_CLASS_NAMES:
                marker = f"{rel_path}:{node.name}"
                if marker not in SHARED_PRIMITIVE_CLASS_ALLOWLIST:
                    errors.append(
                        f"{rel_path}:{node.lineno} class '{node.name}' redefines a reserved shared primitive; "
                        "import it from bw_gui.runtime/dialogs/widgets instead"
                    )

            bases = _local_ui_bases(node)
            if not bases:
                continue
            marker = f"{rel_path}:{node.name}"
            if marker in LEGACY_UI_BASECLASS_ALLOWLIST:
                continue
            errors.append(
                f"{rel_path}:{node.lineno} class '{node.name}' uses local UI base {bases}; "
                "move reusable widget implementation to bw-gui"
            )


def _check_gui_migration_backlog(errors: list[str]) -> None:
    """Erzwingt explizites Backlog-Tracking fuer aktive GUI-Exemptions."""

    backlog = _read(GUI_MIGRATION_BACKLOG_PATH)
    _require_substring(backlog, "## Active Exemptions", GUI_MIGRATION_BACKLOG_PATH, errors)
    _require_substring(backlog, "remove_by:", GUI_MIGRATION_BACKLOG_PATH, errors)

    for rel_path in sorted(FUTURE_GUI_ENTRY_BASELINES):
        _require_substring(backlog, f"- {rel_path}", GUI_MIGRATION_BACKLOG_PATH, errors)

    for marker in sorted(LEGACY_UI_BASECLASS_ALLOWLIST):
        _require_substring(backlog, f"- {marker}", GUI_MIGRATION_BACKLOG_PATH, errors)


def _check_laufkern_fallback_sunset(errors: list[str]) -> None:
    """Erzwingt Wave-3: es bleiben keine ModuleNotFoundError-Fallbacks mehr uebrig."""

    for rel_path in _iter_python_files_under(LAUFKERN_FALLBACK_SCAN_ROOTS):
        if "except ModuleNotFoundError" in _read(rel_path):
            errors.append(
                f"{rel_path}: ModuleNotFoundError fallback is forbidden in Wave-3; require shared imports without local fallback branches"
            )


def _check_ui_contract_bridge_decommission(errors: list[str]) -> None:
    """Erzwingt Phase-I: ui_contract-Bridges bleiben duenn und re-export-only."""

    required_imports = {
        "bw_libs/ui_contract/keybinding.py": "from bw_gui.contracts.keybinding import",
        "bw_libs/ui_contract/popup.py": "from bw_gui.contracts.popup import",
        "bw_libs/ui_contract/hsm.py": "from bw_gui.contracts.hsm import",
        "bw_libs/ui_contract/laufkern.py": "from bw_gui.laufkern import",
    }
    forbidden_local_markers = {
        "bw_libs/ui_contract/keybinding.py": ("class KeyBindingDefinition", "class KeybindingRegistry"),
        "bw_libs/ui_contract/popup.py": ("class PopupPolicy", "class PopupPolicyRegistry"),
        "bw_libs/ui_contract/hsm.py": ("class HsmContract", "def build_ui_hsm_contract"),
        "bw_libs/ui_contract/laufkern.py": ("class LaufKernManifest", "def aggregate_completion("),
    }

    for rel_path, import_marker in required_imports.items():
        source = _read(rel_path).lstrip("\ufeff")
        _require_substring(source, "ensure_bw_gui_on_path", rel_path, errors)
        _require_substring(source, import_marker, rel_path, errors)
        for forbidden in forbidden_local_markers[rel_path]:
            _forbid_substring(source, forbidden, rel_path, errors)
