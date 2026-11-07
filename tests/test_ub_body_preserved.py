"""UB-Dateien: Schreibwege ändern nur ihre Abschnitte, eigener Text und Reflexion bleiben (synthetisch)."""

from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.unterrichtsbesuch_policy import ub_link_stem
from kursplaner.core.usecases.sync_ub_development_focus_usecase import SyncUbDevelopmentFocusUseCase
from kursplaner.core.usecases.ub_files import existing_ub_path, load_development_lists
from kursplaner.core.usecases.ub_markdown_sections import (
    new_ub_body,
    parse_development_lists,
    parse_reflection,
    with_development_lists,
)
from kursplaner.infrastructure.repositories.lesson_repository import FileSystemLessonRepository
from kursplaner.infrastructure.repositories.ub_repository import FileSystemUbRepository

YAML = {"Bereich": ["Pädagogik"], "Langentwurf": False, "Beobachtungsschwerpunkt": "", "Einheit": "[[u]]"}
CUSTOM = "\n## Eigene Notizen\n\nNicht verlieren!\n"


def test_new_body_and_list_replacement_keep_everything_else():
    body = new_ub_body("Gut gelaufen", ["Schritt"], []) + CUSTOM
    updated = with_development_lists(body, ["Neu 1", "Neu 2"], ["Ressource"])
    assert parse_reflection(updated) == "Gut gelaufen"
    assert parse_development_lists(updated) == (["Neu 1", "Neu 2"], ["Ressource"])
    assert "## Eigene Notizen\n\nNicht verlieren!" in updated


def test_empty_lists_keep_their_heading_with_a_placeholder():
    body = with_development_lists(new_ub_body(), [], [])
    assert "## Professionalisierungsschritte\n\n- " in body and parse_development_lists(body) == ([], [])


def test_ub_link_stem_and_path_come_from_one_place(tmp_path: Path):
    repo = FileSystemUbRepository()
    assert ub_link_stem({"Unterrichtsbesuch": "[[ub 26-11-02]]"}) == "ub 26-11-02"
    assert ub_link_stem({}) == ""
    path = repo.ub_markdown_path(tmp_path, "ub 26-11-02")
    assert path.name == "ub 26-11-02.md"
    assert existing_ub_path(repo, tmp_path, {"Unterrichtsbesuch": "[[ub 26-11-02]]"}) is None
    repo.save_ub_markdown(path, YAML, new_ub_body("R", ["S"], ["Q"]))
    assert existing_ub_path(repo, tmp_path, {"Unterrichtsbesuch": "[[ub 26-11-02]]"}) == path
    assert load_development_lists(repo, tmp_path, {"Unterrichtsbesuch": "[[ub 26-11-02]]"}) == (["S"], ["Q"])


def test_grid_sync_replaces_only_the_lists(tmp_path: Path):
    ub_repo = FileSystemUbRepository()
    ub_path = ub_repo.ub_markdown_path(tmp_path, "ub 26-11-02")
    ub_repo.save_ub_markdown(ub_path, YAML, new_ub_body("Meine Reflexion", ["Alt"], []) + CUSTOM)
    lessons = tmp_path / "Kurs" / "Einheiten"
    lessons.mkdir(parents=True)
    lesson = lessons / "u.md"
    lesson.write_text(
        '---\nStundentyp: Unterricht\nDauer: 2\nStundenthema: X\nUnterrichtsbesuch: "[[ub 26-11-02]]"\n---\n',
        encoding="utf-8",
    )
    sync = SyncUbDevelopmentFocusUseCase(FileSystemLessonRepository(), ub_repo)
    assert sync.save(
        workspace_root=tmp_path, lesson_path=lesson, professional_steps_text="Neu", usable_resources_text="- R"
    )
    _yaml, body = ub_repo.load_ub_markdown(ub_path)
    assert parse_reflection(body) == "Meine Reflexion" and "Nicht verlieren!" in body
    assert sync.load(workspace_root=tmp_path, lesson_path=lesson).professional_steps == ["Neu"]
