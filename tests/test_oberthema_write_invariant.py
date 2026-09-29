"""Regressionstests: ein ungültiges `Oberthema` wird nie still überschrieben.

Arbeitet mit dem echten `FileSystemLessonRepository` auf synthetischen Dateien
in `tmp_path`, damit Parser, Kanonisierung und Schreibgrenze zusammen geprüft
werden.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from kursplaner.core.domain.lesson_yaml_policy import canonicalize_lesson_yaml
from kursplaner.core.domain.oberthema_values import OberthemaRepairRequired
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.yaml_registry import RawYamlBlock
from kursplaner.core.usecases.lesson_edit_usecase import LessonEditUseCase
from kursplaner.core.usecases.save_cell_value_usecase import SaveCellValueUseCase
from kursplaner.infrastructure.repositories.lesson_repository import FileSystemLessonRepository

_INVALID_LESSON = """---
Stundentyp: Unterricht
Dauer: 2
Stundenthema: Testeinheit
Oberthema:
  foo: bar
  baz: qux
Stundenziel: Ziel
---

Body bleibt erhalten.
"""


def _write_invalid_lesson(tmp_path: Path) -> Path:
    path = tmp_path / "abc123.md"
    path.write_text(_INVALID_LESSON, encoding="utf-8")
    return path


def _oberthema_block(text: str) -> list[str]:
    lines = text.splitlines()
    start = lines.index("Oberthema:")
    block = [lines[start]]
    for line in lines[start + 1 :]:
        if not line.startswith(" "):
            break
        block.append(line)
    return block


def test_parser_preserves_nested_block_as_raw_value(tmp_path):
    path = _write_invalid_lesson(tmp_path)
    repo = FileSystemLessonRepository()

    raw = repo.load_raw_lesson_frontmatter(path)
    loaded = repo.load_lesson_yaml(path)

    assert raw["Oberthema"] == RawYamlBlock(("  foo: bar", "  baz: qux"))
    assert loaded.data["Oberthema"] == RawYamlBlock(("  foo: bar", "  baz: qux"))


def test_canonicalize_passes_invalid_oberthema_through_unchanged():
    block = RawYamlBlock(("  foo: bar",))
    normalized = canonicalize_lesson_yaml({"Stundentyp": "Unterricht", "Stundenthema": "X", "Oberthema": block})

    assert normalized["Oberthema"] is block


def test_normal_write_of_other_field_keeps_invalid_oberthema_unchanged(tmp_path):
    path = _write_invalid_lesson(tmp_path)
    repo = FileSystemLessonRepository()

    lesson = repo.load_lesson_yaml(path)
    lesson.data["Stundenziel"] = "Neues Ziel"
    repo.save_lesson_yaml(lesson)

    text = path.read_text(encoding="utf-8")
    assert _oberthema_block(text) == ["Oberthema:", "  foo: bar", "  baz: qux"]
    assert "Stundenziel: Neues Ziel" in text
    assert "Body bleibt erhalten." in text


def test_normal_write_replacing_invalid_oberthema_with_empty_list_is_rejected(tmp_path):
    path = _write_invalid_lesson(tmp_path)
    before = path.read_text(encoding="utf-8")
    repo = FileSystemLessonRepository()

    lesson = repo.load_lesson_yaml(path)
    lesson.data["Oberthema"] = []
    with pytest.raises(OberthemaRepairRequired):
        repo.save_lesson_yaml(lesson)

    assert path.read_text(encoding="utf-8") == before


def test_explicit_correction_writes_single_value_for_unterricht(tmp_path):
    path = _write_invalid_lesson(tmp_path)
    repo = FileSystemLessonRepository()

    LessonEditUseCase(repo).set_lesson_oberthemen(path, ["Potenzen", "Potenzen"], "[[11.1]]")

    # Unterricht: Einzelwert wie eingegeben, keine Listenform.
    assert repo.load_raw_lesson_frontmatter(path)["Oberthema"] == "Potenzen"


def test_explicit_correction_rejects_multiple_topics_for_unterricht(tmp_path):
    path = _write_invalid_lesson(tmp_path)
    repo = FileSystemLessonRepository()

    with pytest.raises(RuntimeError, match="Nur eine LZK"):
        LessonEditUseCase(repo).set_lesson_oberthemen(path, ["A", "B"], "11.1")


class _PlanRepoStub:
    def save_plan_table(self, _table: PlanTableData) -> None:
        return None


class _RowDisplayModeStub:
    @staticmethod
    def list_like_fields() -> set[str]:
        return set()


def _save_cell_usecase(repo: FileSystemLessonRepository) -> SaveCellValueUseCase:
    return SaveCellValueUseCase(
        lesson_edit=LessonEditUseCase(repo),
        plan_repo=cast(Any, _PlanRepoStub()),
        lesson_transfer=cast(Any, object()),
        rename_linked_file_for_row=cast(Any, object()),
        row_display_mode_usecase=cast(Any, _RowDisplayModeStub()),
    )


def _table(tmp_path: Path) -> PlanTableData:
    return PlanTableData(
        markdown_path=tmp_path / "Plan.md",
        headers=["Datum", "Inhalt"],
        rows=[["01-09-26", "[[abc123]]"]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=True,
        metadata={"Lerngruppe": "[[11.1]]"},
    )


def _execute(usecase: SaveCellValueUseCase, table: PlanTableData, field_key: str, value: str, path: Path):
    return usecase.execute(
        table=table,
        row_index=0,
        field_key=field_key,
        value=value,
        lesson_path=path,
        list_entries=None,
        should_rename_topic=False,
        desired_stem="",
        allow_yaml_save=True,
        allow_rename=False,
        allow_plan_save_for_rename=False,
    )


def test_cell_save_of_other_field_does_not_touch_invalid_oberthema(tmp_path):
    path = _write_invalid_lesson(tmp_path)
    repo = FileSystemLessonRepository()

    result = _execute(_save_cell_usecase(repo), _table(tmp_path), "Stundenziel", "Anderes Ziel", path)

    assert result.proceed
    assert repo.load_raw_lesson_frontmatter(path)["Oberthema"] == RawYamlBlock(("  foo: bar", "  baz: qux"))


def test_cell_save_keeping_warning_marker_writes_nothing(tmp_path):
    path = _write_invalid_lesson(tmp_path)
    before = path.read_text(encoding="utf-8")
    repo = FileSystemLessonRepository()

    result = _execute(_save_cell_usecase(repo), _table(tmp_path), "Oberthema", "⚠ ungültiges Oberthema", path)

    assert result.proceed
    assert path.read_text(encoding="utf-8") == before


def test_cell_save_of_oberthema_is_explicit_repair(tmp_path):
    path = _write_invalid_lesson(tmp_path)
    repo = FileSystemLessonRepository()

    result = _execute(_save_cell_usecase(repo), _table(tmp_path), "Oberthema", "Potenzen |  | Potenzen", path)

    assert result.proceed
    assert repo.load_raw_lesson_frontmatter(path)["Oberthema"] == "Potenzen"
