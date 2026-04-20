from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData
from kursplaner.core.usecases.convert_to_hospitation_usecase import ConvertToHospitationUseCase


class _PlanRepoStub:
    def __init__(self) -> None:
        self.saved = False

    def save_plan_table(self, table: PlanTableData) -> None:
        self.saved = True


class _LessonRepoStub:
    def __init__(self) -> None:
        self.saved_lesson: LessonYamlData | None = None

    def load_lesson_yaml(self, path: Path) -> LessonYamlData:
        return LessonYamlData(lesson_path=path, data={})

    def save_lesson_yaml(self, lesson: LessonYamlData) -> None:
        self.saved_lesson = lesson


class _LessonCommandsStub:
    def __init__(self, link_path: Path) -> None:
        self.link_path = link_path
        self.created_topic: str | None = None
        self.created_hours: int | None = None

    def create_regular_lesson_link(
        self,
        table: PlanTableData,
        row_index: int,
        topic: str,
        default_hours: int,
    ) -> Path:
        self.created_topic = topic
        self.created_hours = default_hours
        return self.link_path


class _LessonTransferStub:
    def resolve_existing_link(self, table: PlanTableData, row_index: int) -> Path | None:
        return None


def test_execute_write_uses_plain_hospitation_title_and_link_only(tmp_path):
    plan_path = tmp_path / "Inf lila-5 26-2.md"
    plan_path.write_text("", encoding="utf-8")

    table = PlanTableData(
        markdown_path=plan_path,
        headers=["datum", "stunden", "inhalt"],
        rows=[["21-04-26", "2", ""]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={"Lerngruppe": "[[lila-5]]"},
    )

    created_link = tmp_path / "Einheiten" / "lila-5 04-21 Hospitation.md"
    created_link.parent.mkdir(parents=True)
    created_link.write_text("# Test\n", encoding="utf-8")

    plan_repo = _PlanRepoStub()
    lesson_repo = _LessonRepoStub()
    lesson_commands = _LessonCommandsStub(created_link)
    lesson_transfer = _LessonTransferStub()

    usecase = ConvertToHospitationUseCase(
        plan_repo=plan_repo,
        lesson_repo=lesson_repo,
        lesson_commands=lesson_commands,
        lesson_transfer=lesson_transfer,
    )

    result = usecase.execute_write(
        table=table,
        row_index=0,
        focus_text="Sozialverhalten",
        default_hours=2,
        allow_create_link=True,
        allow_yaml_save=True,
        allow_plan_save=True,
    )

    assert result.proceed is True
    assert lesson_commands.created_topic == "Hospitation"
    assert table.rows[0][2] == "[[lila-5 04-21 Hospitation]]"
    assert "HO " not in table.rows[0][2]
    assert plan_repo.saved is True

    assert lesson_repo.saved_lesson is not None
    assert lesson_repo.saved_lesson.data["Stundenthema"] == "Hospitation"
    assert lesson_repo.saved_lesson.data["Stundentyp"] == "Hospitation"
    assert lesson_repo.saved_lesson.data["Beobachtungsschwerpunkte"] == "Sozialverhalten"
