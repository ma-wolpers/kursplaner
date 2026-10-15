"""Kursplaner-Guardrails: Architektur-Checks fuer Hauptfenster-Delegation, Lesson-Index, Docstrings und Undo-Schreibfluss."""

from __future__ import annotations

import ast

from guardrail_config import (  # noqa: E402
    DOCSTRING_REQUIRED_PATHS,
)
from guardrail_support import (  # noqa: E402
    _class_by_name,
    _iter_function_nodes,
    _method_by_name,
    _parse_module,
)


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
