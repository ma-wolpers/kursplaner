"""Kursplaner-Guardrails: gemeinsame Helfer (Repo-/Git-Zugriff, Lesen, AST-Suche, Snippet-Pruefungen)."""

from __future__ import annotations

import ast
import os
import subprocess
from pathlib import Path

from guardrail_config import (  # noqa: E402
    FUTURE_GUI_ENTRY_FILE_NAMES,
    FUTURE_GUI_SEARCH_ROOTS,
    GUI_CONTRACT_SCAN_ROOTS,
    ROOT,
    SCREEN_BUILDER_MIXIN_GLOB,
    SCREEN_BUILDER_PATH,
    UI_BASECLASS_MODULE_ALIASES,
)


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


def _read_screen_builder_family() -> str:
    """Liest `screen_builder.py` samt seiner Mixin-Module als einen Prüftext.

    `ScreenBuilder` ist seit 2026-10-01 auf Mixins (`_screen_key_handlers.py`,
    `_screen_menus.py`, `_screen_shortcuts.py`, `_screen_shortcut_debug.py`,
    `_screen_toolbar.py`) aufgeteilt (Dateigrößen-Regel). Die Verträge gelten
    für die Klasse als Ganzes, deshalb prüfen die ScreenBuilder-Guardrails den
    zusammengesetzten Text statt nur der Einstiegsdatei.

    Returns:
        Inhalt von `screen_builder.py`, gefolgt von allen Mixin-Dateien
        (alphabetisch), jeweils durch eine Leerzeile getrennt.
    """
    parts = [_read(SCREEN_BUILDER_PATH)]
    for mixin in sorted(ROOT.glob(SCREEN_BUILDER_MIXIN_GLOB)):
        parts.append(mixin.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


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


def _is_ci_environment() -> bool:
    """Return whether the check runs in a CI environment."""
    return bool(os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"))
