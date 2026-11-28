"""UB-Dateien: Schreibwege ändern nur ihre Felder, eigener Text und Reflexion bleiben (synthetisch)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kursplaner.core.domain.list_cell_text import ListFieldViolationError
from kursplaner.core.domain.unterrichtsbesuch_policy import (
    UB_RESOURCES_FIELD,
    UB_STEPS_FIELD,
    ub_development_lists,
    ub_link_stem,
    with_ub_development_list,
)
from kursplaner.core.usecases.sync_ub_development_focus_usecase import SyncUbDevelopmentFocusUseCase
from kursplaner.core.usecases.ub_files import existing_ub_path, load_development_lists
from kursplaner.core.usecases.ub_markdown_sections import new_ub_body, parse_reflection
from kursplaner.infrastructure.repositories.lesson_repository import FileSystemLessonRepository
from kursplaner.infrastructure.repositories.ub_repository import FileSystemUbRepository

YAML = {"Bereich": ["Pädagogik"], "Langentwurf": False, "Beobachtungsschwerpunkt": "", "Einheit": "[[u]]"}
CUSTOM = "\n## Eigene Notizen\n\nNicht verlieren!\n"


def test_development_lists_live_in_frontmatter_and_follow_list_invariant():
    ub_yaml = with_ub_development_list(YAML, UB_STEPS_FIELD, ["Neu 1", "Neu 2"])

    assert ub_development_lists(ub_yaml) == (["Neu 1", "Neu 2"], [])
    assert ub_development_lists(YAML) == ([], [])
    with pytest.raises(ListFieldViolationError):
        with_ub_development_list(YAML, UB_RESOURCES_FIELD, ["---"])
    with pytest.raises(ListFieldViolationError):
        ub_development_lists({UB_STEPS_FIELD: "Einzeltext"})
    with pytest.raises(ValueError):
        with_ub_development_list(YAML, "Bereich", ["x"])


def test_ub_link_stem_and_path_come_from_one_place(tmp_path: Path):
    repo = FileSystemUbRepository()
    assert ub_link_stem({"Unterrichtsbesuch": "[[ub 26-11-02]]"}) == "ub 26-11-02"
    assert ub_link_stem({}) == ""
    path = repo.ub_markdown_path(tmp_path, "ub 26-11-02")
    assert path.name == "ub 26-11-02.md"
    assert existing_ub_path(repo, tmp_path, {"Unterrichtsbesuch": "[[ub 26-11-02]]"}) is None
    ub_yaml = with_ub_development_list(with_ub_development_list(YAML, UB_STEPS_FIELD, ["S"]), UB_RESOURCES_FIELD, ["Q"])
    repo.save_ub_markdown(path, ub_yaml, new_ub_body("R"))
    assert existing_ub_path(repo, tmp_path, {"Unterrichtsbesuch": "[[ub 26-11-02]]"}) == path
    assert load_development_lists(repo, tmp_path, {"Unterrichtsbesuch": "[[ub 26-11-02]]"}) == (["S"], ["Q"])


def test_grid_sync_replaces_only_one_list(tmp_path: Path):
    ub_repo = FileSystemUbRepository()
    ub_path = ub_repo.ub_markdown_path(tmp_path, "ub 26-11-02")
    ub_yaml = with_ub_development_list(YAML, UB_RESOURCES_FIELD, ["Bleibt"])
    ub_repo.save_ub_markdown(ub_path, ub_yaml, new_ub_body("Meine Reflexion") + CUSTOM)
    lessons = tmp_path / "Kurs" / "Einheiten"
    lessons.mkdir(parents=True)
    lesson = lessons / "u.md"
    lesson.write_text(
        '---\nStundentyp: Unterricht\nDauer: 2\nStundenthema: X\nUnterrichtsbesuch: "[[ub 26-11-02]]"\n---\n',
        encoding="utf-8",
    )
    sync = SyncUbDevelopmentFocusUseCase(FileSystemLessonRepository(), ub_repo)

    assert sync.save_list(workspace_root=tmp_path, lesson_path=lesson, field=UB_STEPS_FIELD, entries=["Neu"])

    saved_yaml, body = ub_repo.load_ub_markdown(ub_path)
    assert parse_reflection(body) == "Meine Reflexion" and "Nicht verlieren!" in body
    assert ub_development_lists(saved_yaml) == (["Neu"], ["Bleibt"])
    assert saved_yaml["Einheit"] == "[[u]]"
