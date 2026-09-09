from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets

from kursplaner.core.domain.kompetenzgraph_node import KompetenzNode
from kursplaner.core.domain.kompetenzgraph_types import KcZuordnungEintrag
from kursplaner.core.usecases.kompetenzgraph_load_body_usecase import LoadKompetenzNodeBodyUseCase

_COPIED_FEEDBACK_MS = 1200
_NO_SELECTION_TEXT = "Keine Kompetenz ausgewählt."
_NO_ZITAT_TEXT = "(kein Zitat hinterlegt)"
_NO_BODY_TEXT = "(kein zusätzlicher Inhalt)"


class KompetenzGraphDetailPanel:
    """Zeigt alle Felder des aktuell ausgewählten Kompetenz-Knotens, inkl. Zitate zum Kopieren.

    Der Markdown-Body wird lazy über `LoadKompetenzNodeBodyUseCase`
    nachgeladen -- erst wenn ein Knoten hier tatsächlich angezeigt wird,
    nie für alle Knoten eines Snapshots (siehe Lazy-Body-Entscheidung im
    Implementierungsplan).
    """

    def __init__(self, parent, *, load_body_usecase: LoadKompetenzNodeBodyUseCase | None):
        """Baut den (zunächst leeren) Detailbereich auf.

        Args:
            parent: Übergeordnetes Tk-Widget.
            load_body_usecase: Usecase für das On-Demand-Laden des
                Markdown-Body, oder `None` (z. B. wenn `PyYAML` fehlt --
                dann bleibt der Body-Abschnitt leer statt abzustürzen).
        """
        self._load_body_usecase = load_body_usecase
        self.frame = widgets.Frame(parent, padding=(10, 10))
        self._placeholder = widgets.Label(self.frame, text=_NO_SELECTION_TEXT, foreground="gray")
        self._placeholder.pack(anchor="w")
        self._content_frame: widgets.Frame | None = None

    def render(self, node: KompetenzNode | None) -> None:
        """Baut den Detailbereich für `node` neu auf (oder zeigt den Platzhalter bei `None`)."""
        if self._content_frame is not None:
            self._content_frame.destroy()
            self._content_frame = None

        if node is None:
            self._placeholder.pack(anchor="w")
            return
        self._placeholder.pack_forget()

        content = widgets.Frame(self.frame)
        content.pack(fill="both", expand=True)
        self._content_frame = content

        widgets.Label(content, text=node.title, font=("Segoe UI", 11, "bold"), wraplength=320, justify="left").pack(
            anchor="w", pady=(0, 6)
        )
        self._field_row(content, "ID", node.id)
        self._field_row(content, "Fach", node.source.subject)
        self._field_row(content, "Status", node.status)
        self._field_row(content, "Bereich", node.primarer_bereich_id or "–")
        if node.prozessbereich_ids:
            self._field_row(content, "Prozessbereiche", ", ".join(node.prozessbereich_ids))
        if node.oberkompetenzen_ids:
            self._field_row(content, "Oberkompetenzen", ", ".join(node.oberkompetenzen_ids))
        if node.voraussetzungen_ids:
            self._field_row(content, "Voraussetzungen", ", ".join(node.voraussetzungen_ids))
        if node.offene_voraussetzungen:
            self._field_row(content, "Offene Voraussetzungen", "; ".join(node.offene_voraussetzungen))

        widgets.Separator(content, orient="horizontal").pack(fill="x", pady=8)
        widgets.Label(content, text="Kompetenzzitate (klicken zum Kopieren)", font=("Segoe UI", 9, "bold")).pack(
            anchor="w"
        )
        for entry in node.kc_zuordnung:
            self._render_kc_zuordnung_entry(content, entry)

        widgets.Separator(content, orient="horizontal").pack(fill="x", pady=8)
        widgets.Label(content, text="Inhalt", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        body_widget = ui.Text(content, height=8, wrap="word")
        body_widget.insert("1.0", self._load_body(node))
        body_widget.configure(state="disabled")
        body_widget.pack(fill="both", expand=True, pady=(4, 0))

    def _load_body(self, node: KompetenzNode) -> str:
        if self._load_body_usecase is None:
            return _NO_BODY_TEXT
        body = self._load_body_usecase.execute(node.source.path)
        return body.strip() or _NO_BODY_TEXT

    @staticmethod
    def _field_row(parent, label: str, value: str) -> None:
        row = widgets.Frame(parent)
        row.pack(fill="x", anchor="w")
        widgets.Label(row, text=f"{label}: ", font=("Segoe UI", 9, "bold")).pack(side="left")
        widgets.Label(row, text=value, wraplength=280, justify="left").pack(side="left", fill="x")

    def _render_kc_zuordnung_entry(self, parent, entry: KcZuordnungEintrag) -> None:
        header_parts = [
            part
            for part in (
                entry.bundesland,
                entry.schulform,
                entry.niveau,
                f"Jg. {entry.jahrgang}" if entry.jahrgang is not None else None,
                entry.anforderung,
            )
            if part
        ]
        widgets.Label(parent, text=" · ".join(header_parts), font=("Segoe UI", 8, "italic")).pack(
            anchor="w", pady=(6, 0)
        )
        quote_text = entry.kc_verweis.strip() or _NO_ZITAT_TEXT
        quote_label = widgets.Label(parent, text=quote_text, wraplength=300, justify="left", cursor="hand2")
        quote_label.pack(anchor="w", fill="x")
        if entry.kc_verweis.strip():
            quote_label.bind(
                "<Button-1>",
                lambda _event, text=entry.kc_verweis, label=quote_label: self._copy_to_clipboard(text, label),
            )

    def _copy_to_clipboard(self, text: str, label: widgets.Label) -> None:
        try:
            self.frame.clipboard_clear()
            self.frame.clipboard_append(text)
        except ui.TclError:
            return
        original_text = label.cget("text")
        label.configure(text="✓ In Zwischenablage kopiert")
        label.after(_COPIED_FEEDBACK_MS, lambda: label.configure(text=original_text) if label.winfo_exists() else None)
