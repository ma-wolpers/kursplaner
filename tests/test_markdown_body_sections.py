"""Body-Abschnitte mit byte-genauem Frontmatter, Datei-Zugriff, Rollback und Feld-Schreibweg (synthetisch)."""

from __future__ import annotations

import pytest

from kursplaner.core.domain.lesson_yaml_policy import lesson_list_entries
from kursplaner.core.domain.markdown_body_sections import extract_body_section, replace_body_section
from kursplaner.core.domain.yaml_registry import split_frontmatter_block
from kursplaner.core.usecases.command_executor_usecase import CommandExecutorUseCase
from kursplaner.core.usecases.history_usecase import HistoryUseCase
from kursplaner.core.usecases.lesson_edit_usecase import LessonEditUseCase
from kursplaner.core.usecases.tracked_write_usecase import TrackedWriteUseCase
from kursplaner.infrastructure.repositories.command_repository import FileSystemCommandRepository
from kursplaner.infrastructure.repositories.lesson_repository import FileSystemLessonRepository
from kursplaner.infrastructure.repositories.markdown_section_files import write_body_section

DOC = "---\nStundentyp: Unterricht\n## Ideen: kein Abschnitt\ndocument_type: kurzentwurf\n---\n\n# Verlauf\n\nText\n"


def test_split_is_lossless_and_without_frontmatter_everything_is_body():
    head, body = split_frontmatter_block(DOC)
    assert head + body == DOC and head.endswith("kurzentwurf\n---")
    assert split_frontmatter_block("nur Text") == ("", "nur Text")


def test_replace_appends_replaces_and_removes_only_in_the_body():
    added = replace_body_section(DOC, "Ideen", ["Pizza"])
    assert added.startswith(DOC.rstrip("\n")) and added.endswith("## Ideen\n\nPizza\n")
    assert extract_body_section(added, "Ideen") == ("Pizza",)
    replaced = replace_body_section(added, "Ideen", ["Plakat", "Rätsel"])
    assert replaced.count("\n## Ideen\n") == 1 and extract_body_section(replaced, "Ideen") == ("Plakat", "Rätsel")
    assert replace_body_section(replaced, "Ideen", []) == DOC.rstrip("\n") + "\n"
    assert extract_body_section(DOC, "Ideen") is None  # Frontmatter-Zeile ist keine Überschrift


def test_file_write_happens_only_on_change(tmp_path):
    path = tmp_path / "a.md"
    path.write_text(DOC, encoding="utf-8")
    assert write_body_section(path, "Ideen", ["x"]) is True
    assert write_body_section(path, "Ideen", ["x"]) is False


def test_tracked_file_action_rolls_back_every_file_on_error(tmp_path):
    first, second = tmp_path / "a.md", tmp_path / "b.md"
    first.write_text("A", encoding="utf-8")
    second.write_text("B", encoding="utf-8")
    history = HistoryUseCase(CommandExecutorUseCase(command_repo=FileSystemCommandRepository()))

    def action():
        first.write_text("A2", encoding="utf-8")
        raise OSError("kaputt")

    with pytest.raises(OSError):
        TrackedWriteUseCase(history).run_tracked_file_action(label="x", paths=[first, second], action=action)
    assert (first.read_text(encoding="utf-8"), second.read_text(encoding="utf-8")) == ("A", "B")
    assert history.undo_stack == []


def test_lesson_list_entries_reads_canonical_lists_strictly():
    assert lesson_list_entries({"Kompetenzen": ["K1"]}, "Kompetenzen") == ("K1",)
    assert lesson_list_entries({}, "Material") == ()
    with pytest.raises(TypeError):
        lesson_list_entries({"Kompetenzen": "K1"}, "Kompetenzen")


def test_set_lesson_fields_writes_together_and_checks_the_type(tmp_path):
    folder = tmp_path / "Einheiten"
    folder.mkdir()
    path = folder / "u.ebw"
    path.write_text(DOC.replace("## Ideen: kein Abschnitt\n", "Dauer: 2\nStundenthema: X\n"), encoding="utf-8")
    edit = LessonEditUseCase(FileSystemLessonRepository())
    edit.set_lesson_fields(path, {"Stundenziel": "Z", "Teilziele": ["T"]}, require_type="Unterricht")
    text = path.read_text(encoding="utf-8")
    assert "Stundenziel: Z" in text and "document_type: kurzentwurf" in text and text.endswith("# Verlauf\n\nText\n")
    with pytest.raises(ValueError, match="LZK"):
        edit.set_lesson_fields(path, {"Stundenziel": "Y"}, require_type="LZK")
