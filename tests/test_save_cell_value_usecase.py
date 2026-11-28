from typing import Any, cast

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.save_cell_value_usecase import SaveCellValueUseCase


class _LessonEditStub:
    def __init__(self):
        self.set_lesson_field_calls = 0

    def validate_table(self, _table: PlanTableData) -> None:
        return None

    def set_lesson_field(self, lesson_path, field_key, value, list_entries=None) -> None:
        _ = lesson_path, field_key, value, list_entries
        self.set_lesson_field_calls += 1


class _PlanRepoStub:
    def save_plan_table(self, _table: PlanTableData) -> None:
        return None


class _LessonTransferStub:
    pass


class _RowDisplayModeStub:
    @staticmethod
    def list_like_fields() -> set[str]:
        return set()


class _UbSyncStub:
    def __init__(self, *, save_result=True):
        self.save_result = bool(save_result)
        self.save_calls: list[dict[str, object]] = []

    def save_list(self, *, workspace_root, lesson_path, field, entries):
        self.save_calls.append(
            {"workspace_root": workspace_root, "lesson_path": lesson_path, "field": field, "entries": list(entries)}
        )
        return self.save_result


def test_execute_ub_steps_saves_only_that_list(tmp_path):
    table = PlanTableData(
        markdown_path=tmp_path / "Plan.md",
        headers=["Datum", "Stunden", "Inhalt"],
        rows=[["06.02.2026", "2", "[[gruen-6 02-06 Fach-Diagnose]]"]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={"Lerngruppe": "[[gruen-6]]"},
    )
    lesson_path = tmp_path / "Einheiten" / "gruen-6 02-06 Fach-Diagnose.md"
    lesson_path.parent.mkdir(parents=True, exist_ok=True)
    lesson_path.write_text("---\nStundenthema: Alt\n---\n", encoding="utf-8")

    lesson_edit = _LessonEditStub()
    ub_sync = _UbSyncStub()

    usecase = SaveCellValueUseCase(
        lesson_edit=cast(Any, lesson_edit),
        plan_repo=cast(Any, _PlanRepoStub()),
        lesson_transfer=cast(Any, _LessonTransferStub()),
        row_display_mode_usecase=cast(Any, _RowDisplayModeStub()),
        sync_ub_development_focus_usecase=cast(Any, ub_sync),
    )

    result = usecase.execute(
        table=table,
        row_index=0,
        field_key="Baustellen",
        value="Neuer Schritt",
        lesson_path=lesson_path,
        list_entries=["Neuer Schritt"],
        allow_yaml_save=True,
    )

    assert result.proceed is True
    assert lesson_edit.set_lesson_field_calls == 0
    assert len(ub_sync.save_calls) == 1
    assert ub_sync.save_calls[0]["field"] == "Baustellen"
    assert ub_sync.save_calls[0]["entries"] == ["Neuer Schritt"]


def test_execute_ub_resources_fails_cleanly_when_no_ub_link(tmp_path):
    table = PlanTableData(
        markdown_path=tmp_path / "Plan.md",
        headers=["Datum", "Stunden", "Inhalt"],
        rows=[["06.02.2026", "2", "[[gruen-6 02-06 Fach-Diagnose]]"]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={"Lerngruppe": "[[gruen-6]]"},
    )
    lesson_path = tmp_path / "Einheiten" / "gruen-6 02-06 Fach-Diagnose.md"
    lesson_path.parent.mkdir(parents=True, exist_ok=True)
    lesson_path.write_text("---\nStundenthema: Alt\n---\n", encoding="utf-8")

    lesson_edit = _LessonEditStub()
    ub_sync = _UbSyncStub(save_result=False)

    usecase = SaveCellValueUseCase(
        lesson_edit=cast(Any, lesson_edit),
        plan_repo=cast(Any, _PlanRepoStub()),
        lesson_transfer=cast(Any, _LessonTransferStub()),
        row_display_mode_usecase=cast(Any, _RowDisplayModeStub()),
        sync_ub_development_focus_usecase=cast(Any, ub_sync),
    )

    result = usecase.execute(
        table=table,
        row_index=0,
        field_key="Ressourcen",
        value="Neue Ressource",
        lesson_path=lesson_path,
        list_entries=["Neue Ressource"],
        allow_yaml_save=True,
    )

    assert result.proceed is False
    assert "UB-Synchronisierung fehlgeschlagen" in str(result.error_message)
    assert lesson_edit.set_lesson_field_calls == 0
    assert len(ub_sync.save_calls) == 1
