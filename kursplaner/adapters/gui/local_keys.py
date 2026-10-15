"""Dialog- und widgetlokale Tastenkürzel über die bw-gui-Binder (kein ``widget.bind("<Key>")``).

:func:`bind_keys` bindet Zeilen ``(keys, binding_id, handler)`` an einen
``WindowShortcutBinder`` (Toplevel-Tag eines Dialogs) oder ``WidgetShortcutBinder``
(direkt hinter dem Widget, vor seinen Klassenbindungen). Handler bekommen das
bw-gui-``KeyEvent`` und liefern ``EventResult`` (``None`` = Taste läuft weiter, z. B.
zur nativen Klassenbindung).

Toleranzen bei der Migration der früheren Tk-Sequenzen: Tk liess angegebene Modifier
als Mindestmenge gelten (``<Up>`` feuerte auch mit Shift/Strg). bw-gui matcht exakt;
benannte Tasten ohne eigene Shift-Variante tolerieren Shift über die Konstanten hier.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.contracts import KeySpec  # noqa: E402

ENTER = KeySpec.parse("Enter (tolerate: Shift)")
ESCAPE = KeySpec.parse("Escape (tolerate: Shift)")
SPACE = KeySpec.parse("Space (tolerate: Shift)")
UP = KeySpec.parse("Up (tolerate: Shift)")
DOWN = KeySpec.parse("Down (tolerate: Shift)")
LEFT = KeySpec.parse("Left (tolerate: Shift)")
RIGHT = KeySpec.parse("Right (tolerate: Shift)")
CTRL_ENTER = KeySpec.parse("Ctrl+Enter (tolerate: Shift)")

KeyRow = tuple[KeySpec | list[KeySpec], str, Callable[[object], object]]


def bind_keys(binder: Any, rows: Iterable[KeyRow], *, prefix: str, text: bool = True) -> Any:
    """Bindet jede Zeile ``(keys, binding_id, handler)`` an *binder* und gibt ihn zurück.

    Args:
        binder: ``WindowShortcutBinder`` oder ``WidgetShortcutBinder``.
        rows: Tasten (eine Spec oder Alternativen), ID-Suffix, ``handler(KeyEvent)``.
        prefix: Präfix für Binding-ID und Intent (``f"{prefix}.{binding_id}"``).
        text: Auch aktiv, während ein Texteingabe-Widget den Fokus hat (Default wie die
            früheren rohen Bindungen, die nie auf Texteingaben geprüft haben).
    """
    for keys, binding_id, handler in rows:
        full_id = f"{prefix}.{binding_id}"
        binder.bind(keys, handler, binding_id=full_id, intent=full_id, allow_when_text_input=text)
    return binder
