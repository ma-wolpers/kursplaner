"""Sequenzleiter als Oberfläche der Detailansicht: eigene Toolbar plus Hinweisbanner und CardBoard.

Gegenstück zum Grid (Grid-Toolbar + Modusleiste + Editor); `MainViewSwitcher` blendet
`toolbar` und `body` an Stelle der Grid-Teile ein. Reine Anzeige- und Gesten-Verdrahtung:
Board-Gesten gehen an den `SequenceLadderController`, `render` zeigt dessen Ansicht, die
Übersetzung Leiter ↔ Board liegt ausschließlich in `sequence_ladder_board_mapping`.
Die Sequenz-Auswahlliste ist reine Anzeige des Host-Zustands (`set_choices`).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from bw_gui.runtime import combobox_selection, on_combobox_select, widgets
from bw_gui.widgets.card_board import BoardCell, BoardSlot, CardBoard, Cursor

from kursplaner.adapters.gui.help_catalog import SEQUENCE_LADDER_HELP
from kursplaner.adapters.gui.sequence_choices import SequenceChoice
from kursplaner.adapters.gui.sequence_ladder_board_mapping import LANES, board_rows, can_drop
from kursplaner.adapters.gui.sequence_ladder_controller import SequenceLadderController, TextTarget
from kursplaner.adapters.gui.warning_banner import WarningBanner
from kursplaner.core.usecases.load_sequence_ladder_usecase import SequenceLadderView

AddHelp = Callable[..., object]
"""`ScreenBuilder._add_help` (App-Tooltip-Register)."""


class SequenceLadderPanel:
    """Leiter-Oberfläche (eine Instanz, gebaut von `ScreenBuilder`, gesteuert von `SequenceLadderHost`).

    Args:
        toolbar_parent: Platz der Toolbar (derselbe wie die Grid-Toolbar).
        body_parent: Platz des Inhalts (derselbe wie Modusleiste + Grid).
        add_help: Registriert Hover-Hilfen.
        on_import_click: „Aus Kompetenznetz übernehmen…“.
        on_sequence_chosen: Auswahl einer anderen Sequenz in der Liste.
        on_cursor_moved: Cursor des Boards hat sich bewegt (Klick; Controller und Spaltenauswahl folgen dort).
    """

    def __init__(
        self,
        toolbar_parent,
        body_parent,
        *,
        add_help: AddHelp,
        on_import_click: Callable[[], None],
        on_sequence_chosen: Callable[[Path], None],
        on_cursor_moved: Callable[[Cursor], None],
    ) -> None:
        """Baut Toolbar, Banner, Board und Leerhinweis; `attach()` verbindet danach den Controller."""
        self._controller: SequenceLadderController | None = None
        self._on_sequence_chosen, self._on_cursor_moved = on_sequence_chosen, on_cursor_moved
        self._paths: list[Path] = []
        self.toolbar = widgets.Frame(toolbar_parent, style="Toolbar.TFrame")
        self._title = widgets.Label(self.toolbar, text="Sequenzleiter", style="Toolbar.TLabel")
        self._title.pack(side="left", padx=(4, 8))
        self._chooser = widgets.Combobox(self.toolbar, state="readonly", width=48)
        self._chooser.pack(side="left")
        on_combobox_select(self._chooser, lambda _change: self._chosen())
        import_button = widgets.Button(
            self.toolbar, text="Aus Kompetenznetz übernehmen…", command=on_import_click, style="Action.Utility.TButton"
        )
        import_button.pack(side="left", padx=(8, 0))
        add_help(import_button, SEQUENCE_LADDER_HELP["import"])
        add_help(self._title, SEQUENCE_LADDER_HELP["keys"])
        self.body = widgets.Frame(body_parent)
        self._empty = widgets.Label(self.body, text="", justify="left", wraplength=900)
        self.board = CardBoard(
            self.body,
            on_cursor_change=self._on_cursor,
            on_card_activate=self._on_card_activate,
            on_add=lambda cell: self._call(lambda c: c.add(cell)),
            can_drop=self._can_drop,
            on_drop=lambda key, slot: self._call(lambda c: c.drop(key, slot)),
            on_text_commit=lambda cell, text: self._call(lambda c: c.commit_ideas(cell, text)),
            on_row_action=lambda row_key: self._call(lambda c: c.assign_rung(row_key)),
        )
        self.board.frame.pack(fill="both", expand=True)
        self._banner = WarningBanner(self.body, wraplength=1000, before=self.board.frame, pady=(0, 6))
        self.board.set_lanes(LANES)

    def attach(self, controller: SequenceLadderController | None) -> None:
        """Verbindet den Controller der gezeigten Sequenz (``None``: keine Sequenz)."""
        self._controller = controller

    def _call(self, action: Callable[[SequenceLadderController], object]) -> None:
        if self._controller is not None:
            action(self._controller)

    def _on_cursor(self, cursor: Cursor) -> None:
        self._on_cursor_moved(cursor)  # einziger Cursor-Weg: `SequenceLadderHost.move_cursor`

    def _on_card_activate(self, card_key: str) -> None:
        """Doppelklick auf einen Baustein: wie F2 umbenennen."""
        controller = self._controller
        if controller is not None:
            controller.set_cursor(card_key)
            controller.rename()

    def request(
        self, target: TextTarget, *, initial: str, validate: Callable[[str], str | None], done: Callable[[str], None]
    ) -> None:
        """`BlockTextInput`: Namenseingabe direkt im Board statt im Popup.

        Ein Kartenschlüssel öffnet den Inline-Editor über der Karte (umbenennen), ein
        Board-Slot einen Entwurfsplatz für einen neuen Baustein. Enter übernimmt, Escape
        bricht ab; Validierungsfehler stehen unter dem Feld (bw-gui `CardBoard`).
        """
        if isinstance(target, BoardSlot):
            self.board.draft_card(target, on_done=done, initial=initial, validate=validate)
        else:
            self.board.edit_card(target, on_done=done, initial=initial, validate=validate)

    def _can_drop(self, card_key: str, slot: BoardSlot) -> bool:
        controller = self._controller
        return controller is not None and not controller.read_only and can_drop(controller.ladder, card_key, slot)

    def _chosen(self) -> None:
        index = self._chooser.current()
        if 0 <= index < len(self._paths):
            self._on_sequence_chosen(self._paths[index])

    def set_choices(self, choices: Sequence[SequenceChoice], selected: Path | None) -> None:
        """Zeigt die Sequenzen des Kurses; *selected* ist die gezeigte (Host-Zustand)."""
        self._paths = [choice.path for choice in choices]
        self._chooser.configure(values=[choice.label for choice in choices])
        if selected in self._paths:
            combobox_selection.set_index(self._chooser, self._paths.index(selected))
        else:
            self._chooser.set("")

    def render(self, view: SequenceLadderView, cursor: Cursor, banner: str | None) -> None:
        """Zeigt eine Ansicht des Controllers (Board-Zeilen, Cursor, Banner)."""
        self._empty.pack_forget()
        if not self.board.frame.winfo_manager():
            self.board.frame.pack(fill="both", expand=True)
        self.board.set_rows(board_rows(view))
        self.board.set_cursor(cursor)
        self._banner.show(banner)

    def show_empty(self, text: str) -> None:
        """Kein Board: Hinweis statt Leiter (Kurs ohne Sequenz)."""
        self._banner.show(None)
        self.board.frame.pack_forget()
        self._empty.configure(text=text)
        self._empty.pack(fill="x", padx=10, pady=10)

    def focus_board(self, cell: BoardCell | None = None) -> None:
        """Fokus aufs Board (Tastatursteuerung sofort aktiv)."""
        self.board.key_widget.focus_set()
        if cell is not None:
            self.board.set_cursor(cell)
