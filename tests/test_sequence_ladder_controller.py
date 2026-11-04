"""Leiter-Controller: jede Aktion eine Operation, Namensabfragen, Sperren (Fake-Dialoge, echte Datei)."""

from __future__ import annotations

import pytest
from bw_gui.widgets.card_board import BoardCell, BoardSlot
from test_sequence_plan_repository import _build_table

from kursplaner.adapters.gui.sequence_ladder_board_mapping import (
    LANE_IDEEN,
    LANE_INHALT,
    LANE_PROZESS,
    card_key,
    rung_key,
)
from kursplaner.adapters.gui.sequence_ladder_controller import SequenceLadderController
from kursplaner.core.domain.sequence_ladder import BlockRef, LadderSide
from kursplaner.core.domain.topic_sequence_runs import TopicSequenceRun
from kursplaner.core.usecases.command_executor_usecase import CommandExecutorUseCase
from kursplaner.core.usecases.edit_sequence_ladder_usecase import EditSequenceLadderUseCase
from kursplaner.core.usecases.history_usecase import HistoryUseCase
from kursplaner.core.usecases.load_sequence_ladder_usecase import LoadSequenceLadderUseCase
from kursplaner.core.usecases.tracked_write_usecase import TrackedWriteUseCase
from kursplaner.infrastructure.repositories.command_repository import FileSystemCommandRepository
from kursplaner.infrastructure.repositories.sequence_plan_repository import FileSystemSequencePlanRepository


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
    plan_dir = tmp_path / "M GK test-1 26-2"
    plan_dir.mkdir()
    plan_path = plan_dir / "M GK test-1 26-2.md"
    plan_path.write_text("# Kursplan\n", encoding="utf-8")
    repo = FileSystemSequencePlanRepository()
    path = repo.ensure_sequence_document(table=_build_table(plan_path), sequence_name="Brüche")
    history = HistoryUseCase(CommandExecutorUseCase(command_repo=FileSystemCommandRepository()))

    def factory(context=("Brüche", [TopicSequenceRun("Brüche", (0, 1))], [])):
        dialogs, renders, writes = FakeDialogs(), [], []
        controller = SequenceLadderController(
            sequence_path=path,
            load=LoadSequenceLadderUseCase(repo),
            edit=EditSequenceLadderUseCase(repo, TrackedWriteUseCase(history)),
            context=lambda: context,
            dialogs=dialogs,
            render=lambda view, cursor, banner: renders.append((view, cursor, banner)),
            after_write=lambda: writes.append(1),
        )
        controller.reload()
        return controller, dialogs, renders, writes, history

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
            "## Export", "## Sequenzleiter\n\n- Sprosse 1\n  - Prozess: [[Mat-PL-1|Netz]]\n\n## Export"
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
    controller, dialogs, renders, writes, _history = make(context=None)
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
