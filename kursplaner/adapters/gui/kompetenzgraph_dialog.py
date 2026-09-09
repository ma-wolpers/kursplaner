from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets
from bw_gui.theming import theme_canvas

from kursplaner.adapters.gui.kompetenzgraph_canvas_render import KompetenzGraphCanvasRenderer
from kursplaner.adapters.gui.kompetenzgraph_canvas_zoom_pan import KompetenzGraphCanvasZoomPan
from kursplaner.adapters.gui.kompetenzgraph_detail_panel import KompetenzGraphDetailPanel
from kursplaner.adapters.gui.kompetenzgraph_filter_panel import KompetenzGraphFilterPanel
from kursplaner.adapters.gui.kompetenzgraph_ui_state import KompetenzGraphUiState
from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphFilter
from kursplaner.core.domain.kompetenzgraph_layout import compute_layered_layout
from kursplaner.core.domain.kompetenzgraph_view_mode import MODE_FORT_VORAUS, MODE_OBER_TEIL
from kursplaner.core.usecases.kompetenzgraph_load_body_usecase import LoadKompetenzNodeBodyUseCase
from kursplaner.core.usecases.kompetenzgraph_load_usecase import KompetenzGraphLoadResult
from kursplaner.core.usecases.kompetenzgraph_view_usecase import ComputeKompetenzGraphViewUseCase

_VIEW_MODE_LABELS: tuple[tuple[str, str], ...] = (
    (MODE_OBER_TEIL, "Ober-/Teilkompetenzen"),
    (MODE_FORT_VORAUS, "Fort-/Voraussetzung"),
)


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
        super().__init__(
            master,
            title="Kompetenznetz",
            geometry="1180x720",
            minsize=(900, 560),
            theme_key=theme_key,
        )
        self._snapshot = load_result.snapshot
        self._compute_view_usecase = compute_view_usecase
        self._state = KompetenzGraphUiState(filter=initial_filter)

        self._build_ui(load_body_usecase)
        self.apply_theme()
        theme_canvas(self.canvas, theme_key)
        self.bind("<Control-Tab>", self._on_toggle_view_mode_shortcut)
        self._refresh()

    def _requires_close_confirmation(self) -> bool:
        """Reine Leseansicht ohne ungespeicherten Zustand -- schließt immer ohne Rückfrage."""
        return False

    def _build_ui(self, load_body_usecase: LoadKompetenzNodeBodyUseCase | None) -> None:
        root = widgets.Frame(self.content, padding=8)
        root.pack(fill="both", expand=True)

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
        self._build_view_mode_toggle(toolbar)

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

        self._renderer = KompetenzGraphCanvasRenderer(self.canvas, on_node_click=self._on_node_selected)
        self._zoom_pan = KompetenzGraphCanvasZoomPan(self.canvas)

    def _build_view_mode_toggle(self, parent) -> None:
        segment_group = widgets.Frame(parent)
        segment_group.pack(anchor="w")
        self._view_mode_buttons: dict[str, widgets.Button] = {}
        for mode_key, label in _VIEW_MODE_LABELS:
            button = widgets.Button(
                segment_group,
                text=label,
                style="Segmented.TButton",
                command=lambda selected_mode=mode_key: self._on_view_mode_selected(selected_mode),
            )
            button.pack(side="left", padx=(0, 4))
            self._view_mode_buttons[mode_key] = button
        self._refresh_view_mode_buttons()

    def _refresh_view_mode_buttons(self) -> None:
        for mode_key, button in self._view_mode_buttons.items():
            active = mode_key == self._state.view_mode
            button.configure(style="SegmentedActive.TButton" if active else "Segmented.TButton")

    def _on_toggle_view_mode_shortcut(self, _event) -> str:
        other_mode = MODE_FORT_VORAUS if self._state.view_mode == MODE_OBER_TEIL else MODE_OBER_TEIL
        self._on_view_mode_selected(other_mode)
        return "break"

    def _on_view_mode_selected(self, mode_key: str) -> None:
        if mode_key == self._state.view_mode:
            return
        self._state.view_mode = mode_key
        self._refresh_view_mode_buttons()
        self._refresh()

    def _on_filter_changed(self, new_filter: KompetenzGraphFilter) -> None:
        self._state.filter = new_filter
        self._refresh()

    def _on_node_selected(self, node_id: str) -> None:
        self._state.selected_id = node_id
        self._detail_panel.render(self._snapshot.nodes.get(node_id))
        self._redraw_canvas()

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

        self._redraw_canvas()
        selected_node = self._snapshot.nodes.get(self._state.selected_id) if self._state.selected_id else None
        self._detail_panel.render(selected_node)

    def _current_view(self):
        return self._compute_view_usecase.execute(
            self._snapshot, self._state.filter, self._state.view_mode, self._state.focus_id
        )

    def _redraw_canvas(self) -> None:
        """Berechnet Sichtbarkeit + Layout frisch und zeichnet den Canvas neu.

        Wird sowohl bei Filter-/Ansichtswechseln (`_refresh()`) als auch
        bei reinen Selektionsänderungen (`_on_node_selected()`) aufgerufen
        -- Letzteres bewusst ohne erneute Gültigkeitsprüfung, da eine
        Selektionsänderung allein die sichtbare Menge nie verändert.
        """
        view = self._current_view()
        layout = compute_layered_layout(
            self._snapshot, self._state.view_mode, view.visible.all_ids, view.visible_bereich_ids
        )
        self._renderer.render(
            self._snapshot,
            view,
            layout,
            mode_key=self._state.view_mode,
            selected_id=self._state.selected_id,
            focus_id=self._state.focus_id,
        )


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
