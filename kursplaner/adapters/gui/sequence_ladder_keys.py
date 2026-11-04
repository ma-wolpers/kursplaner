"""Tastenkürzel des Sequenzleiter-Fensters – einzige Tastentabelle des Editors.

Gebunden im Fensterscope (`WindowShortcutBinder`): diese Kürzel gehen vor die
gleichlautenden des Hauptfensters (Strg+C/V, Strg+Pfeile, Entf, F2) und gelten
nur hier. ``text=False``: im Ideen-Textfeld behalten Pfeile, Strg+C/V/Z ihre
native Bedeutung. Jeder Handler meldet ``HANDLED``, damit keine Taste zum
Hauptfenster durchsickert. Übersicht: `docs/SHORTCUT_KONFLIKTMATRIX.md`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from bw_gui.contracts import EventResult, KeySpec
from bw_gui.runtime import WindowShortcutBinder
from bw_gui.widgets.card_board import BoardCell, CardBoard, Direction

from kursplaner.adapters.gui.local_keys import DOWN, ENTER, LEFT, RIGHT, UP, KeyRow, bind_keys
from kursplaner.adapters.gui.sequence_ladder_board_mapping import LANE_IDEEN
from kursplaner.adapters.gui.sequence_ladder_controller import SequenceLadderController


def _handled(action: Callable[[], object]) -> Callable[[object], EventResult]:
    def _handler(_event: object) -> EventResult:
        action()
        return EventResult.HANDLED

    return _handler


def bind_ladder_keys(
    window: Any,
    board: CardBoard,
    controller: SequenceLadderController,
    *,
    undo: Callable[[], None],
    redo: Callable[[], None],
) -> None:
    """Bindet alle Editor-Kürzel an *window*.

    Args:
        window: Das Leiter-Fenster (Toplevel).
        board: Das Board (Cursor-Navigation, Ideen-Editor).
        controller: Aktionen des Editors.
        undo: Gemeinsames App-Undo.
        redo: Gemeinsames App-Redo.
    """

    def move(direction: Direction) -> None:
        controller.set_cursor(board.move_cursor(direction))

    def activate() -> None:
        cursor = controller.cursor
        if isinstance(cursor, BoardCell):
            if cursor.lane_key == LANE_IDEEN:
                board.edit_text(cursor)
            else:
                controller.add(cursor)

    rows: list[KeyRow] = [
        (UP, "up", _handled(lambda: move(Direction.UP))),
        (DOWN, "down", _handled(lambda: move(Direction.DOWN))),
        (LEFT, "left", _handled(lambda: move(Direction.LEFT))),
        (RIGHT, "right", _handled(lambda: move(Direction.RIGHT))),
        (KeySpec.parse("Ctrl+Up"), "step_up", _handled(lambda: controller.step(True))),
        (KeySpec.parse("Ctrl+Down"), "step_down", _handled(lambda: controller.step(False))),
        (KeySpec.parse("Ctrl+C"), "copy", _handled(controller.copy)),
        (KeySpec.parse("Ctrl+V"), "paste", _handled(controller.paste)),
        (KeySpec.parse("Delete"), "delete", _handled(controller.delete)),
        (KeySpec.parse("F2"), "rename", _handled(controller.rename)),
        (ENTER, "activate", _handled(activate)),
        (KeySpec.parse("Ctrl+Z"), "undo", _handled(undo)),
        (KeySpec.parse("Ctrl+Y"), "redo", _handled(redo)),
    ]
    bind_keys(WindowShortcutBinder(window), rows, prefix="sequence_ladder", text=False)
