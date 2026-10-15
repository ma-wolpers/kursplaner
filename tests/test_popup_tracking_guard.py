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

    Such a call creates a raw window parented directly to the main app window; unlike
    ``ScrollablePopupWindow`` it does not register itself in the bw-gui overlay stack.
    """
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "Toplevel"
        and bool(node.args)
        and _is_self_app(node.args[0])
    )


_REGISTRATION_CALLS = {"_register_non_modal_window", "register_overlay"}


def _is_overlay_registration_call(node: ast.AST) -> bool:
    """Return True for ``<expr>._register_non_modal_window(...)`` or a ``register_overlay(...)`` call."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
    return name in _REGISTRATION_CALLS


def _untracked_toplevel_functions(source: str, filename: str) -> list[str]:
    """Return "filename:lineno" for functions that build a raw main-window Toplevel
    (``ui.Toplevel(self.app)``) without registering it in the overlay stack
    (``_register_non_modal_window`` or ``register_overlay``).

    The overlay stack is the only source the shortcut gating reads
    (``ScreenBuilder._shortcut_dialog_open``). An unregistered window is invisible to it:
    the gating treats it as "nothing open", and the test diagnostic
    ``unregistered_visible_toplevels`` reports it. (Under the former toplevel scan an
    untracked window was auto-classified as blocking and swallowed Escape -- the
    course-loading dialog bug this guard was written for.)
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
            if _is_overlay_registration_call(child):
                has_tracking_call = True
        if has_untracked_toplevel and not has_tracking_call:
            violations.append(f"{filename}:{first_offending_lineno} ({node.name})")

    return violations


def test_every_main_window_toplevel_is_tracked_as_a_popup():
    """Every raw main-window toplevel declares its overlay category.

    Scans every module in kursplaner/adapters/gui for functions that create a raw
    ``ui.Toplevel(self.app)`` without registering it in the overlay stack.
    """
    violations: list[str] = []
    for path in sorted(GUI_ADAPTERS_DIR.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        violations.extend(_untracked_toplevel_functions(source, path.name))

    assert violations == [], (
        "Found ui.Toplevel(self.app) window(s) created without registering them in the "
        "overlay stack (_register_non_modal_window / register_overlay) in the same "
        "function; the shortcut gating cannot see them: " + ", ".join(violations)
    )
