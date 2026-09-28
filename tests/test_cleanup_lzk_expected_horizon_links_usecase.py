from datetime import datetime
from pathlib import Path

from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData
from kursplaner.core.usecases.cleanup_lzk_expected_horizon_links_usecase import CleanupLzkExpectedHorizonLinksUseCase
from tests.day_column_factory import make_day_column


class _LessonRepoStub:
    def __init__(self, lesson_by_path: dict[Path, LessonYamlData]):
        self._lesson_by_path = dict(lesson_by_path)
        self.saved: list[LessonYamlData] = []

    def load_lesson_yaml(self, path: Path) -> LessonYamlData:
        return self._lesson_by_path[path.resolve()]

    def save_lesson_yaml(self, lesson: LessonYamlData, *, repair_oberthema: bool = False) -> None:
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
            make_day_column(link=lesson_missing, yaml={"Stundentyp": "LZK"}),
            make_day_column(link=lesson_existing, yaml={"Stundentyp": "LZK"}),
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


def _single_lzk_setup(tmp_path: Path, link: str, *, with_vault: bool = True):
    vault = tmp_path / "Vault"
    if with_vault:
        (vault / ".obsidian").mkdir(parents=True)
    course_dir = vault / "kurs"
    einheiten_dir = course_dir / "Einheiten"
    einheiten_dir.mkdir(parents=True)
    lesson = (einheiten_dir / "lzk.md").resolve()
    lesson.write_text("x", encoding="utf-8")
    repo = _LessonRepoStub(
        {
            lesson: LessonYamlData(
                lesson_path=lesson,
                data={"Stundentyp": "LZK", "Kompetenzhorizont": link, "created_at": "2026-09-29T15:30:00"},
            )
        }
    )
    day = make_day_column(link=lesson, yaml={"Stundentyp": "LZK"})
    return vault, course_dir, repo, lesson, day


def test_cleanup_keeps_valid_link_to_other_vault_folder(tmp_path):
    vault, course_dir, repo, lesson, day = _single_lzk_setup(tmp_path, "[[Archiv/KH neu]]")
    (vault / "Archiv").mkdir()
    (vault / "Archiv" / "KH neu.md").write_text("ok", encoding="utf-8")

    result = CleanupLzkExpectedHorizonLinksUseCase(lesson_repo=repo).execute(
        table=_table(course_dir / "kurs.md"), day_columns=[day]
    )

    assert result.cleared_links == 0
    assert repo._lesson_by_path[lesson].data["Kompetenzhorizont"] == "[[Archiv/KH neu]]"


def test_cleanup_clears_missing_link_to_other_vault_folder(tmp_path):
    _vault, course_dir, repo, lesson, day = _single_lzk_setup(tmp_path, "[[Archiv/KH weg]]")

    result = CleanupLzkExpectedHorizonLinksUseCase(lesson_repo=repo).execute(
        table=_table(course_dir / "kurs.md"), day_columns=[day]
    )

    assert result.cleared_links == 1
    assert repo._lesson_by_path[lesson].data["Kompetenzhorizont"] == ""


def test_cleanup_keeps_path_link_when_vault_root_is_unknown(tmp_path):
    _vault, course_dir, repo, lesson, day = _single_lzk_setup(tmp_path, "[[Archiv/KH]]", with_vault=False)

    result = CleanupLzkExpectedHorizonLinksUseCase(lesson_repo=repo).execute(
        table=_table(course_dir / "kurs.md"), day_columns=[day]
    )

    assert result.cleared_links == 0
    assert repo._lesson_by_path[lesson].data["Kompetenzhorizont"] == "[[Archiv/KH]]"
