"""Sequenzleiter-Fenster: nicht-modales Popup mit Kopfzeile, Hinweisbanner und CardBoard.

Reine Anzeige- und Gesten-Verdrahtung: Board-Gesten gehen an den
`SequenceLadderController`, der `render`-Callback zeigt dessen Ansicht. Die
Übersetzung Leiter ↔ Board liegt ausschließlich in
`sequence_ladder_board_mapping`.
"""

from __future__ import annotations

from collections.abc import Callable

from bw_gui.runtime import widgets
from bw_gui.runtime.overlay_stack import OverlayCategory
from bw_gui.widgets import HoverTooltip
from bw_gui.widgets.card_board import BoardCell, BoardSlot, CardBoard, Cursor

from kursplaner.adapters.gui.help_catalog import SEQUENCE_LADDER_HELP
from kursplaner.adapters.gui.popup_window import ScrollablePopupWindow
from kursplaner.adapters.gui.sequence_ladder_board_mapping import LANES, board_rows, can_drop
from kursplaner.adapters.gui.sequence_ladder_controller import SequenceLadderController
from kursplaner.adapters.gui.warning_banner import WarningBanner
from kursplaner.core.usecases.load_sequence_ladder_usecase import SequenceLadderView


class SequenceLadderWindow(ScrollablePopupWindow):
    """Popup des Leiter-Editors (eine Instanz, siehe `SequenceLadderHost`)."""

    def __init__(self, master, *, theme_key: str | None, on_import_click: Callable[[], None]) -> None:
        """Baut Kopf, Banner und Board; `attach()` verbindet danach den Controller.

        Args:
            master: Hauptfenster.
            theme_key: Aktuelles Theme.
            on_import_click: "Aus Kompetenznetz übernehmen…".
        """
        super().__init__(
            master,
            title="Sequenzleiter",
            geometry="1180x760",
            minsize=(820, 480),
            theme_key=theme_key,
            scrollable=False,  # das Board scrollt selbst
            overlay_category=OverlayCategory.NON_MODAL_POPUP,
        )
        self._controller: SequenceLadderController | None = None
        root = widgets.Frame(self.content, padding=8)
        root.pack(fill="both", expand=True)
        head = widgets.Frame(root)
        head.pack(fill="x", pady=(0, 6))
        self._title = widgets.Label(head, text="", font=("TkDefaultFont", 12, "bold"))
        self._title.pack(side="left")
        import_button = widgets.Button(head, text="Aus Kompetenznetz übernehmen…", command=on_import_click)
        import_button.pack(side="right")
        self._tooltips = [
            HoverTooltip(import_button, SEQUENCE_LADDER_HELP["import"]),
            HoverTooltip(self._title, SEQUENCE_LADDER_HELP["keys"]),
        ]
        self.board = CardBoard(
            root,
            on_cursor_change=self._on_cursor,
            on_card_activate=self._on_card_activate,
            on_add=lambda cell: self._call(lambda c: c.add(cell)),
            can_drop=self._can_drop,
            on_drop=lambda key, slot: self._call(lambda c: c.drop(key, slot)),
            on_text_commit=lambda cell, text: self._call(lambda c: c.commit_ideas(cell, text)),
            on_row_action=lambda row_key: self._call(lambda c: c.assign_rung(row_key)),
        )
        self.board.frame.pack(fill="both", expand=True)
        self._banner = WarningBanner(root, wraplength=1000, before=self.board.frame, pady=(0, 6))
        self.board.set_lanes(LANES)
        self.apply_theme()

    def _requires_close_confirmation(self) -> bool:
        """Jede Änderung ist sofort gespeichert – Schließen ohne Rückfrage."""
        return False

    def attach(self, controller: SequenceLadderController) -> None:
        """Verbindet den Controller (nach dem Bau, weil er `render` dieses Fensters braucht)."""
        self._controller = controller

    def _call(self, action: Callable[[SequenceLadderController], object]) -> None:
        if self._controller is not None:
            action(self._controller)

    def _on_cursor(self, cursor: Cursor) -> None:
        self._call(lambda c: c.set_cursor(cursor))

    def _on_card_activate(self, card_key: str) -> None:
        """Doppelklick auf einen Baustein: wie F2 umbenennen."""
        controller = self._controller
        if controller is not None:
            controller.set_cursor(card_key)
            controller.rename()

    def _can_drop(self, card_key: str, slot: BoardSlot) -> bool:
        controller = self._controller
        return controller is not None and not controller.read_only and can_drop(controller.ladder, card_key, slot)

    def render(self, view: SequenceLadderView, cursor: Cursor, banner: str | None) -> None:
        """Zeigt eine Ansicht des Controllers (Board-Zeilen, Cursor, Titel, Banner)."""
        self._title.configure(text=f"Sequenzleiter – {view.oberthema}")
        self.board.set_rows(board_rows(view))
        self.board.set_cursor(cursor)
        self._banner.show(banner)

    def focus_board(self, cell: BoardCell | None = None) -> None:
        """Fokus aufs Board (Tastatursteuerung sofort aktiv)."""
        self.board.key_widget.focus_set()
        if cell is not None:
            self.board.set_cursor(cell)
