"""Tastenkürzel der Sequenzleiter – einzige Tastentabelle des Editors.

Gebunden am Board (`WidgetShortcutBinder` auf `board.key_widget`): diese Kürzel gehen
vor die gleichlautenden des Hauptfensters (Strg+C/V, Strg+Pfeile, Entf, F2), solange
das Board den Fokus hat. ``text=False``: im Ideen-Textfeld behalten Pfeile, Strg+C/V/Z
ihre native Bedeutung. Undo/Redo und Escape bindet die Leiter nicht selbst: sie gehen an
die Hauptfenster-Bindungen (das Intent-Tor der Leiter-Ansicht lässt sie durch, Escape
führt über den `SelectionLayerStack` zurück ins Grid). Übersicht:
`docs/SHORTCUT_KONFLIKTMATRIX.md`.
"""

from __future__ import annotations

from collections.abc import Callable

from bw_gui.contracts import EventResult, KeySpec
from bw_gui.runtime import WidgetShortcutBinder
from bw_gui.widgets.card_board import BoardCell, CardBoard, Cursor, Direction

from kursplaner.adapters.gui.local_keys import DOWN, ENTER, LEFT, RIGHT, UP, KeyRow, bind_keys
from kursplaner.adapters.gui.sequence_ladder_board_mapping import LANE_IDEEN
from kursplaner.adapters.gui.sequence_ladder_controller import SequenceLadderController


def bind_ladder_keys(
    board: CardBoard,
    controller: Callable[[], SequenceLadderController | None],
    move_cursor: Callable[[Cursor], None],
) -> None:
    """Bindet alle Editor-Kürzel an das Board (einmal; *controller* liefert den gerade gezeigten).

    Args:
        board: Das Board (Cursor-Navigation, Ideen-Editor, Tastenziel).
        controller: Liefert den Controller der gezeigten Sequenz (``None``: keine Sequenz).
        move_cursor: Derselbe Cursor-Weg wie bei Klicks (Controller + Spaltenauswahl).
    """

    def act(action: Callable[[SequenceLadderController], object]) -> Callable[[object], EventResult]:
        def _handler(_event: object) -> EventResult:
            current = controller()
            if current is not None:
                action(current)
            return EventResult.HANDLED

        return _handler

    def activate(current: SequenceLadderController) -> None:
        cursor = current.cursor
        if isinstance(cursor, BoardCell):
            if cursor.lane_key == LANE_IDEEN:
                board.edit_text(cursor)
            else:
                current.add(cursor)

    def move(direction: Direction) -> Callable[[object], EventResult]:
        return act(lambda _current: move_cursor(board.move_cursor(direction)))

    rows: list[KeyRow] = [
        (UP, "up", move(Direction.UP)),
        (DOWN, "down", move(Direction.DOWN)),
        (LEFT, "left", move(Direction.LEFT)),
        (RIGHT, "right", move(Direction.RIGHT)),
        (KeySpec.parse("Ctrl+Up"), "step_up", act(lambda c: c.step(True))),
        (KeySpec.parse("Ctrl+Down"), "step_down", act(lambda c: c.step(False))),
        (KeySpec.parse("Ctrl+C"), "copy", act(lambda c: c.copy())),
        (KeySpec.parse("Ctrl+V"), "paste", act(lambda c: c.paste())),
        (KeySpec.parse("Delete"), "delete", act(lambda c: c.delete())),
        (KeySpec.parse("F2"), "rename", act(lambda c: c.rename())),
        (ENTER, "activate", act(activate)),
    ]
    bind_keys(WidgetShortcutBinder(board.key_widget), rows, prefix="sequence_ladder", text=False)
