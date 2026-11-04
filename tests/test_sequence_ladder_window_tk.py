"""Leiter-Fenster an einem echten Tk-Root (außerhalb des Bildschirms): Tasten → Aktionen, keine Lecks.

Nur synthetische Daten in tmp_path. Tasten über `bw_gui.testing.keys.press_key` ohne OS-Fokus.
"""

from __future__ import annotations

import pytest
from bw_gui.testing.keys import press_key
from test_sequence_ladder_controller import FakeDialogs
from test_sequence_plan_repository import _build_table

from kursplaner.adapters.gui.sequence_ladder_controller import SequenceLadderController
from kursplaner.adapters.gui.sequence_ladder_keys import bind_ladder_keys
from kursplaner.adapters.gui.sequence_ladder_window import SequenceLadderWindow
from kursplaner.core.domain.topic_sequence_runs import TopicSequenceRun
from kursplaner.core.usecases.command_executor_usecase import CommandExecutorUseCase
from kursplaner.core.usecases.edit_sequence_ladder_usecase import EditSequenceLadderUseCase
from kursplaner.core.usecases.history_usecase import HistoryUseCase
from kursplaner.core.usecases.load_sequence_ladder_usecase import LoadSequenceLadderUseCase
from kursplaner.core.usecases.tracked_write_usecase import TrackedWriteUseCase
from kursplaner.infrastructure.repositories.command_repository import FileSystemCommandRepository
from kursplaner.infrastructure.repositories.sequence_plan_repository import FileSystemSequencePlanRepository

CTRL = 0x4


@pytest.fixture
def ladder(root, tmp_path):
    plan_dir = tmp_path / "M GK test-1 26-2"
    plan_dir.mkdir()
    plan_path = plan_dir / "M GK test-1 26-2.md"
    plan_path.write_text("# Kursplan\n", encoding="utf-8")
    repo = FileSystemSequencePlanRepository()
    path = repo.ensure_sequence_document(table=_build_table(plan_path), sequence_name="Brüche")
    history = HistoryUseCase(CommandExecutorUseCase(command_repo=FileSystemCommandRepository()))
    window = SequenceLadderWindow(root, theme_key=None, on_import_click=lambda: None)
    window.geometry("1000x600+3000+3000")
    dialogs, undone = FakeDialogs(), []
    controller = SequenceLadderController(
        sequence_path=path,
        load=LoadSequenceLadderUseCase(repo),
        edit=EditSequenceLadderUseCase(repo, TrackedWriteUseCase(history)),
        context=lambda: ("Brüche", [TopicSequenceRun("Brüche", (0, 1))], []),
        dialogs=dialogs,
        render=window.render,
        after_write=lambda: None,
    )
    window.attach(controller)
    bind_ladder_keys(window, window.board, controller, undo=lambda: undone.append("undo"), redo=lambda: None)
    controller.reload()
    window.update()
    window.board.flush_now()
    yield window, controller, dialogs, undone
    window.destroy()


def test_enter_on_empty_cell_adds_and_ctrl_up_moves_across_rungs(ladder):
    window, controller, dialogs, _undone = ladder
    key_widget = window.board.key_widget
    dialogs.answers = ["A"]
    assert press_key(key_widget, "Return") is True
    assert [b.text for b in controller.ladder.rung(0).inhalt] == ["A"]
    assert press_key(key_widget, "Up", state=CTRL) is True
    assert [b.text for b in controller.ladder.rung(1).inhalt] == ["A"]
    window.board.flush_now()
    assert window.board.cursor == "A"


def test_delete_and_undo_keys_are_consumed_by_the_ladder(ladder):
    window, controller, dialogs, undone = ladder
    key_widget = window.board.key_widget
    dialogs.answers = ["A"]
    press_key(key_widget, "Return")
    assert press_key(key_widget, "Delete") is True
    assert controller.ladder.is_empty
    assert press_key(key_widget, "z", char="\x1a", state=CTRL) is True
    assert undone == ["undo"]


def test_arrow_keys_move_the_cursor_and_are_handled_even_at_the_edge(ladder):
    window, controller, _dialogs, _undone = ladder
    key_widget = window.board.key_widget
    assert press_key(key_widget, "Right") is True
    assert controller.cursor == window.board.cursor
    for _ in range(5):
        assert press_key(key_widget, "Down") is True


def test_banner_appears_for_a_malformed_ladder(ladder):
    window, controller, _dialogs, _undone = ladder
    path = controller.sequence_path
    path.write_text(
        path.read_text(encoding="utf-8").replace("## Export", "## Sequenzleiter\n\nkaputt\n\n## Export"),
        encoding="utf-8",
    )
    controller.reload()
    window.update()
    assert window._banner.winfo_manager() == "pack"
    assert "Zeile 1" in window._banner.cget("text")
    assert controller.read_only
