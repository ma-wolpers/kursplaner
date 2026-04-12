from pathlib import Path
from typing import Any, cast

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.move_selected_columns_usecase import MoveSelectedColumnsUseCase
from kursplaner.core.usecases.rename_linked_file_for_row_usecase import RenameLinkedFileResult


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


class _LessonTransferStub:
    def __init__(self, row_links: dict[int, Path | None]):
        self.row_links = row_links

    def resolve_existing_link(self, _table: PlanTableData, row_index: int) -> Path | None:
        return self.row_links.get(row_index)


class _RenameRowSpy:
    def __init__(self, fail_on_call: int | None = None):
        self.calls: list[dict[str, Any]] = []
        self.fail_on_call = fail_on_call

    def execute(self, **kwargs) -> RenameLinkedFileResult:
        self.calls.append(kwargs)
        call_no = len(self.calls)
        if self.fail_on_call is not None and call_no == self.fail_on_call:
            return RenameLinkedFileResult(proceed=False, error_message="rename failed")
        desired_stem = str(kwargs.get("desired_stem", "")).strip()
        return RenameLinkedFileResult(proceed=True, target_path=Path(f"{desired_stem}.md"))


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


def test_execute_swaps_content_renames_both_rows_and_saves_once(tmp_path):
    link_a = tmp_path / "gruen-6 02-06 Fach-Diagnose.md"
    link_b = tmp_path / "gruen-6 02-27 Supertrumpf Kodierung.md"
    link_a.write_text("A", encoding="utf-8")
    link_b.write_text("B", encoding="utf-8")

    table = _build_table()
    plan_repo = _PlanRepoSpy()
    commands = _PlanCommandsSpy()
    transfer = _LessonTransferStub({0: link_a, 1: link_b})
    rename = _RenameRowSpy()

    usecase = MoveSelectedColumnsUseCase(
        plan_repo=cast(Any, plan_repo),
        plan_commands=cast(Any, commands),
        lesson_transfer=cast(Any, transfer),
        rename_linked_file_for_row=cast(Any, rename),
    )

    result = usecase.execute(table, 0, 1)

    assert result.proceed is True
    assert table.rows[0][2] == "[[gruen-6 02-27 Supertrumpf Kodierung]]"
    assert table.rows[1][2] == "[[gruen-6 02-06 Fach-Diagnose]]"
    assert commands.swap_calls == [(0, 1)]
    assert plan_repo.save_calls == 1
    assert len(rename.calls) == 2
    assert rename.calls[0]["row_index"] == 0
    assert rename.calls[0]["desired_stem"] == "gruen-6 02-06 Supertrumpf Kodierung"
    assert rename.calls[0]["allow_conflict_suffix"] is False
    assert rename.calls[1]["row_index"] == 1
    assert rename.calls[1]["desired_stem"] == "gruen-6 02-27 Fach-Diagnose"
    assert rename.calls[1]["allow_conflict_suffix"] is False


def test_execute_swaps_and_saves_when_link_is_missing(tmp_path):
    link_a = tmp_path / "gruen-6 02-06 Fach-Diagnose.md"
    link_a.write_text("A", encoding="utf-8")

    table = _build_table()
    plan_repo = _PlanRepoSpy()
    commands = _PlanCommandsSpy()
    transfer = _LessonTransferStub({0: link_a, 1: None})
    rename = _RenameRowSpy()

    usecase = MoveSelectedColumnsUseCase(
        plan_repo=cast(Any, plan_repo),
        plan_commands=cast(Any, commands),
        lesson_transfer=cast(Any, transfer),
        rename_linked_file_for_row=cast(Any, rename),
    )

    result = usecase.execute(table, 0, 1)

    assert result.proceed is True
    assert plan_repo.save_calls == 1
    assert commands.swap_calls == [(0, 1)]
    assert len(rename.calls) == 1
    assert rename.calls[0]["row_index"] == 1
    assert rename.calls[0]["desired_stem"] == "gruen-6 02-27 Fach-Diagnose"
    assert rename.calls[0]["allow_conflict_suffix"] is False
    assert table.rows[0][2] == "[[gruen-6 02-27 Supertrumpf Kodierung]]"
    assert table.rows[1][2] == "[[gruen-6 02-06 Fach-Diagnose]]"


def test_execute_rolls_back_swapped_content_when_second_rename_fails(tmp_path):
    link_a = tmp_path / "gruen-6 02-06 Fach-Diagnose.md"
    link_b = tmp_path / "gruen-6 02-27 Supertrumpf Kodierung.md"
    link_a.write_text("A", encoding="utf-8")
    link_b.write_text("B", encoding="utf-8")

    table = _build_table()
    plan_repo = _PlanRepoSpy()
    commands = _PlanCommandsSpy()
    transfer = _LessonTransferStub({0: link_a, 1: link_b})
    rename = _RenameRowSpy(fail_on_call=2)

    usecase = MoveSelectedColumnsUseCase(
        plan_repo=cast(Any, plan_repo),
        plan_commands=cast(Any, commands),
        lesson_transfer=cast(Any, transfer),
        rename_linked_file_for_row=cast(Any, rename),
    )

    result = usecase.execute(table, 0, 1)

    assert result.proceed is False
    assert commands.swap_calls == [(0, 1), (0, 1)]
    assert plan_repo.save_calls == 0
    assert len(rename.calls) == 3
    assert rename.calls[2]["desired_stem"] == "gruen-6 02-27 Supertrumpf Kodierung"
    assert table.rows[0][2] == "[[gruen-6 02-06 Fach-Diagnose]]"
    assert table.rows[1][2] == "[[gruen-6 02-27 Supertrumpf Kodierung]]"
