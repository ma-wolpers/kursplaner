from pathlib import Path
from typing import Any, cast

from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData
from kursplaner.core.usecases.lesson_transfer_usecase import LessonTransferUseCase


def _table(rows: list[list[str]]) -> PlanTableData:
    return PlanTableData(
        markdown_path=Path("Kurs.md"),
        headers=["Datum", "Inhalt", "Thema/Ausfall"],
        rows=rows,
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={},
    )


class _LessonRepoStub:
    def __init__(self):
        self.loaded: dict[Path, LessonYamlData] = {}
        self.saved: list[LessonYamlData] = []

    def load_lesson_yaml(self, path: Path) -> LessonYamlData:
        lesson = self.loaded[path]
        return LessonYamlData(lesson_path=lesson.lesson_path, data=dict(lesson.data))

    def save_lesson_yaml(self, lesson: LessonYamlData) -> None:
        self.saved.append(lesson)
        self.loaded[lesson.lesson_path] = LessonYamlData(lesson_path=lesson.lesson_path, data=dict(lesson.data))


class _LessonFileRepoStub:
    def write_file_content(self, target_path: Path, content: str) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")


def test_write_pasted_lesson_clears_unterrichtsbesuch_even_when_stem_unchanged(tmp_path):
    target = tmp_path / "Einheiten" / "gruen-6 02-06 Fach-Diagnose.md"
    lesson_repo = _LessonRepoStub()
    lesson_repo.loaded[target] = LessonYamlData(
        lesson_path=target,
        data={
            "Stundenthema": "Fach-Diagnose",
            "Unterrichtsbesuch": "[[UB 26-02-06 Fach-Diagnose]]",
        },
    )

    usecase = LessonTransferUseCase(
        lesson_repo=cast(Any, lesson_repo),
        lesson_file_repo=cast(Any, _LessonFileRepoStub()),
    )

    created = usecase.write_pasted_lesson(
        target_path=target,
        content="---\nStundenthema: Fach-Diagnose\n---\n",
        source_stem=target.stem,
    )

    assert created == target
    assert len(lesson_repo.saved) == 1
    assert lesson_repo.saved[0].data.get("Unterrichtsbesuch") == ""


def test_write_pasted_lesson_updates_topic_and_clears_unterrichtsbesuch_on_rename(tmp_path):
    target = tmp_path / "Einheiten" / "gruen-6 02-13 Fach-Diagnose 2.md"
    lesson_repo = _LessonRepoStub()
    lesson_repo.loaded[target] = LessonYamlData(
        lesson_path=target,
        data={
            "Stundenthema": "Fach-Diagnose 1",
            "Unterrichtsbesuch": "[[UB 26-02-06 Fach-Diagnose]]",
        },
    )

    usecase = LessonTransferUseCase(
        lesson_repo=cast(Any, lesson_repo),
        lesson_file_repo=cast(Any, _LessonFileRepoStub()),
    )

    usecase.write_pasted_lesson(
        target_path=target,
        content="---\nStundenthema: Fach-Diagnose 1\n---\n",
        source_stem="gruen-6 02-06 Fach-Diagnose",
    )

    assert len(lesson_repo.saved) == 1
    saved_data = lesson_repo.saved[0].data
    assert saved_data.get("Stundenthema") == "Fach-Diagnose 2"
    assert saved_data.get("Unterrichtsbesuch") == ""


def _usecase() -> LessonTransferUseCase:
    return LessonTransferUseCase(
        lesson_repo=cast(Any, _LessonRepoStub()),
        lesson_file_repo=cast(Any, _LessonFileRepoStub()),
    )


def test_relink_row_to_stem_writes_dataview_link_to_inhalt_not_thema_ausfall():
    table = _table([["01-09-25", "", "[[li2 Kodierung]]"]])

    _usecase().relink_row_to_stem(table, 0, "ab12cd", preserve_alias=False)

    assert table.inhalt(0) == '`= link("ab12cd", [[ab12cd]].Stundenthema)`'
    assert table.thema_ausfall(0) == "[[li2 Kodierung]]"


def test_relink_row_to_stem_preserve_alias_flag_has_no_effect_on_output():
    table_true = _table([["01-09-25", "[[oldstem|Alter Alias]]", ""]])
    table_false = _table([["01-09-25", "[[oldstem|Alter Alias]]", ""]])

    _usecase().relink_row_to_stem(table_true, 0, "ab12cd", preserve_alias=True)
    _usecase().relink_row_to_stem(table_false, 0, "ab12cd", preserve_alias=False)

    assert table_true.inhalt(0) == table_false.inhalt(0)
    assert table_true.inhalt(0) == '`= link("ab12cd", [[ab12cd]].Stundenthema)`'


def test_relink_row_to_stem_raises_for_invalid_row_index():
    table = _table([["01-09-25", "", ""]])

    try:
        _usecase().relink_row_to_stem(table, 5, "ab12cd")
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass


def test_replace_or_append_first_link_appends_when_cell_empty():
    table = _table([["01-09-25", "", ""]])

    _usecase().replace_or_append_first_link(table, 0, "ab12cd")

    assert table.inhalt(0) == '`= link("ab12cd", [[ab12cd]].Stundenthema)`'


def test_replace_or_append_first_link_replaces_existing_dataview_query():
    table = _table([["01-09-25", '`= link("oldstem", [[oldstem]].Stundenthema)`', ""]])

    _usecase().replace_or_append_first_link(table, 0, "newstem")

    assert table.inhalt(0) == '`= link("newstem", [[newstem]].Stundenthema)`'


def test_replace_or_append_first_link_replaces_legacy_plain_link():
    table = _table([["01-09-25", "[[oldstem]]", ""]])

    _usecase().replace_or_append_first_link(table, 0, "newstem")

    assert table.inhalt(0) == '`= link("newstem", [[newstem]].Stundenthema)`'
