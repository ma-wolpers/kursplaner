from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.infrastructure.repositories.lesson_index_repository import FileSystemLessonIndexRepository
from kursplaner.infrastructure.repositories.lesson_repository import FileSystemLessonRepository


def _create_lesson(path: Path, title: str, oberthema: str = ""):
    content = (
        "---\n"
        "Stundentyp: Unterricht\n"
        "Dauer: 2\n"
        "Kompetenzen:\n"
        '  - ""\n'
        f"Stundenthema: {title}\n"
        'Stundenziel: ""\n'
        "Material:\n"
        '  - ""\n'
        f"Oberthema: {oberthema}\n"
        "---\n\n# Inhalt\n"
    )
    path.write_text(content, encoding="utf-8")


def _build_plan_table(root: Path) -> PlanTableData:
    return PlanTableData(
        markdown_path=root / "FachA" / "FachA.md",
        headers=["datum", "inhalt"],
        rows=[
            ["2026-03-01", "[[stunde-1]]"],
            ["2026-03-02", "[[stunde-2]]"],
        ],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={},
    )


def test_lesson_repository_batch_contract(tmp_path):
    root = tmp_path / "Unterricht"
    lesson_dir = root / "FachA" / "Einheiten"
    lesson_dir.mkdir(parents=True)
    _create_lesson(lesson_dir / "stunde-1.md", "Thema 1", "Ober 1")
    _create_lesson(lesson_dir / "stunde-2.md", "Thema 2", "Ober 2")

    table = _build_plan_table(root)
    repo = FileSystemLessonRepository()

    subset = repo.load_lessons_for_rows(table, [0])
    all_rows = repo.load_lessons_for_all_rows(table)

    assert 0 in subset
    assert 0 in all_rows
    assert subset[0].data.get("Stundenthema") == all_rows[0].data.get("Stundenthema")
    assert all_rows[0].data.get("Stundenthema") == "Thema 1"
    assert all_rows[1].data.get("Stundenthema") == "Thema 2"


def test_lesson_index_repository_contract_keys(tmp_path):
    root = tmp_path / "Unterricht"
    lesson_dir = root / "FachA" / "Einheiten"
    lesson_dir.mkdir(parents=True)
    _create_lesson(lesson_dir / "stunde-1.md", "Index Thema", "Index Ober")

    table = PlanTableData(
        markdown_path=root / "FachA" / "FachA.md",
        headers=["datum", "inhalt"],
        rows=[["2026-03-01", "[[stunde-1]]"]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={},
    )
    repo = FileSystemLessonIndexRepository()
    repo.rebuild_index(root)

    result = repo.load_lessons_metadata_for_rows(table, [0])
    assert 0 in result
    item = result[0]
    assert set(["Stundenthema", "Oberthema", "path", "mtime_ns", "index_version"]).issubset(item.keys())
    assert item["Stundenthema"] == "Index Thema"
    assert item["index_version"] == FileSystemLessonIndexRepository.INDEX_FORMAT_VERSION


def test_lzk_expected_horizon_link_is_written_quoted(tmp_path):
    lesson_path = tmp_path / "lzk.md"
    lesson_path.write_text("---\nStundentyp: LZK\nDauer: 2\nStundenthema: LZK 1\n---\n", encoding="utf-8")

    repo = FileSystemLessonRepository()
    lesson = repo.load_lesson_yaml(lesson_path)
    lesson.data["Kompetenzhorizont"] = "[[KH-Informationen_und_Daten]]"
    repo.save_lesson_yaml(lesson)

    text = lesson_path.read_text(encoding="utf-8")
    assert 'Kompetenzhorizont: "[[KH-Informationen_und_Daten]]"' in text


def test_repeated_yaml_save_normalizes_to_single_frontmatter_gap(tmp_path):
    lesson_path = tmp_path / "lzk.md"
    lesson_path.write_text(
        "---\nStundentyp: LZK\nDauer: 2\nStundenthema: LZK 1\n---\n\n\n\n# Inhalt\n",
        encoding="utf-8",
    )

    repo = FileSystemLessonRepository()
    lesson = repo.load_lesson_yaml(lesson_path)
    lesson.data["Kompetenzhorizont"] = "[[KH-Informationen_und_Daten]]"
    repo.save_lesson_yaml(lesson)

    lesson = repo.load_lesson_yaml(lesson_path)
    lesson.data["Kompetenzhorizont"] = "[[KH-Informationen_und_Daten_2]]"
    repo.save_lesson_yaml(lesson)

    text = lesson_path.read_text(encoding="utf-8")
    assert "---\n\n\n" not in text
    assert "---\n\n# Inhalt\n" in text
