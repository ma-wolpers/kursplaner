from __future__ import annotations

from collections.abc import Callable

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import widgets

from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.kompetenzgraph_view import KompetenzGraphView

_TREFFER_LABEL = "Treffer"
_KONTEXT_LABEL = "Kontext"


class KompetenzGraphNodeList:
    """Flache Listenansicht der aktuell sichtbaren Kompetenz-Knoten (Meilenstein-3-Übergang).

    Wird in Meilenstein 4 durch die Canvas-Klickauswahl auf dem Graphen
    ersetzt -- bis dahin die einzige Möglichkeit, einen Knoten
    auszuwählen. Primär- und Kontextknoten (siehe Matchingtiefe) sind
    über die Spalte "Art" unterscheidbar.
    """

    def __init__(self, parent, *, on_select: Callable[[str], None]):
        """Baut den Treeview auf.

        Args:
            parent: Übergeordnetes Tk-Widget.
            on_select: Wird mit der Knoten-ID aufgerufen, sobald eine
                Zeile ausgewählt wird.
        """
        self._on_select = on_select

        self.frame = widgets.Frame(parent)
        columns = ("id", "title", "subject", "kind")
        self.tree = widgets.Treeview(self.frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("id", text="ID")
        self.tree.heading("title", text="Titel")
        self.tree.heading("subject", text="Fach")
        self.tree.heading("kind", text="Art")
        self.tree.column("id", width=70, anchor="w", stretch=False)
        self.tree.column("title", width=320, anchor="w", stretch=True)
        self.tree.column("subject", width=100, anchor="w", stretch=False)
        self.tree.column("kind", width=80, anchor="w", stretch=False)

        y_scroll = widgets.Scrollbar(self.frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=y_scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(0, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    def _on_tree_select(self, _event) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        self._on_select(selection[0])

    def refresh(self, snapshot: KompetenzGraphSnapshot, view: KompetenzGraphView) -> None:
        """Baut die Liste aus der aktuellen `KompetenzGraphView` neu auf (Primär- vor Kontextknoten, je alphabetisch)."""
        self.tree.delete(*self.tree.get_children())
        primary_ids = sorted(view.visible.primary_ids)
        context_ids = sorted(view.visible.context_ids)
        for node_id in (*primary_ids, *context_ids):
            node = snapshot.nodes.get(node_id)
            if node is None:
                continue
            kind = _KONTEXT_LABEL if node_id in view.visible.context_ids else _TREFFER_LABEL
            self.tree.insert("", "end", iid=node_id, values=(node.id, node.title, node.source.subject, kind))

    def select(self, node_id: str | None) -> None:
        """Spiegelt eine extern gesetzte Auswahl (z. B. aus dem Detailbereich) in den Treeview."""
        current_selection = self.tree.selection()
        if node_id is None:
            if current_selection:
                self.tree.selection_remove(*current_selection)
            return
        if node_id in current_selection:
            return
        if self.tree.exists(node_id):
            self.tree.selection_set(node_id)
            self.tree.see(node_id)
