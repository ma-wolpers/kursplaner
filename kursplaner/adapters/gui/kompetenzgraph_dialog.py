from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import widgets

from kursplaner.adapters.gui.kompetenzgraph_detail_panel import KompetenzGraphDetailPanel
from kursplaner.adapters.gui.kompetenzgraph_filter_panel import KompetenzGraphFilterPanel
from kursplaner.adapters.gui.kompetenzgraph_node_list import KompetenzGraphNodeList
from kursplaner.adapters.gui.kompetenzgraph_ui_state import KompetenzGraphUiState
from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphFilter
from kursplaner.core.usecases.kompetenzgraph_load_body_usecase import LoadKompetenzNodeBodyUseCase
from kursplaner.core.usecases.kompetenzgraph_load_usecase import KompetenzGraphLoadResult
from kursplaner.core.usecases.kompetenzgraph_view_usecase import ComputeKompetenzGraphViewUseCase


class KompetenzGraphDialog(ScrollablePopupWindow):
    """Nicht-modales Popup für das Kompetenznetz -- Grundgerüst ohne Graph-Canvas (Meilenstein 3).

    Nicht-modal (kein `grab_set()`/`wait_window()`), damit ein kopiertes
    `kc_verweis`-Zitat direkt ins Stundenziel-Feld des weiterhin
    bedienbaren Hauptfensters eingefügt werden kann. Jede Filter-/
    Auswahländerung ruft ausschließlich `ComputeKompetenzGraphViewUseCase`
    auf -- keine eigene Verdrahtung von Filter+Kontext+Fokus in dieser
    Klasse (siehe Implementierungsplan, Abschnitt zur zentralen
    Sichtbarkeits-Pipeline).

    Die rechte Spalte zeigt in diesem Meilenstein noch eine einfache
    Liste statt des Graphen -- Meilenstein 4 ersetzt sie durch den
    tkinter-Canvas-Renderer, ohne die Sidebar-Struktur zu verändern.
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
        widgets.Label(
            right,
            text="Graph-Ansicht folgt in Meilenstein 4 -- vorerst Listenansicht:",
            foreground="gray",
        ).pack(anchor="w", pady=(0, 4))
        self._node_list = KompetenzGraphNodeList(right, on_select=self._on_node_selected)
        self._node_list.frame.pack(fill="both", expand=True)

    def _on_filter_changed(self, new_filter: KompetenzGraphFilter) -> None:
        self._state.filter = new_filter
        self._refresh()

    def _on_node_selected(self, node_id: str) -> None:
        self._state.selected_id = node_id
        self._detail_panel.render(self._snapshot.nodes.get(node_id))

    def _refresh(self) -> None:
        """Berechnet die aktuelle Sichtbarkeits-Ansicht neu und synchronisiert Liste + Detailbereich.

        Wendet die Selektions-Gültigkeitsregel an: verschwindet der
        ausgewählte/fokussierte Knoten durch einen Filterwechsel aus der
        sichtbaren Menge, wird die jeweilige Auswahl automatisch
        aufgehoben (keine Geisterauswahl auf unsichtbare Knoten).
        """
        view = self._compute_view_usecase.execute(
            self._snapshot, self._state.filter, self._state.view_mode, self._state.focus_id
        )

        if self._state.selected_id is not None and self._state.selected_id not in view.visible.all_ids:
            self._state.selected_id = None
        if self._state.focus_id is not None and self._state.focus_id not in view.visible.all_ids:
            self._state.focus_id = None

        self._node_list.refresh(self._snapshot, view)
        self._node_list.select(self._state.selected_id)
        selected_node = self._snapshot.nodes.get(self._state.selected_id) if self._state.selected_id else None
        self._detail_panel.render(selected_node)


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
