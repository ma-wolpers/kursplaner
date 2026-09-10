from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets


class KompetenzGraphSidebarScroll:
    """Eigenständiger, nur-vertikaler Canvas+Scrollbar-Wrapper für die Kompetenzgraph-Sidebar.

    Das Popup selbst öffnet sich mit `scrollable=False`
    (`kompetenzgraph_dialog.py`), da ein zusätzlicher, fensterweiter
    Scroll-Layer um einen bereits selbst scrollbaren Graph-Canvas UND eine
    Sidebar mit mehreren Dropdown-Feldern nur konkurrierende
    Mausrad-Erfassung erzeugen würde -- diese Klasse übernimmt das
    Scrollen ausschließlich für die Sidebar. Mausrad-Bindung sitzt lokal
    auf dem eigenen Canvas (nicht global auf dem Fenster): Tk leitet
    Mausrad-Events an das Widget unter dem Cursor, ein Scroll über dem
    Graphen bleibt dadurch unberührt, ohne dass es einer eigenen
    Kontrolllogik bedarf (dasselbe Muster wie `screen_builder.py`s
    `grid_canvas.bind("<MouseWheel>", ...)`).

    Bewusst NICHT in `bw_gui` extrahiert oder mit dem Popup-internen
    Scroll-Muster (`ScrollablePopupWindow`) zusammengelegt: einziger
    aktueller Anwendungsfall, eine weitere Abstraktionsebene in der
    geteilten Bibliothek wäre hier unnötiger Mehraufwand.
    """

    def __init__(self, parent):
        """Baut den Scroll-Wrapper auf. `self.outer` gehört in den Elterncontainer (z. B. ein
        `Panedwindow`), `self.inner` ist der Frame, in den die eigentlichen Sidebar-Inhalte gebaut werden."""
        self.outer = widgets.Frame(parent)

        self._canvas = ui.Canvas(self.outer, highlightthickness=0)
        scrollbar = widgets.Scrollbar(self.outer, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.inner = widgets.Frame(self._canvas)
        self._inner_window = self._canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)

    def bind_mousewheel_to_content(self, root=None) -> None:
        """Bindet den Mausrad-Handler zusätzlich auf JEDES Kind-Widget unter `root` (Default: `self.inner`).

        Nötig, weil ein Canvas keine Mausrad-Events mehr empfängt, sobald seine Fläche
        komplett von Kind-Widgets bedeckt ist -- Tk liefert das Event an das konkrete
        Widget unter dem Cursor, nicht an dessen Canvas-Vorfahren (dasselbe Muster wie
        `grid_renderer.py`s `widget.bind("<MouseWheel>", self.app._on_grid_mousewheel)`
        pro Zelle).

        Der `root`-Parameter ist wichtig, um Mehrfach-Bindungen zu vermeiden: die
        Filter-Sidebar wird nur EINMAL gebaut (Aufruf ohne `root` direkt nach dem
        initialen Aufbau reicht), der Detailbereich wird dagegen bei JEDER
        Selektionsänderung komplett neu gebaut (`KompetenzGraphDetailPanel.render()`
        zerstört/erzeugt seinen Inhalt neu) -- dort MUSS bei jedem Re-Render erneut
        gebunden werden (siehe `kompetenzgraph_dialog.py::_render_detail_panel()`),
        aber bewusst nur mit `root=self._detail_panel.frame` beschränkt: ein Aufruf
        ohne `root` würde bei jedem Re-Render zusätzlich auch die längst gebundenen,
        unveränderten Filter-Widgets erneut binden (`add="+"` häuft dieselbe Funktion
        dann mehrfach an -- ein einzelner Mausrad-Tick würde nach N Re-Renders um das
        N-fache scrollen).

        `ui.Text`-Widgets werden bewusst ausgenommen: sie haben bereits ein eigenes
        Standard-Mausrad-Scrollverhalten (der Body-Vorschau-Text im Detailbereich hat
        keine eigene Scrollbar) -- ein zusätzlicher, höher priorisierter
        Instanz-Handler würde dieses bei Bedarf unterdrücken und den Body dann nicht
        mehr unabhängig von der restlichen Sidebar scrollbar machen.
        """
        self._bind_recursively(root if root is not None else self.inner)

    def _bind_recursively(self, widget) -> None:
        if not isinstance(widget, ui.Text):
            widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
        for child in widget.winfo_children():
            self._bind_recursively(child)

    def _on_inner_configure(self, _event=None) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        self._canvas.itemconfigure(self._inner_window, width=max(1, int(event.width)))

    def _on_mousewheel(self, event) -> str | None:
        """Scrollt nur, wenn der Sidebar-Inhalt tatsächlich über den sichtbaren Bereich hinausgeht."""
        bbox = self._canvas.bbox("all")
        if not bbox:
            return None
        content_height = bbox[3] - bbox[1]
        if content_height <= self._canvas.winfo_height():
            return None
        step = -1 if event.delta > 0 else 1
        self._canvas.yview_scroll(step, "units")
        return "break"
