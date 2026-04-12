from datetime import datetime
from pathlib import Path

from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData
from kursplaner.core.usecases.cleanup_lzk_expected_horizon_links_usecase import CleanupLzkExpectedHorizonLinksUseCase


class _LessonRepoStub:
    def __init__(self, lesson_by_path: dict[Path, LessonYamlData]):
        self._lesson_by_path = dict(lesson_by_path)
        self.saved: list[LessonYamlData] = []

    def load_lesson_yaml(self, path: Path) -> LessonYamlData:
        return self._lesson_by_path[path.resolve()]

    def save_lesson_yaml(self, lesson: LessonYamlData) -> None:
        self.saved.append(lesson)
        self._lesson_by_path[lesson.lesson_path.resolve()] = lesson


def _table(plan_path: Path) -> PlanTableData:
    return PlanTableData(
        markdown_path=plan_path,
        headers=["Datum", "Stunden", "Inhalt"],
        rows=[["02-04-26", "2", "[[LZK 1]]"]],
        start_line=1,
        end_line=2,
        source_lines=[],
        had_trailing_newline=True,
        metadata={"Kursfach": "Informatik", "Lerngruppe": "[[gruen-6]]"},
    )


def test_cleanup_clears_missing_links_and_repairs_invalid_created_at(tmp_path):
    course_dir = tmp_path / "kurs"
    einheiten_dir = course_dir / "Einheiten"
    einheiten_dir.mkdir(parents=True)
    (course_dir / "kurs.md").write_text("", encoding="utf-8")

    existing_eh = (course_dir / "KH-gueltig.md").resolve()
    existing_eh.write_text("ok", encoding="utf-8")

    lesson_missing = (einheiten_dir / "a.md").resolve()
    lesson_missing.write_text("x", encoding="utf-8")
    lesson_existing = (einheiten_dir / "b.md").resolve()
    lesson_existing.write_text("x", encoding="utf-8")

    repo = _LessonRepoStub(
        {
            lesson_missing: LessonYamlData(
                lesson_path=lesson_missing,
                data={"Stundentyp": "LZK", "Kompetenzhorizont": "[[KH-fehlt]]", "created_at": "kaputt"},
            ),
            lesson_existing: LessonYamlData(
                lesson_path=lesson_existing,
                data={"Stundentyp": "LZK", "Kompetenzhorizont": "[[KH-gueltig]]", "created_at": "kaputt"},
            ),
        }
    )

    result = CleanupLzkExpectedHorizonLinksUseCase(lesson_repo=repo).execute(
        table=_table(course_dir / "kurs.md"),
        day_columns=[
            {"is_lzk": True, "link": lesson_missing},
            {"is_lzk": True, "link": lesson_existing},
        ],
    )

    assert result.cleared_links == 1
    assert result.repaired_timestamps == 1
    assert len(repo.saved) == 2

    first = repo._lesson_by_path[lesson_missing].data
    assert first["Kompetenzhorizont"] == ""
    assert first["created_at"] == ""

    second = repo._lesson_by_path[lesson_existing].data
    assert second["Kompetenzhorizont"] == "[[KH-gueltig]]"
    assert datetime.fromisoformat(str(second["created_at"]))
