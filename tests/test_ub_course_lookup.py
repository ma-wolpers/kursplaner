from pathlib import Path
from types import SimpleNamespace

import pytest

from kursplaner.core.usecases.ub_course_lookup import LessonCourse, courses_by_lesson_stem


class _FakePlanRepo:
    def __init__(self, tables):
        self._tables = tables

    def load_plan_tables(self, _base_dir):
        return self._tables


def _table(course: str, stems: list[str], stufe: str = "7"):
    return SimpleNamespace(
        markdown_path=Path("Unterricht") / course / f"{course}.md",
        headers=["Datum", "Inhalt"],
        rows=[["01.01.26", f"[[{stem}]]"] for stem in stems],
        metadata={"Stufe": stufe},
    )


def test_maps_each_lesson_to_course_name_and_stufe(tmp_path):
    repo = _FakePlanRepo([_table("ma7", ["a1"]), _table("inf10", ["b2"], stufe="10")])

    assert courses_by_lesson_stem(repo, tmp_path) == {
        "a1": LessonCourse(course_name="ma7", stufe=7),
        "b2": LessonCourse(course_name="inf10", stufe=10),
    }


def test_missing_base_dir_gives_empty_mapping(tmp_path):
    assert courses_by_lesson_stem(_FakePlanRepo([_table("ma7", ["a1"])]), tmp_path / "fehlt") == {}


def test_lesson_in_two_courses_raises(tmp_path):
    repo = _FakePlanRepo([_table("ma7", ["a1"]), _table("ma8", ["a1"])])

    with pytest.raises(RuntimeError, match="Uneindeutige Kurszuordnung"):
        courses_by_lesson_stem(repo, tmp_path)
