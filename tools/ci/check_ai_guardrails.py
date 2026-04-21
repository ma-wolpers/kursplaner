#!/usr/bin/env python3
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

GUARDRAIL_RELEVANT_PATHS = {
    "AGENTS.md",
    ".github/copilot-instructions.md",
    ".github/workflows/repo-path-guardrails.yml",
    "docs/DEVELOPMENT_LOG.md",
    "docs/ARCHITEKTUR_KERN.md",
    "docs/ARCHITEKTUR_UMSETZUNGSPLAN.md",
    "kursplaner/adapters/gui/main_window.py",
    "kursplaner/core/config/path_store.py",
    "kursplaner/core/usecases/daily_course_log_usecase.py",
    "kursplaner/infrastructure/repositories/lesson_index_repository.py",
    "tools/ci/check_ai_guardrails.py",
    "tools/repo_ci/check_no_absolute_paths.py",
}

DOCSTRING_REQUIRED_PATHS = {
    "tools/ci/check_ai_guardrails.py",
    "kursplaner/adapters/gui/main_window.py",
    "kursplaner/infrastructure/repositories/lesson_index_repository.py",
}


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


def _parse_module(rel_path: str, errors: list[str]) -> ast.Module | None:
    """Parst eine Python-Datei in ein AST-Modul und meldet Parse-Fehler gesammelt."""
    try:
        return ast.parse(_read(rel_path), filename=rel_path)
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
        if norm in normalized_relevant:
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

    has_returned_delegation = False
    for node in ast.walk(method):
        if not isinstance(node, ast.Return):
            continue
        call = node.value
        if not isinstance(call, ast.Call):
            continue
        if not (isinstance(call.func, ast.Attribute) and call.func.attr == "handle_intent"):
            continue

        has_intent_arg = bool(call.args) and isinstance(call.args[0], ast.Name) and call.args[0].id == "intent"
        has_payload_unpack = any(
            keyword.arg is None and isinstance(keyword.value, ast.Name) and keyword.value.id == "payload"
            for keyword in call.keywords
        )
        if has_intent_arg and has_payload_unpack:
            has_returned_delegation = True
            break

    if not has_returned_delegation:
        errors.append(
            "main_window.py: _handle_ui_intent must return a delegated controller.handle_intent(intent, **payload) call"
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
        or path == "docs/ARCHITEKTUR_KERN.md"
        for path in normalized
    )

    if requires_log and not log_touched:
        errors.append(
            "docs/DEVELOPMENT_LOG.md missing update: relevant feature/architecture changes require a same-cycle log entry"
        )


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
    _read("tools/repo_ci/check_no_absolute_paths.py")

    _check_main_window_intent_delegation(errors)
    _check_lesson_index_observability(errors)
    _check_required_docstrings(errors)
    _check_development_log_updated(staged, errors)

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
        "Persistierte Pfadwerte werden **immer relativ zum Workspace-Stamm `7thCloud`** gespeichert.",
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

    print("AI guardrail check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
