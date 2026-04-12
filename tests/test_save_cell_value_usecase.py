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


class _RenameLinkedFileStub:
    def __init__(self):
        self.calls = 0

    def execute(self, **kwargs):
        _ = kwargs
        self.calls += 1
        raise AssertionError("Rename should not be called when plan save is denied")


class _RowDisplayModeStub:
    @staticmethod
    def list_like_fields() -> set[str]:
        return set()


class _UbSyncStub:
    def __init__(self, *, load_steps=None, load_resources=None, save_result=True):
        self.load_steps = list(load_steps or [])
        self.load_resources = list(load_resources or [])
        self.save_result = bool(save_result)
        self.load_calls = 0
        self.save_calls: list[dict[str, object]] = []

    def load(self, *, workspace_root, lesson_path):
        _ = workspace_root, lesson_path
        self.load_calls += 1
        return type(
            "_Focus",
            (),
            {
                "professional_steps": list(self.load_steps),
                "usable_resources": list(self.load_resources),
            },
        )()

    def save(self, *, workspace_root, lesson_path, professional_steps_text, usable_resources_text):
        self.save_calls.append(
            {
                "workspace_root": workspace_root,
                "lesson_path": lesson_path,
                "professional_steps_text": professional_steps_text,
                "usable_resources_text": usable_resources_text,
            }
        )
        return self.save_result


def test_execute_aborts_before_rename_when_plan_save_for_rename_is_denied(tmp_path):
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
    rename_uc = _RenameLinkedFileStub()

    usecase = SaveCellValueUseCase(
        lesson_edit=cast(Any, lesson_edit),
        plan_repo=cast(Any, _PlanRepoStub()),
        lesson_transfer=cast(Any, _LessonTransferStub()),
        rename_linked_file_for_row=cast(Any, rename_uc),
        row_display_mode_usecase=cast(Any, _RowDisplayModeStub()),
        sync_ub_development_focus_usecase=None,
    )

    result = usecase.execute(
        table=table,
        row_index=0,
        field_key="Stundenthema",
        value="Neu",
        lesson_path=lesson_path,
        list_entries=None,
        should_rename_topic=True,
        desired_stem="gruen-6 02-06 Neu",
        allow_plan_hours_save=True,
        allow_yaml_save=True,
        allow_duration_save=True,
        allow_rename=True,
        allow_plan_save_for_rename=False,
    )

    assert result.proceed is False
    assert result.error_message == "Speichern der Planungstabelle abgebrochen."
    assert lesson_edit.set_lesson_field_calls == 1
    assert rename_uc.calls == 0


def test_execute_ub_steps_syncs_directly_and_preserves_resources(tmp_path):
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
    rename_uc = _RenameLinkedFileStub()
    ub_sync = _UbSyncStub(load_steps=["Alt Schritt"], load_resources=["Res A", "Res B"])

    usecase = SaveCellValueUseCase(
        lesson_edit=cast(Any, lesson_edit),
        plan_repo=cast(Any, _PlanRepoStub()),
        lesson_transfer=cast(Any, _LessonTransferStub()),
        rename_linked_file_for_row=cast(Any, rename_uc),
        row_display_mode_usecase=cast(Any, _RowDisplayModeStub()),
        sync_ub_development_focus_usecase=cast(Any, ub_sync),
    )

    result = usecase.execute(
        table=table,
        row_index=0,
        field_key="Professionalisierungsschritte",
        value="Neuer Schritt",
        lesson_path=lesson_path,
        list_entries=["Neuer Schritt"],
        should_rename_topic=False,
        desired_stem="",
        allow_plan_hours_save=True,
        allow_yaml_save=True,
        allow_duration_save=True,
        allow_rename=True,
        allow_plan_save_for_rename=True,
    )

    assert result.proceed is True
    assert lesson_edit.set_lesson_field_calls == 0
    assert ub_sync.load_calls == 1
    assert len(ub_sync.save_calls) == 1
    assert ub_sync.save_calls[0]["professional_steps_text"] == "Neuer Schritt"
    assert ub_sync.save_calls[0]["usable_resources_text"] == "Res A\nRes B"
    assert rename_uc.calls == 0


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
    rename_uc = _RenameLinkedFileStub()
    ub_sync = _UbSyncStub(save_result=False)

    usecase = SaveCellValueUseCase(
        lesson_edit=cast(Any, lesson_edit),
        plan_repo=cast(Any, _PlanRepoStub()),
        lesson_transfer=cast(Any, _LessonTransferStub()),
        rename_linked_file_for_row=cast(Any, rename_uc),
        row_display_mode_usecase=cast(Any, _RowDisplayModeStub()),
        sync_ub_development_focus_usecase=cast(Any, ub_sync),
    )

    result = usecase.execute(
        table=table,
        row_index=0,
        field_key="Nutzbare Ressourcen",
        value="Neue Ressource",
        lesson_path=lesson_path,
        list_entries=["Neue Ressource"],
        should_rename_topic=False,
        desired_stem="",
        allow_plan_hours_save=True,
        allow_yaml_save=True,
        allow_duration_save=True,
        allow_rename=True,
        allow_plan_save_for_rename=True,
    )

    assert result.proceed is False
    assert "UB-Synchronisierung fehlgeschlagen" in str(result.error_message)
    assert lesson_edit.set_lesson_field_calls == 0
    assert ub_sync.load_calls == 1
    assert len(ub_sync.save_calls) == 1
    assert rename_uc.calls == 0
