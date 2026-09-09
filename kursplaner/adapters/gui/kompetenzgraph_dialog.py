from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets
from bw_gui.theming import theme_canvas

from kursplaner.adapters.gui.kompetenzgraph_canvas_arrow_nav import KompetenzGraphCanvasArrowNav
from kursplaner.adapters.gui.kompetenzgraph_canvas_colors import assign_bereich_hues
from kursplaner.adapters.gui.kompetenzgraph_canvas_recenter import recenter_on_node
from kursplaner.adapters.gui.kompetenzgraph_canvas_render import NODE_TAG_PREFIX, KompetenzGraphCanvasRenderer
from kursplaner.adapters.gui.kompetenzgraph_canvas_selection import handle_double_click_or_enter
from kursplaner.adapters.gui.kompetenzgraph_canvas_tooltip import KompetenzGraphCanvasTooltip
from kursplaner.adapters.gui.kompetenzgraph_canvas_zoom_pan import KompetenzGraphCanvasZoomPan
from kursplaner.adapters.gui.kompetenzgraph_detail_panel import KompetenzGraphDetailPanel
from kursplaner.adapters.gui.kompetenzgraph_diagnostics_banner import KompetenzGraphDiagnosticsBanner
from kursplaner.adapters.gui.kompetenzgraph_filter_panel import KompetenzGraphFilterPanel
from kursplaner.adapters.gui.kompetenzgraph_ui_state import KompetenzGraphUiState
from kursplaner.adapters.gui.kompetenzgraph_view_mode_toggle import KompetenzGraphViewModeToggle
from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.core.domain.kompetenzgraph_arrow_navigation import find_nearest_node_in_direction
from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphFilter
from kursplaner.core.domain.kompetenzgraph_layout import compute_layered_layout
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
        super().__init__(master, title="Kompetenznetz", geometry="1180x720", minsize=(900, 560), theme_key=theme_key)
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

        sidebar = widgets.Frame(paned)
        paned.add(sidebar, weight=0)

        self._filter_panel = KompetenzGraphFilterPanel(
            sidebar, snapshot=self._snapshot, initial_filter=self._state.filter, on_change=self._on_filter_changed
        )
        self._filter_panel.frame.pack(fill="x")

        widgets.Separator(sidebar, orient="horizontal").pack(fill="x", pady=8)

        self._detail_panel = KompetenzGraphDetailPanel(sidebar, load_body_usecase=load_body_usecase)
        self._detail_panel.frame.pack(fill="both", expand=True)

        right = widgets.Frame(paned)
        paned.add(right, weight=1)

        toolbar = widgets.Frame(right)
        toolbar.pack(fill="x", pady=(0, 6))
        self._view_mode_toggle = KompetenzGraphViewModeToggle(
            toolbar, initial_mode=self._state.view_mode, on_mode_selected=self._on_view_mode_selected
        )

        canvas_container = widgets.Frame(right)
        canvas_container.pack(fill="both", expand=True)
        self.canvas = ui.Canvas(canvas_container, highlightthickness=0)
        h_scroll = widgets.Scrollbar(canvas_container, orient="horizontal", command=self.canvas.xview)
        v_scroll = widgets.Scrollbar(canvas_container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        canvas_container.rowconfigure(0, weight=1)
        canvas_container.columnconfigure(0, weight=1)

        self._tooltip = KompetenzGraphCanvasTooltip(self.canvas)
        self._renderer = KompetenzGraphCanvasRenderer(
            self.canvas,
            on_node_click=self._on_node_selected,
            on_node_double_click=self._on_node_double_clicked,
            tooltip=self._tooltip,
        )
        self._zoom_pan = KompetenzGraphCanvasZoomPan(self.canvas)
        self._arrow_nav = KompetenzGraphCanvasArrowNav(self.canvas, on_direction=self._on_arrow_direction)
        self.canvas.bind("<Return>", self._on_enter_key)
        self.canvas.bind("<KP_Enter>", self._on_enter_key)

    def _on_toggle_view_mode_shortcut(self, _event) -> str:
        self._on_view_mode_selected(self._view_mode_toggle.other_mode())
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

    def _on_node_selected(self, node_id: str) -> None:
        """Einfacher Klick: ändert nur die Selektion, niemals die sichtbare Menge -- siehe `_reapply_selection()`."""
        self._state.selected_id = node_id
        self._detail_panel.render(self._snapshot.nodes.get(node_id))
        self._reapply_selection()
        self.canvas.focus_set()

    def _on_node_double_clicked(self, node_id: str) -> None:
        """Doppelklick: togglet den Fokus (siehe `kompetenzgraph_canvas_selection.py`) -- kann die sichtbare Menge ändern."""
        handle_double_click_or_enter(self._state, node_id)
        self._detail_panel.render(self._snapshot.nodes.get(self._state.selected_id))
        self._recompute_and_redraw()
        self.canvas.focus_set()

    def _on_enter_key(self, _event) -> str:
        """Enter auf der aktuellen Auswahl: togglet den Fokus, äquivalent zu einem Doppelklick darauf."""
        handle_double_click_or_enter(self._state)
        self._recompute_and_redraw()
        return "break"

    def _on_arrow_direction(self, direction: tuple[float, float]) -> None:
        """Bewegt die Auswahl auf den nächstgelegenen sichtbaren Knoten im 60°-Kegel Richtung `direction`.

        Kandidaten kommen aus der zwischengespeicherten Momentaufnahme
        (`self._last_layout`/`self._last_view`) -- Bereich-Hubs sind nie
        Kandidaten. Ändert nur die Selektion, daher `_reapply_selection()`
        statt Neuberechnung; zentriert die Ansicht auf den neuen Knoten.
        """
        if self._state.selected_id is None or self._last_layout is None or self._last_view is None:
            return
        current_position = self._last_layout.positions.get(self._state.selected_id)
        if current_position is None:
            return

        candidates = {
            node_id: (position.x, position.y)
            for node_id, position in self._last_layout.positions.items()
            if node_id != self._state.selected_id and node_id in self._last_view.visible.all_ids
        }
        nearest_id = find_nearest_node_in_direction((current_position.x, current_position.y), candidates, direction)
        if nearest_id is None:
            return

        self._state.selected_id = nearest_id
        self._detail_panel.render(self._snapshot.nodes.get(nearest_id))
        self._reapply_selection()
        recenter_on_node(self.canvas, f"{NODE_TAG_PREFIX}{nearest_id}")

    def _refresh(self) -> None:
        """Berechnet die aktuelle Sichtbarkeits-Ansicht neu, wendet die Selektions-Gültigkeitsregel an
        und synchronisiert Canvas + Detailbereich.

        Gültigkeitsregel: verschwindet der ausgewählte/fokussierte Knoten
        durch einen Filter-/Ansichtswechsel aus der sichtbaren Menge, wird
        die jeweilige Auswahl automatisch aufgehoben (keine Geisterauswahl
        auf unsichtbare Knoten).
        """
        view = self._current_view()
        if self._state.selected_id is not None and self._state.selected_id not in view.visible.all_ids:
            self._state.selected_id = None
        if self._state.focus_id is not None and self._state.focus_id not in view.visible.all_ids:
            self._state.focus_id = None

        self._recompute_and_redraw()
        selected_node = self._snapshot.nodes.get(self._state.selected_id) if self._state.selected_id else None
        self._detail_panel.render(selected_node)

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

    def _reapply_selection(self) -> None:
        """Zeichnet mit der zwischengespeicherten Momentaufnahme neu, OHNE Sichtbarkeit/Layout neu zu berechnen.

        Eine reine Selektionsänderung (Klick, Pfeiltasten-Navigation)
        verändert nachweislich weder die sichtbare Menge noch das Layout
        -- das Überspringen der teuren Sichtbarkeits-Pipeline UND des
        vollen Sugiyama-Layouts (inkl. Crossing-Minimierung) ist der
        zentrale Fix gegen die zuvor bei jedem Klick/Pfeiltastendruck
        spürbare Navigations-Ruckelei. Fällt defensiv auf
        `_recompute_and_redraw()` zurück, falls noch keine Momentaufnahme
        existiert (im laufenden Betrieb unerreichbar, da `_refresh()`
        bereits im Konstruktor läuft).
        """
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
