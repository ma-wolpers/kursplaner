from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import widgets
from bw_gui.theming import theme_canvas

from kursplaner.adapters.gui.help_catalog import KOMPETENZGRAPH_HELP
from kursplaner.adapters.gui.kompetenzgraph_canvas_area import KompetenzGraphCanvasArea
from kursplaner.adapters.gui.kompetenzgraph_canvas_colors import assign_bereich_hues
from kursplaner.adapters.gui.kompetenzgraph_canvas_recenter import (
    recenter_on_selection,
    recenter_on_selection_if_offscreen,
)
from kursplaner.adapters.gui.kompetenzgraph_canvas_selection import (
    handle_double_click_or_enter,
    select_nearest_in_direction,
)
from kursplaner.adapters.gui.kompetenzgraph_detail_panel import KompetenzGraphDetailPanel
from kursplaner.adapters.gui.kompetenzgraph_diagnostics_banner import KompetenzGraphDiagnosticsBanner
from kursplaner.adapters.gui.kompetenzgraph_filter_panel import KompetenzGraphFilterPanel
from kursplaner.adapters.gui.kompetenzgraph_sidebar_scroll import KompetenzGraphSidebarScroll
from kursplaner.adapters.gui.kompetenzgraph_ui_state import KompetenzGraphUiState
from kursplaner.adapters.gui.kompetenzgraph_view_mode_toggle import KompetenzGraphViewModeToggle
from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphFilter
from kursplaner.core.domain.kompetenzgraph_layout import compute_layered_layout
from kursplaner.core.domain.kompetenzgraph_node import KompetenzNode
from kursplaner.core.domain.kompetenzgraph_view_mode import MODE_ABHAENGIGKEITEN
from kursplaner.core.usecases.kompetenzgraph_load_body_usecase import LoadKompetenzNodeBodyUseCase
from kursplaner.core.usecases.kompetenzgraph_load_usecase import KompetenzGraphLoadResult
from kursplaner.core.usecases.kompetenzgraph_view_usecase import ComputeKompetenzGraphViewUseCase


class KompetenzGraphDialog(ScrollablePopupWindow):
    """Nicht-modales Popup für das Kompetenznetz mit interaktivem Canvas-Graphen.

    Nicht-modal (kein `grab_set()`/`wait_window()`), damit ein kopiertes
    `kc_verweis`-Zitat direkt ins Stundenziel-Feld des weiterhin
    bedienbaren Hauptfensters eingefügt werden kann. Jede Filter-/
    Ansichts-/Auswahländerung ruft ausschließlich `ComputeKompetenzGraphViewUseCase`
    (Filter/Matchingtiefe/Fokus) bzw. die reine Domain-Funktion
    `compute_layered_layout()` (Layout) auf -- keine eigene Verdrahtung
    dieser Schritte in dieser Klasse.

    View-Mode-Umschaltung als Segmented-Control (`Segmented.TButton`/
    `SegmentedActive.TButton`, dieselben von Blattwerk und Kursplaner
    gemeinsam genutzten `bw_gui`-Styles) sowie per Tastenkürzel
    (`Strg+Tab`, lokal auf dieses Popup beschränkt).
    """

    def __init__(
        self,
        master,
        *,
        load_result: KompetenzGraphLoadResult,
        initial_filter: KompetenzGraphFilter,
        compute_view_usecase: ComputeKompetenzGraphViewUseCase,
        load_body_usecase: LoadKompetenzNodeBodyUseCase | None,
        theme_key: str | None = None,
    ):
        # scrollable=False: Graph-Canvas und Sidebar (KompetenzGraphSidebarScroll) verwalten ihr
        # eigenes Scrollen bereits selbst -- ein zusaetzlicher, fensterweiter Scroll-Layer wuerde
        # nur konkurrierende Mausrad-Erfassung erzeugen (siehe kompetenzgraph_sidebar_scroll.py).
        super().__init__(
            master,
            title="Kompetenznetz",
            geometry="1180x720",
            minsize=(900, 560),
            theme_key=theme_key,
            scrollable=False,
        )
        self._snapshot = load_result.snapshot
        self._compute_view_usecase = compute_view_usecase
        self._state = KompetenzGraphUiState(
            filter=initial_filter, bereich_hues=assign_bereich_hues(self._snapshot.bereiche.keys())
        )
        self._last_view = None
        self._last_layout = None

        self._build_ui(load_result, load_body_usecase)
        self.apply_theme()
        theme_canvas(self.canvas, theme_key)
        self.bind("<Control-Tab>", self._on_toggle_view_mode_shortcut)
        self._refresh()
        self.canvas.focus_set()

    def _requires_close_confirmation(self) -> bool:
        """Reine Leseansicht ohne ungespeicherten Zustand -- schließt immer ohne Rückfrage."""
        return False

    def _build_ui(
        self, load_result: KompetenzGraphLoadResult, load_body_usecase: LoadKompetenzNodeBodyUseCase | None
    ) -> None:
        root = widgets.Frame(self.content, padding=8)
        root.pack(fill="both", expand=True)

        self._diagnostics_banner = KompetenzGraphDiagnosticsBanner(root)
        self._diagnostics_banner.update(load_result)

        paned = widgets.Panedwindow(root, orient="horizontal")
        paned.pack(fill="both", expand=True)

        self._sidebar_scroll = KompetenzGraphSidebarScroll(paned)
        paned.add(self._sidebar_scroll.outer, weight=0)
        sidebar = self._sidebar_scroll.inner

        self._filter_panel = KompetenzGraphFilterPanel(
            sidebar, snapshot=self._snapshot, initial_filter=self._state.filter, on_change=self._on_filter_changed
        )
        self._filter_panel.frame.pack(fill="x")

        widgets.Separator(sidebar, orient="horizontal").pack(fill="x", pady=8)

        self._detail_panel = KompetenzGraphDetailPanel(sidebar, load_body_usecase=load_body_usecase)
        self._detail_panel.frame.pack(fill="x")
        self._sidebar_scroll.bind_mousewheel_to_content()

        right = widgets.Frame(paned)
        paned.add(right, weight=1)

        toolbar = widgets.Frame(right)
        toolbar.pack(fill="x", pady=(0, 6))
        self._view_mode_toggle = KompetenzGraphViewModeToggle(
            toolbar,
            initial_mode=self._state.view_mode,
            on_mode_selected=self._on_view_mode_selected,
            mode_help_text={MODE_ABHAENGIGKEITEN: KOMPETENZGRAPH_HELP["abhaengigkeiten_ansicht"]},
        )

        canvas_area = KompetenzGraphCanvasArea(
            right,
            on_node_click=self._on_node_selected,
            on_node_double_click=self._on_node_double_clicked,
            on_arrow_direction=self._on_arrow_direction,
            on_enter_key=self._on_enter_key,
        )
        self.canvas = canvas_area.canvas
        self._renderer = canvas_area.renderer
        self._zoom_pan = canvas_area.zoom_pan

    def _on_toggle_view_mode_shortcut(self, _event) -> str:
        """Strg+Tab: zyklisch zur nächsten Ansicht (`next_mode()`, mit Wraparound über alle `VIEW_MODES`)."""
        self._on_view_mode_selected(self._view_mode_toggle.next_mode())
        return "break"

    def _on_view_mode_selected(self, mode_key: str) -> None:
        if mode_key == self._state.view_mode:
            return
        self._state.view_mode = mode_key
        self._view_mode_toggle.refresh(mode_key)
        self._refresh()
        self.canvas.focus_set()

    def _on_filter_changed(self, new_filter: KompetenzGraphFilter) -> None:
        self._state.filter = new_filter
        self._refresh()

    def _render_detail_panel(self, node) -> None:
        """Rendert den Detailbereich und bindet Sidebar-Mausrad-Weiterleitung auf die neu erzeugten Widgets.

        Der Detailbereich wird bei jeder Selektionsänderung komplett neu gebaut -- die neuen
        Widgets brauchen daher jedes Mal frische Bindungen, gezielt nur für `self._detail_panel.frame`
        (siehe `KompetenzGraphSidebarScroll.bind_mousewheel_to_content()`-Docstring)."""
        self._detail_panel.render(node)
        self._sidebar_scroll.bind_mousewheel_to_content(self._detail_panel.frame)

    def _on_node_selected(self, node_id: str) -> None:
        """Einfacher Klick: ändert nur die Selektion, niemals die sichtbare Menge -- siehe `_reapply_selection()`."""
        self._state.selected_id = node_id
        self._render_detail_panel(self._snapshot.nodes.get(node_id))
        self._reapply_selection()
        self.canvas.focus_set()

    def _selected_node(self) -> KompetenzNode | None:
        """Liefert den aktuell ausgewählten `KompetenzNode` (`None` ohne Auswahl) -- bündelt den
        `str | None`-Guard vor `MappingProxyType.get()`, statt ihn an mehreren Aufrufstellen zu wiederholen."""
        return self._snapshot.nodes.get(self._state.selected_id) if self._state.selected_id is not None else None

    def _on_node_double_clicked(self, node_id: str) -> None:
        """Doppelklick: togglet den Fokus (siehe `kompetenzgraph_canvas_selection.py`) -- kann die sichtbare Menge ändern."""
        handle_double_click_or_enter(self._state, node_id)
        self._render_detail_panel(self._selected_node())
        self._recompute_and_redraw()
        recenter_on_selection(self.canvas, self._state.selected_id)
        self.canvas.focus_set()

    def _on_enter_key(self, _event) -> str:
        """Enter: togglet den Fokus wie ein Doppelklick, zentriert die Ansicht danach auf den Knoten
        (das Layout wird beim Fokus-Toggle neu berechnet, der Knoten kann woanders landen)."""
        handle_double_click_or_enter(self._state)
        self._recompute_and_redraw()
        recenter_on_selection(self.canvas, self._state.selected_id)
        return "break"

    def _on_arrow_direction(self, direction: tuple[float, float]) -> None:
        """Pfeiltaste: bewegt die Auswahl mittels `select_nearest_in_direction()`, zentriert bei Erfolg.

        Ändert nur die Selektion, daher `_reapply_selection()` statt Neuberechnung.
        """
        if self._last_layout is None or self._last_view is None:
            return
        if not select_nearest_in_direction(self._state, self._last_layout, self._last_view, direction):
            return
        self._render_detail_panel(self._selected_node())
        self._reapply_selection()
        recenter_on_selection(self.canvas, self._state.selected_id)

    def _refresh(self) -> None:
        """Berechnet die Sichtbarkeits-Ansicht neu und synchronisiert Canvas + Detailbereich.

        Gültigkeitsregel: verschwindet die Auswahl/der Fokus durch einen Filter-/Ansichtswechsel
        aus der sichtbaren Menge, wird sie automatisch aufgehoben (keine Geisterauswahl)."""
        view = self._current_view()
        if self._state.selected_id is not None and self._state.selected_id not in view.visible.all_ids:
            self._state.selected_id = None
        if self._state.focus_id is not None and self._state.focus_id not in view.visible.all_ids:
            self._state.focus_id = None

        self._recompute_and_redraw()
        self._render_detail_panel(self._selected_node())

    def _current_view(self):
        return self._compute_view_usecase.execute(
            self._snapshot, self._state.filter, self._state.view_mode, self._state.focus_id
        )

    def _recompute_and_redraw(self) -> None:
        """Berechnet Sichtbarkeit + Layout frisch und zeichnet den Canvas neu.

        Genutzt bei Filter-/Ansichtswechseln und Fokus-Toggles -- diese
        KÖNNEN die sichtbare Menge verändern. Für reine Selektions-
        änderungen (Klick, Pfeiltasten) siehe `_reapply_selection()`.
        """
        view = self._current_view()
        layout = compute_layered_layout(
            self._snapshot, self._state.view_mode, view.visible.all_ids, view.visible_bereich_ids
        )
        self._last_view = view
        self._last_layout = layout
        self._render_canvas(view, layout)
        recenter_on_selection_if_offscreen(self.canvas, self._state.selected_id)

    def _reapply_selection(self) -> None:
        """Zeichnet mit der zwischengespeicherten Momentaufnahme neu, OHNE Sichtbarkeit/Layout neu zu berechnen.

        Eine reine Selektionsänderung verändert nachweislich weder die sichtbare Menge noch das
        Layout -- das Überspringen der teuren Pipeline ist der zentrale Fix gegen die frühere
        Navigations-Ruckelei. Fällt defensiv auf `_recompute_and_redraw()` zurück, falls noch
        keine Momentaufnahme existiert (praktisch unerreichbar, `_refresh()` läuft im Konstruktor)."""
        if self._last_view is None or self._last_layout is None:
            self._recompute_and_redraw()
            return
        self._render_canvas(self._last_view, self._last_layout)

    def _render_canvas(self, view, layout) -> None:
        """Gemeinsamer Render-Aufruf für `_recompute_and_redraw()` und `_reapply_selection()`."""
        self._renderer.render(
            self._snapshot,
            view,
            layout,
            mode_key=self._state.view_mode,
            selected_id=self._state.selected_id,
            focus_id=self._state.focus_id,
            bereich_hues=self._state.bereich_hues,
        )
        self._zoom_pan.reapply_zoom()
        self._zoom_pan.reapply_label_visibility()


def ask_kompetenz_graph(
    master,
    *,
    load_result: KompetenzGraphLoadResult,
    initial_filter: KompetenzGraphFilter,
    compute_view_usecase: ComputeKompetenzGraphViewUseCase,
    load_body_usecase: LoadKompetenzNodeBodyUseCase | None,
    theme_key: str | None = None,
) -> KompetenzGraphDialog:
    """Öffnet das Kompetenzgraph-Popup nicht-modal und gibt die Dialog-Instanz zurück.

    Anders als die übrigen `ask_xyz(...)`-Konvenienzfunktionen im Projekt
    blockiert dies NICHT über `wait_window()` und liefert kein
    `Result`-Objekt -- das Popup ist ein dauerhaft geöffnetes,
    nicht-modales Fenster, kein einmaliger Eingabedialog. Der Aufrufer
    (`action_controller.py::show_kompetenzgraph`) registriert die
    zurückgegebene Instanz explizit als `dialog.non_blocking`.
    """
    return KompetenzGraphDialog(
        master,
        load_result=load_result,
        initial_filter=initial_filter,
        compute_view_usecase=compute_view_usecase,
        load_body_usecase=load_body_usecase,
        theme_key=theme_key,
    )
