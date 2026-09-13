from __future__ import annotations

import re
from collections.abc import Callable

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import widgets

from kursplaner.adapters.gui.kompetenzgraph_detail_panel import KompetenzGraphDetailPanel
from kursplaner.adapters.gui.kompetenzgraph_filter_panel import KompetenzGraphFilterPanel
from kursplaner.adapters.gui.kompetenzgraph_sidebar_scroll import KompetenzGraphSidebarScroll
from kursplaner.adapters.gui.kompetenzgraph_text_search_panel import KompetenzGraphTextSearchPanel
from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphFilter
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.usecases.kompetenzgraph_load_body_usecase import LoadKompetenzNodeBodyUseCase


class KompetenzGraphSidebarTabs:
    """Baut die Sidebar als `widgets.Notebook` mit zwei Tabs ("Filter", "Details") auf.

    Ausgelagert aus `kompetenzgraph_dialog.py` als reine UI-Aufbau-Verantwortung, analog
    `kompetenzgraph_canvas_area.py` -- KEINE Auswahl-/Business-Logik: `render_detail_panel(node)`
    AKTUALISIERT NUR den Inhalt, wechselt niemals selbst den aktiven Tab. Welcher Tab sichtbar
    ist, entscheidet ausschließlich der/die Nutzer:in per Klick auf den Tab-Header;
    `kompetenzgraph_dialog.py` entscheidet weiterhin WANN Detaildaten aktualisiert werden, diese
    Klasse kennt nur die UI-Struktur. Kein `notebook.select(...)` von außerhalb dieser Klasse.

    Jeder Tab bekommt eine EIGENE `KompetenzGraphSidebarScroll`-Instanz (Filter-Tab: Filter- +
    Textsuche-Panel; Details-Tab: Detail-Panel) statt eines gemeinsamen Scroll-Containers für die
    ganze Sidebar -- beide Tab-Inhalte können unabhängig lang werden, und jeder Tab behält dadurch
    automatisch seinen eigenen, persistenten Scrollzustand (das jeweilige Canvas bleibt beim
    Tab-Wechsel bestehen, nur `detail_panel.frame`-Inhalt wird bei jedem `render_detail_panel()`
    neu aufgebaut -- der umgebende Scroll-Canvas nicht).

    Bewusst NUR klickgesteuerter Tab-Wechsel -- kein `enable_traversal()` (würde Strg+Tab/
    Strg+Umschalt+Tab beanspruchen, das im Dialog bereits für den View-Mode-Wechsel gebunden ist)
    und keine zusätzliche Pfeiltasten-Bindung (Pfeiltasten sind bereits an die Knoten-Navigation
    auf dem Graph-Canvas gebunden -- ein zweites, fokusabhängiges Pfeiltasten-Verhalten im selben
    Popup wäre unnötige Komplexität ohne echten Mehrwert gegenüber Klick auf zwei sichtbare
    Tab-Header).
    """

    def __init__(
        self,
        parent,
        *,
        snapshot: KompetenzGraphSnapshot,
        initial_filter: KompetenzGraphFilter,
        on_filter_changed: Callable[[KompetenzGraphFilter], None],
        on_text_search_triggered: Callable[[str, re.Pattern[str] | None, bool, bool, bool, bool], None],
        load_body_usecase: LoadKompetenzNodeBodyUseCase | None,
    ):
        self.notebook = widgets.Notebook(parent)

        self._filter_scroll = KompetenzGraphSidebarScroll(self.notebook)
        self.notebook.add(self._filter_scroll.outer, text="Filter")
        filter_container = self._filter_scroll.inner

        self.filter_panel = KompetenzGraphFilterPanel(
            filter_container, snapshot=snapshot, initial_filter=initial_filter, on_change=on_filter_changed
        )
        self.filter_panel.frame.pack(fill="x")

        widgets.Separator(filter_container, orient="horizontal").pack(fill="x", pady=8)

        self.text_search_panel = KompetenzGraphTextSearchPanel(
            filter_container, initial_filter=initial_filter, on_search=on_text_search_triggered
        )
        self.text_search_panel.frame.pack(fill="x")
        self._filter_scroll.bind_mousewheel_to_content()

        self._detail_scroll = KompetenzGraphSidebarScroll(self.notebook)
        self.notebook.add(self._detail_scroll.outer, text="Details")
        self.detail_panel = KompetenzGraphDetailPanel(self._detail_scroll.inner, load_body_usecase=load_body_usecase)
        self.detail_panel.frame.pack(fill="x")
        self._detail_scroll.bind_mousewheel_to_content()

    def render_detail_panel(self, node) -> None:
        """Aktualisiert NUR den Detailinhalt (unabhängig davon, welcher Tab gerade aktiv ist) und
        bindet Mausrad auf die neu erzeugten Widgets -- wechselt bewusst NICHT den Tab (siehe
        Klassendocstring)."""
        self.detail_panel.render(node)
        self._detail_scroll.bind_mousewheel_to_content(self.detail_panel.frame)
