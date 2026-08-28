import pytest

from kursplaner.core.domain.achievement_requirements import (
    AchievementRequirementsParseError,
    AchievementTargets,
    GradeRequirement,
    compute_grade_group_progress,
    parse_achievement_requirements,
)


def _valid_raw() -> dict:
    return {
        "schema_version": 1,
        "Pädagogik": {
            "targets": {"half": 5, "full": 9, "bub": 2},
            "grade_groups": [
                {"label": "5./6.", "grade_min": 5, "grade_max": 6, "min_count": 1},
            ],
        },
        "Mathematik": {"targets": {"half": 4, "full": 8, "ubplus": 1, "bub": 1}, "grade_groups": []},
    }


def test_parse_achievement_requirements_parses_full_valid_configuration():
    result = parse_achievement_requirements(_valid_raw())

    assert result["Pädagogik"].targets == AchievementTargets(half=5, full=9, ubplus=None, bub=2)
    assert result["Pädagogik"].grade_groups == (GradeRequirement(label="5./6.", grade_min=5, grade_max=6, min_count=1),)
    assert result["Mathematik"].targets == AchievementTargets(half=4, full=8, ubplus=1, bub=1)
    assert result["Mathematik"].grade_groups == ()


def test_parse_achievement_requirements_ignores_schema_version_key():
    result = parse_achievement_requirements(_valid_raw())
    assert "schema_version" not in result


def test_parse_achievement_requirements_subject_without_ubplus_or_bub():
    raw = {"Darstellendes Spiel": {"targets": {"half": 4, "full": 8}, "grade_groups": []}}
    result = parse_achievement_requirements(raw)
    assert result["Darstellendes Spiel"].targets == AchievementTargets(half=4, full=8, ubplus=None, bub=None)


def test_parse_achievement_requirements_rejects_non_dict_root():
    with pytest.raises(AchievementRequirementsParseError):
        parse_achievement_requirements([])


def test_parse_achievement_requirements_rejects_unknown_target_key():
    raw = {"Pädagogik": {"targets": {"half": 5, "full": 9, "unknown": 1}, "grade_groups": []}}
    with pytest.raises(AchievementRequirementsParseError):
        parse_achievement_requirements(raw)


def test_parse_achievement_requirements_rejects_missing_half():
    raw = {"Pädagogik": {"targets": {"full": 9}, "grade_groups": []}}
    with pytest.raises(AchievementRequirementsParseError):
        parse_achievement_requirements(raw)


def test_parse_achievement_requirements_rejects_missing_full():
    raw = {"Pädagogik": {"targets": {"half": 5}, "grade_groups": []}}
    with pytest.raises(AchievementRequirementsParseError):
        parse_achievement_requirements(raw)


def test_parse_achievement_requirements_rejects_non_positive_target_value():
    raw = {"Pädagogik": {"targets": {"half": 0, "full": 9}, "grade_groups": []}}
    with pytest.raises(AchievementRequirementsParseError):
        parse_achievement_requirements(raw)


def test_parse_achievement_requirements_rejects_non_int_target_value():
    raw = {"Pädagogik": {"targets": {"half": "fünf", "full": 9}, "grade_groups": []}}
    with pytest.raises(AchievementRequirementsParseError):
        parse_achievement_requirements(raw)


def test_parse_achievement_requirements_rejects_invalid_grade_group_entry():
    raw = {"Pädagogik": {"targets": {"half": 5, "full": 9}, "grade_groups": [{"label": "5./6.", "grade_min": 5}]}}
    with pytest.raises(AchievementRequirementsParseError):
        parse_achievement_requirements(raw)


def test_parse_achievement_requirements_rejects_missing_targets():
    raw = {"Pädagogik": {"grade_groups": []}}
    with pytest.raises(AchievementRequirementsParseError):
        parse_achievement_requirements(raw)


def test_compute_grade_group_progress_counts_matching_grades_only():
    requirements = (
        GradeRequirement(label="5./6.", grade_min=5, grade_max=6, min_count=1),
        GradeRequirement(label="7.-10.", grade_min=7, grade_max=10, min_count=2),
    )
    progress = compute_grade_group_progress(jahrgangsstufen=[5, 5, 8], requirements=requirements)

    assert [(p.label, p.current, p.target) for p in progress] == [
        ("5./6.", 2, 1),
        ("7.-10.", 1, 2),
    ]


def test_compute_grade_group_progress_returns_empty_list_for_no_requirements():
    assert compute_grade_group_progress(jahrgangsstufen=[5, 8], requirements=()) == []
