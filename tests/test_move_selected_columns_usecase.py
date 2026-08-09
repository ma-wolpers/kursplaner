from pathlib import Path
from typing import Any, cast

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.move_selected_columns_usecase import MoveSelectedColumnsUseCase


class _PlanRepoSpy:
    def __init__(self):
        self.save_calls = 0

    def save_plan_table(self, _table: PlanTableData) -> None:
        self.save_calls += 1


class _PlanCommandsSpy:
    def __init__(self):
        self.swap_calls: list[tuple[int, int]] = []

    def swap_contents(self, table: PlanTableData, row_a: int, row_b: int) -> None:
        self.swap_calls.append((row_a, row_b))
        table.rows[row_a][2], table.rows[row_b][2] = table.rows[row_b][2], table.rows[row_a][2]


def _build_table() -> PlanTableData:
    return PlanTableData(
        markdown_path=Path("plan.md"),
        headers=["Datum", "Stunden", "Inhalt"],
        rows=[
            ["06.02.2026", "2", "[[gruen-6 02-06 Fach-Diagnose]]"],
            ["27.02.2026", "1", "[[gruen-6 02-27 Supertrumpf Kodierung]]"],
        ],
        start_line=1,
        end_line=2,
        source_lines=[],
        had_trailing_newline=True,
        metadata={"Lerngruppe": "[[gruen-6]]"},
    )


def _build_usecase(plan_repo: _PlanRepoSpy, commands: _PlanCommandsSpy) -> MoveSelectedColumnsUseCase:
    return MoveSelectedColumnsUseCase(
        plan_repo=cast(Any, plan_repo),
        plan_commands=cast(Any, commands),
    )


def test_execute_swaps_content_and_saves_once():
    table = _build_table()
    plan_repo = _PlanRepoSpy()
    commands = _PlanCommandsSpy()

    usecase = _build_usecase(plan_repo, commands)

    result = usecase.execute(table, 0, 1)

    assert result.proceed is True
    assert table.rows[0][2] == "[[gruen-6 02-27 Supertrumpf Kodierung]]"
    assert table.rows[1][2] == "[[gruen-6 02-06 Fach-Diagnose]]"
    assert commands.swap_calls == [(0, 1)]
    assert plan_repo.save_calls == 1


def test_execute_is_noop_when_rows_are_identical():
    table = _build_table()
    plan_repo = _PlanRepoSpy()
    commands = _PlanCommandsSpy()

    usecase = _build_usecase(plan_repo, commands)

    result = usecase.execute(table, 0, 0)

    assert result.proceed is True
    assert commands.swap_calls == []
    assert plan_repo.save_calls == 0
    assert table.rows[0][2] == "[[gruen-6 02-06 Fach-Diagnose]]"


def test_execute_rejects_invalid_row_index():
    table = _build_table()
    plan_repo = _PlanRepoSpy()
    commands = _PlanCommandsSpy()

    usecase = _build_usecase(plan_repo, commands)

    result = usecase.execute(table, 0, 5)

    assert result.proceed is False
    assert result.error_message
    assert commands.swap_calls == []
    assert plan_repo.save_calls == 0
