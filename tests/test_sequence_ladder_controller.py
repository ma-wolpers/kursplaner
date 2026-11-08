"""Leiter-Controller: jede Aktion eine Operation, Namensabfragen, Sperren (Fake-Dialoge, echte Datei)."""

from __future__ import annotations

import pytest
from bw_gui.widgets.card_board import BoardCell, BoardSlot
from sequence_ladder_test_support import make_ladder_env

from kursplaner.adapters.gui.sequence_ladder_board_mapping import (
    LANE_IDEEN,
    LANE_INHALT,
    LANE_PROZESS,
    card_key,
    rung_key,
)
from kursplaner.adapters.gui.sequence_ladder_controller import SequenceLadderController
from kursplaner.core.domain.sequence_ladder import BlockRef, LadderSide


class FakeDialogs:
    def __init__(self):
        self.answers: list[str | None] = []
        self.asked: list[tuple[str, str]] = []
        self.validators = []
        self.infos: list[str] = []
        self.errors: list[str] = []

    def ask_text(self, title, prompt, *, initial, validate):
        self.asked.append((title, initial))
        self.validators.append(validate)
        return self.answers.pop(0)

    def show_error(self, title, message):
        self.errors.append(message)

    def show_info(self, title, message):
        self.infos.append(message)


@pytest.fixture
def make(tmp_path):
    """Controller über einer synthetischen Sequenz; ohne *kinds* liegen alle Sprossen in der Ablage."""

    def factory(kinds="", *, missing=False, after_write=None, **units):
        env = make_ladder_env(tmp_path, kinds, **units)
        dialogs, renders, writes = FakeDialogs(), [], []
        controller = SequenceLadderController(
            sequence_path=env.sequence_path,
            load=env.load,
            edit=env.edit,
            context=lambda: None if missing else env.context,
            dialogs=dialogs,
            render=lambda view, cursor, banner: renders.append((view, cursor, banner)),
            after_write=after_write or writes.append,
        )
        controller.reload()
        return controller, dialogs, renders, writes, env.history

    return factory


def _key(text, rung=0, side=LadderSide.INHALT):
    return card_key(BlockRef(rung, side, text))


def _inhalt(controller, rung=0):
    return [b.text for b in controller.ladder.rung(rung).inhalt]


def test_plus_asks_for_a_name_and_appends_in_the_cell(make):
    controller, dialogs, _renders, writes, history = make()
    dialogs.answers = ["A", "B"]
    controller.add(BoardCell(rung_key(0), LANE_INHALT))
    controller.add(BoardCell(rung_key(0), LANE_INHALT))
    assert _inhalt(controller) == ["A", "B"] and controller.cursor == _key("B")
    assert len(writes) == 2 and len(history.undo_stack) == 2
    assert dialogs.validators[-1]("a") is not None  # Eindeutigkeit schon im Dialog


def test_copy_paste_inserts_above_with_prefilled_name(make):
    controller, dialogs, *_ = make()
    dialogs.answers = ["A", "B", "A2"]
    controller.add(BoardCell(rung_key(0), LANE_INHALT))
    controller.add(BoardCell(rung_key(0), LANE_INHALT))
    controller.set_cursor(_key("A"))
    controller.copy()
    controller.set_cursor(_key("B"))
    controller.paste()
    assert dialogs.asked[-1] == ("Kopie benennen", "A")
    assert _inhalt(controller) == ["A", "A2", "B"]


def test_paste_without_clipboard_or_target_explains_itself(make):
    controller, dialogs, *_ = make()
    controller.paste()
    controller.clipboard = "A"
    controller.set_cursor(None)
    controller.paste()
    assert len(dialogs.infos) == 2


def test_rename_refuses_network_blocks(make, tmp_path):
    controller, dialogs, *_ = make()
    path = controller.sequence_path
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "## Export", "## Sequenzleiter\n\n- Ablage 1\n  - Prozess: [[Mat-PL-1|Netz]]\n\n## Export"
        ),
        encoding="utf-8",
    )
    controller.reload()
    controller.set_cursor(_key("Netz", side=LadderSide.PROZESS))
    controller.rename()
    assert dialogs.asked == [] and "nicht umbenannt" in dialogs.infos[0]


def test_delete_selects_the_neighbour_or_the_empty_cell(make):
    controller, dialogs, *_ = make()
    dialogs.answers = ["A", "B"]
    controller.add(BoardCell(rung_key(0), LANE_INHALT))
    controller.add(BoardCell(rung_key(0), LANE_INHALT))
    controller.set_cursor(_key("A"))
    controller.delete()
    assert controller.cursor == _key("B")
    controller.delete()
    assert controller.cursor == BoardCell(rung_key(0), LANE_INHALT)


def test_delete_reads_the_ladder_only_once(make):
    """Löschen lud die Leiter früher zweimal (einmal nur, um den Nachbar-Cursor zu zeigen)."""
    controller, dialogs, renders, *_ = make()
    dialogs.answers = ["A", "B"]
    controller.add(BoardCell(rung_key(0), LANE_INHALT))
    controller.add(BoardCell(rung_key(0), LANE_INHALT))
    controller.set_cursor(_key("A"))
    reloads_before = controller._reload_count
    controller.delete()
    assert controller._reload_count == reloads_before + 1
    assert renders[-1][1] == _key("B")


def test_step_and_drop_keep_the_selection(make):
    controller, dialogs, *_ = make()
    dialogs.answers = ["A"]
    controller.add(BoardCell(rung_key(0), LANE_INHALT))
    controller.step(up=True)
    assert _inhalt(controller, 1) == ["A"] and controller.cursor == _key("A", 1)
    controller.drop(_key("A", 1), BoardSlot(rung_key(3), LANE_INHALT, 0))
    assert _inhalt(controller, 3) == ["A"] and controller.cursor == _key("A", 3)


def test_ideas_commit_is_one_step(make):
    controller, _dialogs, _renders, _writes, history = make()
    controller.commit_ideas(BoardCell(rung_key(1), LANE_IDEEN), "Plakat\nPizza")
    assert controller.ladder.rung(1).ideen == ("Plakat", "Pizza")
    assert [e.label for e in history.undo_stack] == ["Ideen bearbeiten"]


def test_missing_sequence_is_read_only_with_banner(make):
    controller, dialogs, renders, writes, _history = make(missing=True)
    controller.add(BoardCell(rung_key(0), LANE_PROZESS))
    assert controller.read_only and writes == [] and dialogs.asked == []
    assert "nicht (mehr) vor" in renders[-1][2]


def test_right_column_names_are_checked_per_rung(make):
    controller, dialogs, *_ = make()
    dialogs.answers = ["P", None, None]
    controller.add(BoardCell(rung_key(0), LANE_PROZESS))
    controller.add(BoardCell(rung_key(1), LANE_PROZESS))
    other_rung = dialogs.validators[-1]
    controller.add(BoardCell(rung_key(0), LANE_PROZESS))
    same_rung = dialogs.validators[-1]
    assert other_rung("p") is None
    assert same_rung("p") is not None


def test_write_refreshes_the_written_files_and_reloads_the_ladder_exactly_once(make):
    reloads = []
    holder = {}

    def after_write(written):
        reloads.append(written)
        holder["controller"].reload()  # wie `_publish_sequence_plans` nach dem gezielten Refresh

    controller, dialogs, renders, *_ = make("U", after_write=after_write)
    holder["controller"] = controller
    dialogs.answers = ["Ziel"]
    before = len(renders)
    controller.add(BoardCell(rung_key(0), LANE_INHALT))
    ((written,),) = reloads
    assert written.parent.name == "Einheiten" and len(renders) == before + 1
    assert controller.cursor == _key("Ziel")


def test_locked_rung_explains_itself_instead_of_asking(make):
    controller, dialogs, _renders, writes, _history = make("UL")
    controller.add(BoardCell(rung_key(1), LANE_INHALT))
    assert dialogs.asked == [] and writes == [] and "Sprosse 2" in dialogs.infos[0]


def test_banner_lists_legacy_duplicates(make):
    _controller, _dialogs, renders, *_ = make("UU", u0={"ziel": "Gleich"}, u1={"ziel": "Gleich"})
    assert "„Gleich“ steht mehrfach (Sprossen 1 und 2)" in renders[-1][2]
