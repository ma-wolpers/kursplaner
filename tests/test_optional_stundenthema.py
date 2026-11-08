"""``Stundenthema`` ist optional: leer oder fehlend lädt, und nichts füllt es still auf.

Früher war das Thema Pflichtfeld (ein Kurs mit einer leeren Einheit lud gar
nicht) und wurde beim Speichern durch den Dateinamen ersetzt. Alle Tests nutzen
synthetische Dateien in ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.lesson_naming import is_random_lesson_stem
from kursplaner.core.domain.lesson_yaml_policy import canonicalize_lesson_yaml, default_yaml_for_type
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.yaml_registry import LESSON_SCHEMA, parse_yaml_frontmatter
from kursplaner.core.usecases.lesson_commands_usecase import LessonCommandsUseCase
from kursplaner.core.usecases.lesson_edit_usecase import LessonEditUseCase
from kursplaner.core.usecases.load_plan_detail_usecase import LoadPlanDetailUseCase
from kursplaner.infrastructure.repositories.lesson_repository import FileSystemLessonRepository
from kursplaner.infrastructure.repositories.plan_table_file_repository import new_lesson_path

_NO_TOPIC = "---\nStundentyp: Unterricht\nDauer: 2\n---\nBody\n"
_EMPTY_TOPIC = '---\nStundentyp: Unterricht\nDauer: 2\nStundenthema: ""\n---\nBody\n'


def _plan(tmp_path: Path, lesson_text: str | None = None) -> tuple[PlanTableData, Path]:
    """Plan mit einer Zeile, optional verlinkt auf ``Einheiten/ab12cd.md`` mit *lesson_text*."""
    plan_dir = tmp_path / "Kurs"
    lesson = plan_dir / "Einheiten" / "ab12cd.md"
    lesson.parent.mkdir(parents=True)
    plan_path = plan_dir / "Kurs.md"
    plan_path.write_text("# Kursplan\n", encoding="utf-8")
    if lesson_text is not None:
        lesson.write_text(lesson_text, encoding="utf-8")
    table = PlanTableData(
        markdown_path=plan_path,
        headers=["Datum", "Inhalt", "Thema/Ausfall"],
        rows=[["02-03-26", "[[ab12cd]]" if lesson_text is not None else "", ""]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=True,
        metadata={"Lerngruppe": "[[GK blau-1]]"},
    )
    return table, lesson


def test_schema_accepts_missing_and_empty_topic():
    for text in (_NO_TOPIC, _EMPTY_TOPIC):
        data, _ = parse_yaml_frontmatter(text, LESSON_SCHEMA, "synthetisch")
        assert data["Stundentyp"] == "Unterricht"


def test_canonicalize_keeps_empty_topic_and_adds_missing_key():
    assert canonicalize_lesson_yaml({"Stundentyp": "Unterricht", "Stundenthema": ""})["Stundenthema"] == ""
    assert canonicalize_lesson_yaml({"Stundentyp": "Unterricht"})["Stundenthema"] == ""
    assert default_yaml_for_type("LZK")["Stundenthema"] == ""


def test_course_with_topicless_lesson_loads(tmp_path):
    for index, text in enumerate((_NO_TOPIC, _EMPTY_TOPIC)):
        table, _lesson = _plan(tmp_path / f"fall{index}", text)
        usecase = LoadPlanDetailUseCase(plan_repo=None, lesson_repo=FileSystemLessonRepository())

        (day,) = usecase.build_day_columns(table)

        assert day.yaml.get("Stundenthema") == ""


def test_header_of_topicless_unit_never_shows_the_file_code(tmp_path):
    """Leeres Thema: Kopf zeigt die Art (LZK) bzw. nichts (Unterricht), nie den Dataview-Link."""
    usecase = LoadPlanDetailUseCase(plan_repo=None, lesson_repo=FileSystemLessonRepository())
    lzk_text = _EMPTY_TOPIC.replace("Unterricht", "LZK")
    for index, (text, expected) in enumerate(((_EMPTY_TOPIC, ""), (lzk_text, "LZK"))):
        table, _lesson = _plan(tmp_path / f"fall{index}", text)

        (day,) = usecase.build_day_columns(table)

        assert day.header_content() == expected


def test_clearing_the_topic_writes_empty_not_the_file_code(tmp_path):
    _table, lesson = _plan(tmp_path, '---\nStundentyp: Unterricht\nDauer: 2\nStundenthema: "Brüche"\n---\nBody\n')
    repo = FileSystemLessonRepository()

    LessonEditUseCase(lesson_repo=repo).set_lesson_field(lesson, "Stundenthema", "")

    text = lesson.read_text(encoding="utf-8")
    assert "ab12cd" not in text
    assert repo.load_lesson_yaml(lesson).data["Stundenthema"] == ""
    assert text.endswith("Body\n")


def test_created_lessons_get_no_placeholder_topic(tmp_path):
    table, _ = _plan(tmp_path)
    commands = LessonCommandsUseCase(FileSystemLessonRepository())

    unterricht = commands.create_regular_lesson_link(table, 0, "", 2)
    lzk = commands.create_lzk_lesson(table, 0, "", 2)

    for path in (unterricht, lzk):
        assert commands.lesson_repo.load_lesson_yaml(path).data["Stundenthema"] == ""
        assert is_random_lesson_stem(path.stem)


def test_new_lesson_path_is_random_and_avoids_ebw_and_archive_stems(tmp_path, monkeypatch):
    plan_dir = tmp_path / "Kurs"
    (plan_dir / "Einheiten").mkdir(parents=True)
    (plan_dir / "Alteinheiten").mkdir()
    (plan_dir / "Einheiten" / "aaaaaa.ebw").write_text("", encoding="utf-8")
    (plan_dir / "Alteinheiten" / "bbbbbb.md").write_text("", encoding="utf-8")
    candidates = iter(["aaaaaa", "bbbbbb", "cccccc"])
    monkeypatch.setattr(
        "kursplaner.core.domain.lesson_naming.random.choices", lambda _alphabet, k: list(next(candidates))
    )

    path = new_lesson_path(plan_dir, ".ebw")

    assert path == plan_dir / "Einheiten" / "cccccc.ebw"
