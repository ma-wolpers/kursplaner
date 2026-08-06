import ast
import pathlib

GUI_ADAPTERS_DIR = pathlib.Path(__file__).resolve().parent.parent / "kursplaner" / "adapters" / "gui"


def _is_self_app(node: ast.expr) -> bool:
    """Return True for an AST node representing the attribute access ``self.app``."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "app"
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


def _is_toplevel_of_self_app_call(node: ast.AST) -> bool:
    """Return True for an AST node representing a ``ui.Toplevel(self.app, ...)`` call.

    Such a call creates a window parented directly to the main app window, which is
    exactly the shape ``ScreenBuilder._sync_popup_sessions_from_windows`` scans for.
    """
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "Toplevel"
        and bool(node.args)
        and _is_self_app(node.args[0])
    )


def _is_track_popup_window_call(node: ast.AST) -> bool:
    """Return True for an AST node representing any ``<expr>._track_popup_window(...)`` call."""
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "_track_popup_window"


def _untracked_toplevel_functions(source: str, filename: str) -> list[str]:
    """Return "filename:lineno" for functions that build a raw main-window Toplevel
    (``ui.Toplevel(self.app)``) without also registering it via ``_track_popup_window``.

    Any such window is a direct child of the main app window, so it gets picked up by
    ``ScreenBuilder._sync_popup_sessions_from_windows`` and auto-classified as a
    blocking "dialog.modal" popup the moment it becomes visible -- but nothing knows how
    to close it, so every Escape press is silently swallowed while it's open. This is
    exactly what happened with the course-loading dialog (see overview_controller.py).
    """

    tree = ast.parse(source, filename=filename)
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        has_untracked_toplevel = False
        has_tracking_call = False
        first_offending_lineno = None
        for child in ast.walk(node):
            if _is_toplevel_of_self_app_call(child):
                has_untracked_toplevel = True
                if first_offending_lineno is None:
                    first_offending_lineno = child.lineno
            if _is_track_popup_window_call(child):
                has_tracking_call = True
        if has_untracked_toplevel and not has_tracking_call:
            violations.append(f"{filename}:{first_offending_lineno} ({node.name})")

    return violations


def test_every_main_window_toplevel_is_tracked_as_a_popup():
    """Guard against reintroducing the Escape-swallowing bug for any future dialog.

    Scans every module in kursplaner/adapters/gui for functions that create a raw
    ``ui.Toplevel(self.app)`` without a matching ``_track_popup_window(...)`` call.
    """
    violations: list[str] = []
    for path in sorted(GUI_ADAPTERS_DIR.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        violations.extend(_untracked_toplevel_functions(source, path.name))

    assert violations == [], (
        "Found ui.Toplevel(self.app) window(s) created without a matching "
        "_track_popup_window(...) call in the same function. Untracked main-window "
        "popups are silently misclassified as blocking and can never be closed, which "
        "makes Escape stop working while they're open: " + ", ".join(violations)
    )
