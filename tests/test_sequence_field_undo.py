"""Sequenzziel/Leitkompetenzen-Edits sind ein eigener Undo-Schritt (sonst nähme ein Leiter-Undo sie mit)."""

from __future__ import annotations

from types import SimpleNamespace

from test_sequence_plan_repository import _build_table

from kursplaner.adapters.gui.editor_controller import MainWindowEditorController
from kursplaner.core.domain.topic_sequence_runs import TopicSequenceRun
from kursplaner.core.usecases.command_executor_usecase import CommandExecutorUseCase
from kursplaner.core.usecases.history_usecase import HistoryUseCase
from kursplaner.core.usecases.sync_topic_sequence_plans_usecase import TopicSequencePlanView
from kursplaner.core.usecases.tracked_write_usecase import TrackedWriteUseCase
from kursplaner.core.usecases.update_sequence_goal_field_usecase import UpdateSequenceGoalFieldUseCase
from kursplaner.infrastructure.repositories.command_repository import FileSystemCommandRepository
from kursplaner.infrastructure.repositories.sequence_plan_repository import FileSystemSequencePlanRepository


class _Cell:
    def __init__(self, text: str) -> None:
        self.text = text

    def get(self, _start, _end):
        return self.text


def test_saving_the_sequence_goal_records_one_undoable_entry(tmp_path):
    plan_dir = tmp_path / "M GK test-1 26-2"
    plan_dir.mkdir()
    plan_path = plan_dir / "M GK test-1 26-2.md"
    plan_path.write_text("# Kursplan\n", encoding="utf-8")
    table = _build_table(plan_path)
    repo = FileSystemSequencePlanRepository()
    path = repo.ensure_sequence_document(table=table, sequence_name="Brüche")
    history = HistoryUseCase(CommandExecutorUseCase(command_repo=FileSystemCommandRepository()))
    deps = SimpleNamespace(
        lesson_commands=None,
        save_cell_value=None,
        tracked_write_usecase=TrackedWriteUseCase(history),
        update_sequence_goal_field_usecase=UpdateSequenceGoalFieldUseCase(sequence_plan_repo=repo),
    )
    app = SimpleNamespace(
        gui_dependencies=deps,
        _is_rebuilding_grid=False,
        current_table=table,
        sequence_field_widgets={("Sequenzziel", 0): _Cell("Brüche verstehen")},
        topic_sequence_plans=[TopicSequencePlanView(TopicSequenceRun("Brüche", (0, 1)), path, "", ())],
        pending_cell_text={},
        _collect_day_columns=lambda: None,
        _rebuild_grid=lambda: None,
    )
    before = path.read_text(encoding="utf-8")

    assert MainWindowEditorController(app).save_sequence_field("Sequenzziel", 0) is True

    assert repo.read_goal_and_focus_competencies(path)[0] == "Brüche verstehen"
    assert [entry.label for entry in history.undo_stack] == ["Sequenzziel bearbeiten"]
    history.undo()
    assert path.read_text(encoding="utf-8") == before
