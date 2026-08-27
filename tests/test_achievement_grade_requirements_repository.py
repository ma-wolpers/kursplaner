import json

from kursplaner.core.domain.achievement_grade_rules import GradeRequirement
from kursplaner.core.usecases.query_ub_achievements_usecase import QueryUbAchievementsUseCase
from kursplaner.infrastructure.repositories.achievement_grade_requirements_repository import (
    FileSystemAchievementGradeRequirementsRepository,
)


def test_default_resource_file_keys_match_domain_order():
    """Verhindert stillen Drift zwischen der JSON-Ressource und der massgeblichen Fachliste."""
    repo = FileSystemAchievementGradeRequirementsRepository()
    requirements = repo.load_requirements()
    assert set(requirements.keys()) == set(QueryUbAchievementsUseCase.DOMAIN_ORDER)


def test_default_resource_file_ships_with_no_configured_requirements():
    """Solange keine Fach-Vorgaben final geklärt sind, darf die Ressource keine echten Werte enthalten."""
    repo = FileSystemAchievementGradeRequirementsRepository()
    requirements = repo.load_requirements()
    assert all(entries == () for entries in requirements.values())


def test_load_requirements_reads_and_parses_custom_file(tmp_path, monkeypatch):
    custom_path = tmp_path / "grade_requirements.json"
    custom_path.write_text(
        json.dumps({"Pädagogik": [{"label": "5./6.", "grade_min": 5, "grade_max": 6, "min_count": 1}]}),
        encoding="utf-8",
    )
    repo = FileSystemAchievementGradeRequirementsRepository()
    monkeypatch.setattr(FileSystemAchievementGradeRequirementsRepository, "_RESOURCE_PATH", custom_path)

    requirements = repo.load_requirements()

    assert requirements == {
        "Pädagogik": (GradeRequirement(label="5./6.", grade_min=5, grade_max=6, min_count=1),)
    }


def test_load_requirements_returns_empty_dict_when_file_missing(tmp_path, monkeypatch):
    repo = FileSystemAchievementGradeRequirementsRepository()
    monkeypatch.setattr(FileSystemAchievementGradeRequirementsRepository, "_RESOURCE_PATH", tmp_path / "missing.json")

    assert repo.load_requirements() == {}
