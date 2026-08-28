import json

import pytest

from kursplaner.core.domain.achievement_requirements import AchievementRequirementsParseError, AchievementTargets
from kursplaner.core.usecases.query_ub_achievements_usecase import QueryUbAchievementsUseCase
from kursplaner.infrastructure.repositories.achievement_requirements_repository import (
    FileSystemAchievementRequirementsRepository,
)


def test_default_resource_file_keys_match_domain_order():
    """Verhindert stillen Drift zwischen der JSON-Ressource und der massgeblichen Fachliste."""
    repo = FileSystemAchievementRequirementsRepository()
    requirements = repo.load_requirements()
    assert set(requirements.keys()) == set(QueryUbAchievementsUseCase.DOMAIN_ORDER)


def test_default_resource_file_has_production_targets():
    """Die ausgelieferte Datei enthaelt die tatsaechlich gueltigen Schwellenwerte, keine Platzhalter."""
    repo = FileSystemAchievementRequirementsRepository()
    requirements = repo.load_requirements()

    assert requirements["Pädagogik"].targets == AchievementTargets(half=5, full=9, ubplus=None, bub=2)
    assert requirements["Mathematik"].targets == AchievementTargets(half=4, full=8, ubplus=1, bub=1)
    assert requirements["Informatik"].targets == AchievementTargets(half=4, full=8, ubplus=1, bub=1)
    assert requirements["Darstellendes Spiel"].targets == AchievementTargets(half=4, full=8, ubplus=None, bub=None)


def test_default_resource_file_has_paedagogik_grade_groups_configured():
    repo = FileSystemAchievementRequirementsRepository()
    requirements = repo.load_requirements()

    labels = [g.label for g in requirements["Pädagogik"].grade_groups]
    assert labels == ["5./6.", "7.-10.", "11.-13."]
    assert all(g.min_count == 1 for g in requirements["Pädagogik"].grade_groups)


def test_default_resource_file_has_no_grade_groups_for_other_subjects():
    repo = FileSystemAchievementRequirementsRepository()
    requirements = repo.load_requirements()

    for subject in ("Mathematik", "Informatik", "Darstellendes Spiel"):
        assert requirements[subject].grade_groups == ()


def test_load_requirements_reads_and_parses_custom_file(tmp_path, monkeypatch):
    custom_path = tmp_path / "requirements.json"
    custom_path.write_text(
        json.dumps({"Pädagogik": {"targets": {"half": 5, "full": 9}, "grade_groups": []}}),
        encoding="utf-8",
    )
    repo = FileSystemAchievementRequirementsRepository()
    monkeypatch.setattr(FileSystemAchievementRequirementsRepository, "_RESOURCE_PATH", custom_path)

    requirements = repo.load_requirements()

    assert requirements["Pädagogik"].targets == AchievementTargets(half=5, full=9, ubplus=None, bub=None)


def test_load_requirements_raises_when_file_missing(tmp_path, monkeypatch):
    repo = FileSystemAchievementRequirementsRepository()
    monkeypatch.setattr(FileSystemAchievementRequirementsRepository, "_RESOURCE_PATH", tmp_path / "missing.json")

    with pytest.raises(AchievementRequirementsParseError):
        repo.load_requirements()
