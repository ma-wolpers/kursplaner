from __future__ import annotations

from kursplaner.core.domain.grade_groups import GRADE_GROUPS, expand_grade_selection


def test_group_boundaries_are_contiguous_and_non_overlapping():
    grades = sorted(g for group in GRADE_GROUPS for g in group.grades())
    assert grades == list(range(1, 14))


def test_gs_sek1_boundary():
    gs = next(g for g in GRADE_GROUPS if g.key == "gs")
    sek1 = next(g for g in GRADE_GROUPS if g.key == "sek1")
    assert 4 in gs.grades()
    assert 4 not in sek1.grades()
    assert 5 in sek1.grades()
    assert 5 not in gs.grades()


def test_sek1_sek2_boundary():
    sek1 = next(g for g in GRADE_GROUPS if g.key == "sek1")
    sek2 = next(g for g in GRADE_GROUPS if g.key == "sek2")
    assert 10 in sek1.grades()
    assert 10 not in sek2.grades()
    assert 11 in sek2.grades()
    assert 11 not in sek1.grades()


def test_expand_grade_selection_with_full_group():
    result = expand_grade_selection(fully_selected_group_keys=frozenset({"sek2"}), individually_selected_grades=frozenset())
    assert result == frozenset({11, 12, 13})


def test_expand_grade_selection_mixes_group_and_individual():
    result = expand_grade_selection(
        fully_selected_group_keys=frozenset({"sek2"}), individually_selected_grades=frozenset({8})
    )
    assert result == frozenset({8, 11, 12, 13})


def test_expand_grade_selection_empty():
    result = expand_grade_selection(fully_selected_group_keys=frozenset(), individually_selected_grades=frozenset())
    assert result == frozenset()


def test_expand_grade_selection_ignores_unknown_group_key():
    result = expand_grade_selection(
        fully_selected_group_keys=frozenset({"unknown"}), individually_selected_grades=frozenset({7})
    )
    assert result == frozenset({7})
