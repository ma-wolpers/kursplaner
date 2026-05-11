#!/usr/bin/env python3
from __future__ import annotations

import ast
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

GUARDRAIL_RELEVANT_PATHS = {
    "AGENTS.md",
    ".github/copilot-instructions.md",
    ".github/workflows/repo-path-guardrails.yml",
    "docs/DEVELOPMENT_LOG.md",
    "docs/GUI_MIGRATION_BACKLOG.md",
    "docs/ARCHITEKTUR_KERN.md",
    "docs/ARCHITEKTUR_UMSETZUNGSPLAN.md",
    "kursplaner/adapters/gui/main_window.py",
    "kursplaner/adapters/gui/screen_builder.py",
    "kursplaner/adapters/gui/hover_tooltip.py",
    "kursplaner/core/config/path_store.py",
    "kursplaner/core/usecases/daily_course_log_usecase.py",
    "kursplaner/infrastructure/repositories/lesson_index_repository.py",
    "bw_libs/ui_contract/keybinding.py",
    "bw_libs/ui_contract/popup.py",
    "bw_libs/ui_contract/hsm.py",
    "bw_libs/ui_contract/laufkern.py",
    "bw_libs/app_paths.py",
    "tools/ci/check_ai_guardrails.py",
    "tools/repo_ci/check_no_absolute_paths.py",
}
PROCESS_GUIDANCE_RULES = {
    "feature_commit": "Feature-Aenderungen werden in eigenstaendigen Commits",
    "manual_push": "Push erfolgt manuell",
}
CHANGELOG_RELEVANT_PREFIXES = (
    "kursplaner/adapters/gui/",
    "kursplaner/core/usecases/",
    "bw_libs/",
)
CHANGELOG_CODEV_RELEVANT_PATHS = {
    "AGENTS.md",
    ".github/copilot-instructions.md",
    ".github/pull_request_template.md",
    "tools/ci/check_ai_guardrails.py",
    "docs/GUI_MIGRATION_BACKLOG.md",
    "bw_libs/ui_contract/keybinding.py",
    "bw_libs/ui_contract/popup.py",
    "bw_libs/ui_contract/hsm.py",
    "bw_libs/ui_contract/laufkern.py",
    "bw_libs/app_paths.py",
}
LAUFKERN_BRIDGE_PATH = "bw_libs/ui_contract/laufkern.py"
LAUFKERN_FALLBACK_SCAN_ROOTS = ("kursplaner", "bw_libs")

DOCSTRING_REQUIRED_PATHS = {
    "tools/ci/check_ai_guardrails.py",
    "kursplaner/adapters/gui/main_window.py",
    "kursplaner/infrastructure/repositories/lesson_index_repository.py",
}
FUTURE_GUI_SEARCH_ROOTS = (
    "kursplaner/adapters/gui",
)
FUTURE_GUI_ENTRY_FILE_NAMES = {
    "main_window.py",
    "ui.py",
    "blatt_ui.py",
    "screen_builder.py",
}
FUTURE_GUI_ENTRY_BASELINES: set[str] = set()
FUTURE_GUI_REQUIRED_SHARED_SNIPPETS = (
    "ensure_bw_gui_on_path()",
    "from bw_gui.runtime import",
    "from bw_gui.menu import",
    "open_tabbed_settings_dialog",
    "compose_hover_text",
    "HoverTooltip",
)
GUI_CONTRACT_SCAN_ROOTS = (*FUTURE_GUI_SEARCH_ROOTS, "bw_libs")
UI_BASECLASS_MODULE_ALIASES = {"ui", "widgets", "tui"}
LEGACY_UI_BASECLASS_ALLOWLIST: set[str] = set()
SHARED_PRIMITIVE_CLASS_NAMES = {"TkRootHost", "ScrollablePopupWindow", "WrappedTextField"}
SHARED_PRIMITIVE_CLASS_ALLOWLIST = {
    "kursplaner/adapters/gui/popup_window.py:ScrollablePopupWindow",
}
GUI_MIGRATION_BACKLOG_PATH = "docs/GUI_MIGRATION_BACKLOG.md"


def _repo_root() -> Path:
    """Bestimmt robust das Git-Repository-Root mit Fallback auf `ROOT`."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(ROOT),
            check=True,
            capture_output=True,
            text=True,
        )
        return Path(result.stdout.strip())
    except Exception:
        return ROOT


def _staged_files(repo_root: Path) -> set[str]:
    """Liefert normalisierte, staged Dateipfade relativ zum Repository-Root."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(repo_root),
            check=True,
            capture_output=True,
            text=True,
        )
        lines = [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]
        return set(lines)
    except Exception:
        return set()


def _read(rel_path: str) -> str:
    """Liest eine UTF-8-Datei relativ zum Projekt-Root und validiert Existenz."""
    path = ROOT / rel_path
    if not path.exists():
        raise RuntimeError(f"Missing required file: {rel_path}")
    return path.read_text(encoding="utf-8")


def _require_substring(text: str, needle: str, source: str, errors: list[str]) -> None:
    """Ergänzt einen Fehler, wenn ein verpflichtender Textbaustein fehlt."""
    if needle not in text:
        errors.append(f"{source}: missing required text -> {needle}")


def _forbid_substring(text: str, needle: str, source: str, errors: list[str]) -> None:
    """Ergänzt einen Fehler, wenn ein verbotener Legacy-Fallback gefunden wird."""
    if needle in text:
        errors.append(f"{source}: forbidden fallback text present -> {needle}")


def _is_future_gui_entry_path(rel_path: str) -> bool:
    """Prüft, ob ein Pfad auf einen relevanten GUI-Entrypointnamen zeigt."""
    normalized = rel_path.replace("\\", "/")
    file_name = normalized.rsplit("/", 1)[-1]
    if file_name not in FUTURE_GUI_ENTRY_FILE_NAMES:
        return False
    return any(normalized.startswith(f"{root}/") for root in FUTURE_GUI_SEARCH_ROOTS)


def _iter_future_gui_entry_candidates() -> list[str]:
    """Sammelt alle GUI-Entrypoint-Kandidaten unter den definierten Suchwurzeln."""
    candidates: set[str] = set()
    for rel_root in FUTURE_GUI_SEARCH_ROOTS:
        root_path = ROOT / rel_root
        if not root_path.exists():
            continue
        for file_path in root_path.rglob("*.py"):
            if file_path.name not in FUTURE_GUI_ENTRY_FILE_NAMES:
                continue
            candidates.add(file_path.relative_to(ROOT).as_posix())
    return sorted(candidates)


def _is_repo_gui_python_path(rel_path: str) -> bool:
    """Prüft, ob ein Pfad unter die repo-weiten GUI-Quellpfade fällt."""
    normalized = rel_path.replace("\\", "/")
    if not normalized.endswith(".py"):
        return False
    return any(normalized.startswith(f"{root}/") for root in GUI_CONTRACT_SCAN_ROOTS)


def _iter_repo_gui_python_files() -> list[str]:
    """Sammelt alle Python-Dateien unter den GUI-Scanwurzeln."""
    files: set[str] = set()
    for rel_root in GUI_CONTRACT_SCAN_ROOTS:
        root_path = ROOT / rel_root
        if not root_path.exists():
            continue
        for file_path in root_path.rglob("*.py"):
            files.add(file_path.relative_to(ROOT).as_posix())
    return sorted(files)


def _iter_python_files_under(rel_roots: tuple[str, ...]) -> list[str]:
    """Sammelt Python-Dateien unter den uebergebenen Root-Pfaden relativ zu `ROOT`."""

    files: set[str] = set()
    for rel_root in rel_roots:
        root_path = ROOT / rel_root
        if not root_path.exists():
            continue
        for file_path in root_path.rglob("*.py"):
            files.add(file_path.relative_to(ROOT).as_posix())
    return sorted(files)


def _contains_direct_tkinter_import(module: ast.Module) -> bool:
    """Erkennt direkte tkinter/ttk-Imports auf Modulebene."""
    for node in module.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == "tkinter" or name.startswith("tkinter.") or name == "ttk":
                    return True
        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if (
                module_name == "tkinter"
                or module_name.startswith("tkinter.")
                or module_name == "ttk"
            ):
                return True
    return False


def _local_ui_bases(class_node: ast.ClassDef) -> list[str]:
    """Extrahiert lokale UI-Basisklassen wie ui.Tk/widgets.Frame/tui.Frame."""
    bases: list[str] = []
    for base in class_node.bases:
        if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name):
            if base.value.id in UI_BASECLASS_MODULE_ALIASES:
                bases.append(ast.unparse(base))
    return bases


def _parse_module(rel_path: str, errors: list[str]) -> ast.Module | None:
    """Parst eine Python-Datei in ein AST-Modul und meldet Parse-Fehler gesammelt."""
    try:
        source = _read(rel_path).lstrip("\ufeff")
        return ast.parse(source, filename=rel_path)
    except Exception as exc:
        errors.append(f"{rel_path}: failed to parse Python AST -> {exc}")
        return None


def _iter_function_nodes(module: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Sammelt alle Funktionsknoten (inkl. Methoden) aus einem AST-Modul."""
    return [node for node in ast.walk(module) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _class_by_name(module: ast.Module, class_name: str) -> ast.ClassDef | None:
    """Findet eine Klasse per Name auf Modulebene."""
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None


def _method_by_name(class_node: ast.ClassDef, method_name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Findet eine Methode per Name innerhalb einer Klasse."""
    for node in class_node.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name:
            return node
    return None


def _has_relevant_staged_changes(staged: set[str], repo_root: Path) -> bool:
    """Prüft robust, ob staged Änderungen guardrail-relevante Pfade betreffen."""
    try:
        root_rel_to_repo = str(ROOT.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        root_rel_to_repo = ""

    normalized_relevant: set[str] = set()
    for rel in GUARDRAIL_RELEVANT_PATHS:
        rel_norm = rel.replace("\\", "/")
        normalized_relevant.add(rel_norm)
        if root_rel_to_repo not in {"", "."}:
            normalized_relevant.add(f"{root_rel_to_repo}/{rel_norm}")

    for staged_path in staged:
        norm = staged_path.replace("\\", "/")
        if norm in normalized_relevant or _is_future_gui_entry_path(norm) or _is_repo_gui_python_path(norm):
            return True
    return False


def _check_main_window_intent_delegation(errors: list[str]) -> None:
    """Validiert strukturell die zentrale Intent-Delegation in `main_window.py`."""
    rel_path = "kursplaner/adapters/gui/main_window.py"
    module = _parse_module(rel_path, errors)
    if module is None:
        return

    has_required_import = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "kursplaner.adapters.gui.ui_intent_controller"
        and any(alias.name == "MainWindowUiIntentController" for alias in node.names)
        for node in module.body
    )
    if not has_required_import:
        errors.append(
            "main_window.py: missing required import of MainWindowUiIntentController "
            "from kursplaner.adapters.gui.ui_intent_controller"
        )

    app_class = _class_by_name(module, "KursplanerApp")
    if app_class is None:
        errors.append("main_window.py: missing class KursplanerApp")
        return

    method = _method_by_name(app_class, "_handle_ui_intent")
    if method is None:
        errors.append("main_window.py: missing method _handle_ui_intent")
        return

    has_delegation_call = False
    for node in ast.walk(method):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Attribute) and node.func.attr == "handle_intent"):
            continue

        has_intent_arg = bool(node.args) and isinstance(node.args[0], ast.Name) and node.args[0].id == "intent"
        has_payload_unpack = any(
            keyword.arg is None and isinstance(keyword.value, ast.Name) and keyword.value.id == "payload"
            for keyword in node.keywords
        )
        if has_intent_arg and has_payload_unpack:
            has_delegation_call = True
            break

    if not has_delegation_call:
        errors.append(
            "main_window.py: _handle_ui_intent must delegate to controller.handle_intent(intent, **payload)"
        )


def _check_lesson_index_observability(errors: list[str]) -> None:
    """Validiert strukturell die zentralen Observability-Logs im Lesson-Index-Repo."""
    rel_path = "kursplaner/infrastructure/repositories/lesson_index_repository.py"
    module = _parse_module(rel_path, errors)
    if module is None:
        return

    repo_class = _class_by_name(module, "FileSystemLessonIndexRepository")
    if repo_class is None:
        errors.append("lesson_index_repository.py: missing class FileSystemLessonIndexRepository")
        return

    required_messages = {
        "invalidate_index": "lesson_index.invalidate completed",
        "rebuild_index": "lesson_index.rebuild completed",
    }

    for method_name, required_message in required_messages.items():
        method = _method_by_name(repo_class, method_name)
        if method is None:
            errors.append(f"lesson_index_repository.py: missing method {method_name}")
            continue

        has_required_info_log = False
        for node in ast.walk(method):
            if not isinstance(node, ast.Call):
                continue
            if not (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "info"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "_logger"
                and isinstance(node.func.value.value, ast.Name)
                and node.func.value.value.id == "self"
            ):
                continue

            first_arg = node.args[0] if node.args else None
            if isinstance(first_arg, ast.Constant) and first_arg.value == required_message:
                has_required_info_log = True
                break

        if not has_required_info_log:
            errors.append(
                f"lesson_index_repository.py: {method_name} must emit self._logger.info('{required_message}', ...)"
            )


def _check_required_docstrings(errors: list[str]) -> None:
    """Erzwingt Docstrings für alle Funktionen/Methoden in guardrail-kritischen Python-Dateien."""
    for rel_path in sorted(DOCSTRING_REQUIRED_PATHS):
        module = _parse_module(rel_path, errors)
        if module is None:
            continue

        for node in _iter_function_nodes(module):
            docstring = ast.get_docstring(node)
            if docstring is None or not docstring.strip():
                errors.append(f"{rel_path}:{node.lineno} function '{node.name}' missing docstring")


def _check_undo_writeflow_guardrails(errors: list[str]) -> None:
    """Validiert Undo-relevante Writeflow-Grenzen für Delete/Paste in GUI-Adaptern."""
    ui_module = _parse_module("kursplaner/adapters/gui/ui_intent_controller.py", errors)
    if ui_module is None:
        return

    ui_class = _class_by_name(ui_module, "MainWindowUiIntentController")
    if ui_class is None:
        errors.append("ui_intent_controller.py: missing class MainWindowUiIntentController")
        return

    delete_method = _method_by_name(ui_class, "intent_grid_delete_cell")
    if delete_method is None:
        errors.append("ui_intent_controller.py: missing method intent_grid_delete_cell")
        return

    for node in ast.walk(delete_method):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "apply_value"):
            continue
        owner = func.value
        if not (isinstance(owner, ast.Attribute) and owner.attr == "editor_controller"):
            continue
        app_obj = owner.value
        if not (isinstance(app_obj, ast.Attribute) and app_obj.attr == "app"):
            continue
        if isinstance(app_obj.value, ast.Name) and app_obj.value.id == "self":
            errors.append(
                "ui_intent_controller.py: intent_grid_delete_cell must not call "
                "self.app.editor_controller.apply_value(...) directly"
            )
            break

    action_module = _parse_module("kursplaner/adapters/gui/action_controller.py", errors)
    if action_module is None:
        return

    action_class = _class_by_name(action_module, "MainWindowActionController")
    if action_class is None:
        errors.append("action_controller.py: missing class MainWindowActionController")
        return

    for method_name in ("clear_selected_lesson_content", "paste_copied_lesson"):
        method = _method_by_name(action_class, method_name)
        if method is None:
            errors.append(f"action_controller.py: missing method {method_name}")
            continue

        has_tracked_write = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_run_tracked_write"
            for node in ast.walk(method)
        )
        if not has_tracked_write:
            errors.append(f"action_controller.py: {method_name} must call self._run_tracked_write(...)")

    clear_method = _method_by_name(action_class, "clear_selected_lesson_content")
    if clear_method is not None:
        has_extra_after_from_result = False
        for node in ast.walk(clear_method):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "_run_tracked_write"
            ):
                continue
            if any(keyword.arg == "extra_after_from_result" for keyword in node.keywords):
                has_extra_after_from_result = True
                break

        if not has_extra_after_from_result:
            errors.append(
                "action_controller.py: clear_selected_lesson_content must pass extra_after_from_result to "
                "self._run_tracked_write(...)"
            )

    paste_method = _method_by_name(action_class, "paste_copied_lesson")
    if paste_method is not None:
        has_ub_choice_call = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_ask_paste_ub_copy_mode"
            for node in ast.walk(paste_method)
        )
        if not has_ub_choice_call:
            errors.append(
                "action_controller.py: paste_copied_lesson must call "
                "self._ask_paste_ub_copy_mode(...) for UB copy decisions"
            )


def _check_runtime_shortcut_integration(errors: list[str]) -> None:
    """Validate ScreenBuilder runtime shortcut and popup policy integration."""

    screen_builder = _read("kursplaner/adapters/gui/screen_builder.py")
    _require_substring(
        screen_builder,
        "from bw_libs.ui_contract.popup import POPUP_KIND_MODAL, POPUP_KIND_NON_MODAL, PopupPolicy, PopupPolicyRegistry",
        "screen_builder.py",
        errors,
    )
    _require_substring(
        screen_builder,
        "self._popup_registry = PopupPolicyRegistry()",
        "screen_builder.py",
        errors,
    )
    _require_substring(
        screen_builder,
        "self._runtime_shortcuts.evaluate_runtime(",
        "screen_builder.py",
        errors,
    )
    _require_substring(
        screen_builder,
        "self._sync_popup_sessions_from_windows()",
        "screen_builder.py",
        errors,
    )
    _require_substring(
        screen_builder,
        "self._popup_registry.has_mode_blocking_popup()",
        "screen_builder.py",
        errors,
    )


def _check_shared_ui_contract_hardening(errors: list[str]) -> None:
    """Erzwingt Shared-UI-Vertraege in ScreenBuilder und HoverTooltip-Bridge."""

    screen_builder = _read("kursplaner/adapters/gui/screen_builder.py")
    for snippet in (
        "from bw_gui.menu import CustomMenuBar as SharedCustomMenuBar",
        "from bw_gui.shortcuts import compose_hover_text_for_intent as compose_shared_hover_text_for_intent",
        "from kursplaner.adapters.gui.hover_tooltip import HoverTooltip",
        "self._shared_menu_bar = SharedCustomMenuBar(",
        "rendered_text = compose_shared_hover_text_for_intent(",
        "tooltip = HoverTooltip(widget, rendered_text)",
    ):
        _require_substring(screen_builder, snippet, "kursplaner/adapters/gui/screen_builder.py", errors)

    for snippet in (
        "except ModuleNotFoundError",
        "def _build_native_menu(",
        "if SharedCustomMenuBar is None",
        "if compose_shared_hover_text_for_intent is None",
    ):
        _forbid_substring(screen_builder, snippet, "kursplaner/adapters/gui/screen_builder.py", errors)

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

        text = _read(rel_path)
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


def _check_development_log_updated(staged: set[str], errors: list[str]) -> None:
    """Erzwingt Log-Update bei relevanten Feature-/Architektur-Aenderungen."""
    normalized = {path.replace("\\", "/") for path in staged}
    if not normalized:
        return

    log_touched = "docs/DEVELOPMENT_LOG.md" in normalized

    requires_log = any(
        path.startswith("kursplaner/core/")
        or path.startswith("kursplaner/adapters/")
        or path.startswith("kursplaner/infrastructure/")
        or path.startswith("bw_libs/")
        or path == "docs/ARCHITEKTUR_KERN.md"
        for path in normalized
    )

    if requires_log and not log_touched:
        errors.append(
            "docs/DEVELOPMENT_LOG.md missing update: relevant feature/architecture changes require a same-cycle log entry"
        )


def _check_changelog_updated(staged: set[str], errors: list[str]) -> None:
    """Require changelog updates for user- or co-developer-relevant changes."""
    normalized = {path.replace("\\", "/") for path in staged}
    if not normalized:
        return

    if "CHANGELOG.md" in normalized:
        return

    requires_changelog = any(
        path.startswith(prefix) for path in normalized for prefix in CHANGELOG_RELEVANT_PREFIXES
    ) or any(path in CHANGELOG_CODEV_RELEVANT_PATHS for path in normalized)

    if requires_changelog:
        errors.append(
            "CHANGELOG.md missing update: user- or co-developer-relevant changes require a changelog entry"
        )


def _collect_process_guidance_warnings() -> list[str]:
    """Collect non-blocking warnings for commit/push process guidance drift."""
    warnings: list[str] = []
    sources = {
        "AGENTS.md": _read("AGENTS.md"),
        ".github/copilot-instructions.md": _read(".github/copilot-instructions.md"),
        ".github/pull_request_template.md": _read(".github/pull_request_template.md"),
    }

    for label, needle in PROCESS_GUIDANCE_RULES.items():
        if not any(needle in text for text in sources.values()):
            warnings.append(
                f"process-guidance ({label}) not found in governance docs/templates"
            )
    return warnings


def _is_ci_environment() -> bool:
    """Return whether the check runs in a CI environment."""
    return bool(os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"))


def main() -> int:
    """Führt robuste Guardrail-Checks aus und gibt einen CI-kompatiblen Exitcode zurück."""
    repo_root = _repo_root()
    staged = _staged_files(repo_root)
    if staged and not _has_relevant_staged_changes(staged, repo_root):
        print("AI guardrail check skipped (no guardrail-relevant staged files).")
        return 0

    errors: list[str] = []

    # Guardrail files must exist.
    _read("AGENTS.md")
    _read(".github/copilot-instructions.md")
    _read(".github/workflows/repo-path-guardrails.yml")
    _read(".github/pull_request_template.md")
    _read("tools/repo_ci/check_no_absolute_paths.py")
    _read("bw_libs/ui_contract/keybinding.py")
    _read("bw_libs/ui_contract/popup.py")
    _read("bw_libs/ui_contract/hsm.py")
    _read("bw_libs/ui_contract/laufkern.py")
    _read("bw_libs/app_paths.py")

    _check_main_window_intent_delegation(errors)
    _check_lesson_index_observability(errors)
    _check_required_docstrings(errors)
    _check_development_log_updated(staged, errors)
    _check_changelog_updated(staged, errors)
    _check_undo_writeflow_guardrails(errors)
    _check_runtime_shortcut_integration(errors)
    _check_shared_ui_contract_hardening(errors)
    _check_laufkern_fallback_sunset(errors)
    _check_future_gui_entry_contracts(errors)
    _check_repo_wide_gui_contracts(errors)
    _check_gui_migration_backlog(errors)
    warnings = _collect_process_guidance_warnings()

    # Doku must keep architecture orientation + open-work-only plan wording.
    arch_core = _read("docs/ARCHITEKTUR_KERN.md")
    _require_substring(
        arch_core,
        "GUI-Infrastruktur-Orientierung",
        "ARCHITEKTUR_KERN.md",
        errors,
    )
    _require_substring(
        arch_core,
        "Persistierte Pfadwerte werden **immer relativ zum konfigurierten Workspace-Stamm** gespeichert.",
        "ARCHITEKTUR_KERN.md",
        errors,
    )

    path_store = _read("kursplaner/core/config/path_store.py")
    _require_substring(
        path_store,
        "def serialize_workspace_relative_path(path: Path) -> str:",
        "path_store.py",
        errors,
    )

    daily_log_uc = _read("kursplaner/core/usecases/daily_course_log_usecase.py")
    _require_substring(
        daily_log_uc,
        "serialize_workspace_relative_path(unterricht_dir)",
        "daily_course_log_usecase.py",
        errors,
    )
    _require_substring(
        daily_log_uc,
        "serialize_workspace_relative_path(link_path)",
        "daily_course_log_usecase.py",
        errors,
    )

    lesson_index_repo = _read("kursplaner/infrastructure/repositories/lesson_index_repository.py")
    _require_substring(
        lesson_index_repo,
        "serialize_workspace_relative_path(unterricht_dir)",
        "lesson_index_repository.py",
        errors,
    )
    _require_substring(
        lesson_index_repo,
        "serialize_workspace_relative_path(entry.path)",
        "lesson_index_repository.py",
        errors,
    )

    plan_doc = _read("docs/ARCHITEKTUR_UMSETZUNGSPLAN.md")
    _require_substring(
        plan_doc,
        "nur offene Punkte",
        "ARCHITEKTUR_UMSETZUNGSPLAN.md",
        errors,
    )

    repo_path_workflow = _read(".github/workflows/repo-path-guardrails.yml")
    _require_substring(
        repo_path_workflow,
        "python tools/repo_ci/check_no_absolute_paths.py",
        "repo-path-guardrails.yml",
        errors,
    )

    if errors:
        print("AI guardrail check failed:")
        for item in errors:
            print(f" - {item}")
        return 2

    if warnings and not _is_ci_environment():
        print("AI guardrail process warnings (non-blocking):")
        for item in warnings:
            print(f" - {item}")

    print("AI guardrail check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
