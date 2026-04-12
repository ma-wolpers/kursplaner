from pathlib import Path

from kursplaner.core.usecases.command_executor_usecase import CommandEntry, FileDelta
from kursplaner.core.usecases.history_usecase import HistoryUseCase


class _CommandExecutorStub:
    def __init__(self):
        self.apply_calls: list[tuple[list[FileDelta], bool]] = []

    def capture(self, _paths: list[Path]) -> dict[Path, str | None]:
        return {}

    def build_entry(self, label: str, before: dict[Path, str | None], after: dict[Path, str | None]):
        del before, after
        return CommandEntry(label=label, deltas=[])

    def apply_deltas(self, deltas: list[FileDelta], *, use_before: bool) -> None:
        self.apply_calls.append((deltas, use_before))


def _entry(label: str) -> CommandEntry:
    return CommandEntry(
        label=label,
        deltas=[FileDelta(path=Path(f"/{label}.md"), before="old", after="new")],
    )


def test_list_recent_undo_entries_returns_newest_first_with_limit():
    history = HistoryUseCase(command_executor=_CommandExecutorStub())
    history.undo_stack = [_entry("A"), _entry("B"), _entry("C")]

    recent = history.list_recent_undo_entries(limit=2)

    assert [item.label for item in recent] == ["C", "B"]
    assert [item.recent_index for item in recent] == [0, 1]


def test_execute_undo_to_recent_index_undoes_prefix_from_top():
    executor = _CommandExecutorStub()
    history = HistoryUseCase(command_executor=executor)
    first = _entry("A")
    second = _entry("B")
    third = _entry("C")
    history.undo_stack = [first, second, third]

    result = history.execute_undo_to_recent_index(recent_index=1, limit=5)

    assert result.applied_count == 2
    assert result.last_entry == second
    assert history.undo_stack == [first]
    assert history.redo_stack == [third, second]
    assert [use_before for _, use_before in executor.apply_calls] == [True, True]
