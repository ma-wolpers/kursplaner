"""Tests für die Migration ``Oberthema`` Skalar → kanonische Liste (synthetische Dateien)."""

from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.yaml_registry import RawYamlBlock
from kursplaner.core.usecases.lesson_edit_usecase import LessonEditUseCase
from kursplaner.core.usecases.migrate_oberthema_list_usecase import MigrateOberthemaListUseCase
from kursplaner.infrastructure.repositories.lesson_repository import FileSystemLessonRepository
from tests.day_column_factory import make_day_column


def _lesson(tmp_path: Path, stem: str, oberthema_lines: str, stundentyp: str = "Unterricht") -> Path:
    path = tmp_path / f"{stem}.md"
    path.write_text(
        f"---\nStundentyp: {stundentyp}\nDauer: 2\nStundenthema: {stem}\n{oberthema_lines}---\n\nBody {stem}\n",
        encoding="utf-8",
    )
    return path


def _table(tmp_path: Path) -> PlanTableData:
    return PlanTableData(
        markdown_path=tmp_path / "Plan.md",
        headers=["Datum", "Inhalt"],
        rows=[],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=True,
        metadata={"Lerngruppe": "[[11.1]]"},
    )


def _run(tmp_path: Path, paths: list[Path]):
    repo = FileSystemLessonRepository()
    days = [make_day_column(row_index=index, link=path) for index, path in enumerate(paths)]
    result = MigrateOberthemaListUseCase(lesson_repo=repo).execute(table=_table(tmp_path), day_columns=days)
    return repo, result


def test_lzk_legacy_scalar_is_migrated_to_canonical_list(tmp_path):
    lzk = _lesson(tmp_path, "aaa111", "Oberthema: Potenzen\n", stundentyp="LZK")

    repo, result = _run(tmp_path, [lzk])

    assert result.migrated_files == (lzk.resolve(),)
    assert result.problems == ()
    assert repo.load_raw_lesson_frontmatter(lzk)["Oberthema"] == ["[[11.1 Potenzen]]"]
    assert lzk.read_text(encoding="utf-8").rstrip().endswith("Body aaa111")


def test_unterricht_and_hospitation_single_values_are_left_untouched(tmp_path):
    plain = _lesson(tmp_path, "bbb222", "Oberthema: Potenzen\n")
    linked = _lesson(tmp_path, "bbb333", 'Oberthema: "[[11.1 Potenzen]]"\n', stundentyp="Hospitation")
    empty = _lesson(tmp_path, "bbb444", "Oberthema: \n")
    before = {path: path.read_text(encoding="utf-8") for path in (plain, linked, empty)}

    _repo, result = _run(tmp_path, [plain, linked, empty])

    assert result.migrated_files == ()
    assert result.problems == ()
    assert all(path.read_text(encoding="utf-8") == text for path, text in before.items())


def test_unterricht_list_with_one_entry_is_restored_to_single_value(tmp_path):
    """Korrigiert Dateien, die eine frühere, zu weit gefasste Migration auf die Liste umgestellt hat."""
    unit = _lesson(tmp_path, "ccc333", 'Oberthema:\n  - "[[11.1 Potenzen]]"\n')

    repo, result = _run(tmp_path, [unit])

    assert result.migrated_files == (unit.resolve(),)
    assert repo.load_raw_lesson_frontmatter(unit)["Oberthema"] == "[[11.1 Potenzen]]"


def test_lzk_empty_value_stays_empty_list(tmp_path):
    empty = _lesson(tmp_path, "ccc444", "Oberthema: \n", stundentyp="LZK")

    repo, result = _run(tmp_path, [empty])

    assert result.migrated_files == ()
    assert repo.load_raw_lesson_frontmatter(empty)["Oberthema"] == []


def test_list_with_duplicates_and_plain_entries_is_normalized(tmp_path):
    lzk = _lesson(
        tmp_path,
        "ddd444",
        'Oberthema:\n  - "Potenzen"\n  - "[[11.1 Potenzen]]"\n  - "Exponential"\n',
        stundentyp="LZK",
    )

    repo, result = _run(tmp_path, [lzk])

    assert result.migrated_files == (lzk.resolve(),)
    assert repo.load_raw_lesson_frontmatter(lzk)["Oberthema"] == ["[[11.1 Potenzen]]", "[[11.1 Exponential]]"]


def test_already_canonical_file_is_not_written(tmp_path):
    canonical = _lesson(tmp_path, "eee555", 'Oberthema:\n  - "[[11.1 Potenzen]]"\n', stundentyp="LZK")
    before = canonical.stat().st_mtime_ns

    _repo, result = _run(tmp_path, [canonical])

    assert result.migrated_files == ()
    assert canonical.stat().st_mtime_ns == before


def test_unsupported_block_is_left_unchanged_and_reported(tmp_path):
    invalid = _lesson(tmp_path, "fff666", "Oberthema:\n  foo: bar\n")
    before = invalid.read_text(encoding="utf-8")

    repo, result = _run(tmp_path, [invalid])

    assert result.migrated_files == ()
    assert [problem.lesson_path for problem in result.problems] == [invalid.resolve()]
    assert invalid.read_text(encoding="utf-8") == before
    assert repo.load_raw_lesson_frontmatter(invalid)["Oberthema"] == RawYamlBlock(("  foo: bar",))


def test_multiple_topics_on_non_lzk_are_reported_not_truncated(tmp_path):
    unit = _lesson(tmp_path, "ggg777", 'Oberthema:\n  - "A"\n  - "B"\n')
    before = unit.read_text(encoding="utf-8")

    _repo, result = _run(tmp_path, [unit])

    assert result.migrated_files == ()
    assert "mehrere Oberthemen" in result.problems[0].reason
    assert unit.read_text(encoding="utf-8") == before


def test_load_reports_problem_then_normal_write_keeps_invalid_oberthema(tmp_path):
    """Regression: Laden meldet das Problem → ein normaler Schreibvorgang verändert
    das ungültige Oberthema nicht still zu ``[]``."""
    invalid = _lesson(tmp_path, "hhh888", "Oberthema:\n  foo: bar\n")

    repo, result = _run(tmp_path, [invalid])
    assert result.problems

    LessonEditUseCase(repo).set_lesson_field(invalid, "Stundenthema", "Neuer Titel")

    raw = repo.load_raw_lesson_frontmatter(invalid)
    assert raw["Stundenthema"] == "Neuer Titel"
    assert raw["Oberthema"] == RawYamlBlock(("  foo: bar",))
