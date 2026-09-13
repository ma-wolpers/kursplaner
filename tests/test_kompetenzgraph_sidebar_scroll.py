"""Tests für `KompetenzGraphSidebarScroll.bind_mousewheel_to_content()` -- insbesondere die
Idempotenz-Garantie, die den früheren Mausrad-Akkumulations-Bug behebt (siehe
`kompetenzgraph_sidebar_scroll.py::bind_mousewheel_to_content()`-Docstring und
`tests/test_kompetenzgraph_sidebar_tabs.py::test_render_detail_panel_does_not_accumulate_mousewheel_bindings`
für den End-zu-End-Nachweis über die Sidebar-Tabs).

Nutzt einen echten `tk.Toplevel` pro Test (Isolation von der session-weiten `tk_root`-Fixture,
siehe `test_kompetenzgraph_canvas_recenter.py`) -- `widget.bind()`-Introspektion ist reines
Tcl/Tk-Verhalten.
"""

from __future__ import annotations

import tkinter as tk

from kursplaner.adapters.gui.kompetenzgraph_sidebar_scroll import KompetenzGraphSidebarScroll


def _binding_count(widget: tk.Widget) -> int:
    """Zählt die Anzahl gebundener `<MouseWheel>`-Handler -- Tk trennt mehrere über `add='+'`
    angehäufte Bindungen durch Zeilenumbrüche im von `bind()` zurückgegebenen Tcl-Skript (bereits
    eine einzelne Bindung endet auf einen Zeilenumbruch, daher werden nur nicht-leere Zeilen gezählt)."""
    bound_script = widget.bind("<MouseWheel>")
    return len([line for line in bound_script.split("\n") if line.strip()])


def test_bind_mousewheel_to_content_binds_each_widget_exactly_once(tk_root):
    toplevel = tk.Toplevel(tk_root)
    scroll = KompetenzGraphSidebarScroll(toplevel)
    child = tk.Frame(scroll.inner)
    child.pack()

    scroll.bind_mousewheel_to_content()
    scroll.bind_mousewheel_to_content()
    scroll.bind_mousewheel_to_content()

    assert _binding_count(scroll.inner) == 1
    assert _binding_count(child) == 1


def test_repeated_bind_on_a_persistent_root_does_not_accumulate(tk_root):
    """Reproduziert exakt den früheren Detailbereich-Bug: ein PERSISTENTES `root`-Widget (nie
    zerstört) mit wechselndem Inhalt (bei jedem Aufruf zerstört und neu erzeugt, wie
    `KompetenzGraphDetailPanel._content_frame`) -- `root` selbst darf nur einmal gebunden werden,
    jeder neue Inhalt jeweils frisch."""
    toplevel = tk.Toplevel(tk_root)
    scroll = KompetenzGraphSidebarScroll(toplevel)
    persistent_root = tk.Frame(scroll.inner)
    persistent_root.pack()

    content_widgets: list[tk.Widget] = []
    for _ in range(3):
        if content_widgets:
            content_widgets[-1].destroy()
        new_content = tk.Label(persistent_root, text="x")
        new_content.pack()
        content_widgets.append(new_content)
        scroll.bind_mousewheel_to_content(root=persistent_root)

    assert _binding_count(persistent_root) == 1
    assert _binding_count(content_widgets[-1]) == 1


def test_newly_added_sibling_widget_still_gets_bound(tk_root):
    """Ein Widget, das erst NACH dem ersten `bind_mousewheel_to_content()`-Aufruf hinzukommt, muss
    bei einem erneuten Aufruf trotzdem gebunden werden -- die Idempotenz gilt pro Widget, nicht
    pauschal pro `root`."""
    toplevel = tk.Toplevel(tk_root)
    scroll = KompetenzGraphSidebarScroll(toplevel)
    scroll.bind_mousewheel_to_content()

    late_child = tk.Frame(scroll.inner)
    late_child.pack()
    scroll.bind_mousewheel_to_content()

    assert _binding_count(late_child) == 1
