"""Tests für `KompetenzGraphSidebarTabs` -- Tab-Struktur und Tab-Wechsel-Verhalten.

Nutzt einen echten Tk-Parent (eigener `tk.Toplevel` pro Test, siehe
`test_kompetenzgraph_canvas_recenter.py` für dasselbe Isolations-Muster gegenüber der
session-weiten `tk_root`-Fixture) -- die Klasse erzeugt echte `bw_gui`-Widgets
(`widgets.Notebook`/`widgets.Frame`); ein nicht existierender ttk-Style fällt in Tk
stillschweigend auf den Default-Style zurück, es wird also kein Theme-Setup benötigt.
"""

from __future__ import annotations

import tkinter as tk

import pytest

from kursplaner.adapters.gui.kompetenzgraph_sidebar_tabs import KompetenzGraphSidebarTabs
from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphFilter
from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from tests.kompetenzgraph_test_support import make_bereich, make_node


def _build_tabs(tk_root) -> KompetenzGraphSidebarTabs:
    node = make_node("A")
    bereich = make_bereich("I-Test")
    snapshot = build_kompetenz_graph_snapshot([node], [bereich])
    toplevel = tk.Toplevel(tk_root)
    return KompetenzGraphSidebarTabs(
        toplevel,
        snapshot=snapshot,
        initial_filter=KompetenzGraphFilter(),
        on_filter_changed=lambda _filter: None,
        on_text_search_triggered=lambda *_args: None,
        load_body_usecase=None,
    )


def test_notebook_has_exactly_filter_and_details_tabs_in_order(tk_root):
    sidebar_tabs = _build_tabs(tk_root)

    tab_labels = [sidebar_tabs.notebook.tab(tab_id, "text") for tab_id in sidebar_tabs.notebook.tabs()]

    assert tab_labels == ["Filter", "Details"]


def test_render_detail_panel_does_not_change_active_tab_when_filter_active(tk_root):
    sidebar_tabs = _build_tabs(tk_root)
    sidebar_tabs.notebook.select(sidebar_tabs._filter_scroll.outer)

    sidebar_tabs.render_detail_panel(None)

    assert sidebar_tabs.notebook.select() == str(sidebar_tabs._filter_scroll.outer)


def test_render_detail_panel_does_not_change_active_tab_when_details_active(tk_root):
    sidebar_tabs = _build_tabs(tk_root)
    sidebar_tabs.notebook.select(sidebar_tabs._detail_scroll.outer)

    sidebar_tabs.render_detail_panel(None)

    assert sidebar_tabs.notebook.select() == str(sidebar_tabs._detail_scroll.outer)


@pytest.mark.xfail(
    reason=(
        "Bekannter, VOR diesem Tab-Feature bereits bestehender Bug in "
        "kompetenzgraph_sidebar_scroll.py::_bind_recursively(): sie bindet bei jedem Aufruf "
        "erneut auch auf das übergebene `root`-Widget selbst (add='+'), nicht nur auf dessen "
        "jeweils neu erzeugte Kind-Widgets. `detail_panel.frame` wird aber nie zerstört/neu "
        "erzeugt (nur sein innerer _content_frame pro Selektion) -- jede Selektion häuft daher "
        "eine weitere Bindung auf `frame` selbst an. Absichtlich als xfail dokumentiert statt "
        "stillschweigend entfernt: wird in einem eigenen, unmittelbar folgenden Fix behoben."
    ),
    strict=True,
)
def test_render_detail_panel_does_not_accumulate_mousewheel_bindings(tk_root):
    """Analog zur bestehenden Absicherung in `kompetenzgraph_dialog.py` -- mehrfaches `render()`
    darf die Mausrad-Bindung nicht kumulativ anhäufen (kein N-facher Scroll-Sprung)."""
    sidebar_tabs = _build_tabs(tk_root)

    sidebar_tabs.render_detail_panel(None)
    sidebar_tabs.render_detail_panel(None)
    sidebar_tabs.render_detail_panel(None)

    bindings = sidebar_tabs.detail_panel.frame.bind("<MouseWheel>")
    # Tk liefert bei mehreren add="+"-Bindungen einen mehrzeiligen Tcl-Callback-Namen-Block --
    # bei korrektem, gezieltem Rebind je Aufruf bleibt das eine einzelne Bindung pro Widget.
    assert bindings.count("\n") <= 1


def test_filter_and_text_search_panels_are_both_inside_the_filter_tab(tk_root):
    sidebar_tabs = _build_tabs(tk_root)

    assert str(sidebar_tabs.filter_panel.frame).startswith(str(sidebar_tabs._filter_scroll.inner))
    assert str(sidebar_tabs.text_search_panel.frame).startswith(str(sidebar_tabs._filter_scroll.inner))
    assert not str(sidebar_tabs.detail_panel.frame).startswith(str(sidebar_tabs._filter_scroll.inner))
