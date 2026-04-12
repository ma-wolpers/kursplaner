from pathlib import Path
from typing import Any, cast

from kursplaner.core.domain.plan_table import LessonYamlData
from kursplaner.core.usecases.lesson_transfer_usecase import LessonTransferUseCase


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
