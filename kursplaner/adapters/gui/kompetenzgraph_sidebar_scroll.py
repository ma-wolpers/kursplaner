from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.contracts import EventResult
from bw_gui.runtime import PointerGroup, ui, widgets


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
        self._wheel_group = PointerGroup(self._canvas, "kompetenzgraph-sidebar")
        self._wheel_group.on_wheel(self._on_mousewheel)
        self._wheel_group.add(self._canvas)

    def bind_mousewheel_to_content(self, root=None) -> None:
        """Nimmt jedes Kind-Widget unter `root` (Default: `self.inner`) in die Mausrad-Gruppe der Sidebar auf.

        Nötig, weil ein Canvas keine Mausrad-Events mehr empfängt, sobald seine Fläche
        komplett von Kind-Widgets bedeckt ist -- Tk liefert das Event an das konkrete
        Widget unter dem Cursor, nicht an dessen Canvas-Vorfahren.

        Die Mitgliedschaft in der bw-gui-``PointerGroup`` ist idempotent (ein Bindtag je
        Widget), wiederholte Aufrufe -- der Detailbereich wird bei jeder Selektionsänderung
        neu aufgebaut, das äußere ``detail_panel.frame`` bleibt bestehen -- akkumulieren
        deshalb nichts mehr (früher eine Pfad-Menge gegen mehrfaches ``bind(add="+")``, sonst
        scrollte ein Tick nach N Selektionen N-fach). Neu erzeugte Kind-Widgets werden frisch
        aufgenommen. Zerstörte Widgets verschwinden samt Bindtag.

        `ui.Text`-Widgets werden bewusst ausgenommen: sie haben bereits ein eigenes
        Standard-Mausrad-Scrollverhalten (der Body-Vorschau-Text im Detailbereich hat
        keine eigene Scrollbar) -- eine vorgeschaltete Gruppenbindung würde dieses bei
        Bedarf unterdrücken und den Body dann nicht mehr unabhängig scrollbar machen.
        """
        self._add_recursively(root if root is not None else self.inner)

    def _add_recursively(self, widget) -> None:
        if not isinstance(widget, ui.Text):
            self._wheel_group.add(widget)
        for child in widget.winfo_children():
            self._add_recursively(child)

    def _on_inner_configure(self, _event=None) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        self._canvas.itemconfigure(self._inner_window, width=max(1, int(event.width)))

    def _on_mousewheel(self, event) -> EventResult | None:
        """Scrollt (ganze Rasten) nur, wenn der Sidebar-Inhalt tatsächlich über den sichtbaren Bereich hinausgeht."""
        bbox = self._canvas.bbox("all")
        if not bbox:
            return None
        content_height = bbox[3] - bbox[1]
        if content_height <= self._canvas.winfo_height():
            return None
        if event.whole_steps:
            self._canvas.yview_scroll(event.whole_steps, "units")
        return EventResult.HANDLED
