import pytest

from kursplaner.core.domain.achievement_grade_rules import (
    GradeRequirement,
    compute_grade_group_progress,
    parse_grade_requirements,
)


def test_parse_grade_requirements_accepts_empty_lists_per_subject():
    raw = {"Pädagogik": [], "Mathematik": []}
    result = parse_grade_requirements(raw)
    assert result == {"Pädagogik": (), "Mathematik": ()}


def test_parse_grade_requirements_parses_valid_entries():
    raw = {
        "Pädagogik": [
            {"label": "5./6.", "grade_min": 5, "grade_max": 6, "min_count": 1},
        ]
    }
    result = parse_grade_requirements(raw)
    assert result["Pädagogik"] == (GradeRequirement(label="5./6.", grade_min=5, grade_max=6, min_count=1),)


def test_parse_grade_requirements_rejects_non_dict_root():
    with pytest.raises(ValueError):
        parse_grade_requirements([])


def test_parse_grade_requirements_rejects_non_list_subject_value():
    with pytest.raises(ValueError):
        parse_grade_requirements({"Pädagogik": "nicht eine Liste"})


def test_parse_grade_requirements_rejects_incomplete_entry():
    with pytest.raises(ValueError):
        parse_grade_requirements({"Pädagogik": [{"label": "5./6.", "grade_min": 5}]})


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
