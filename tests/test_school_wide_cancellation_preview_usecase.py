from __future__ import annotations

from datetime import date
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.school_wide_cancellation import (
    CourseApplicationLedger,
    RowLocation,
    SchoolWideCancellationEntry,
    UnitMove,
    course_key_for_path,
)
from kursplaner.core.usecases.school_wide_cancellation_preview_usecase import SchoolWideCancellationPreviewUseCase

_HEADERS = ["Datum", "Inhalt", "Thema/Ausfall"]
_BASE_DIR = Path("courses")
_PATH_7A = _BASE_DIR / "7a" / "7a.md"
_PATH_11 = _BASE_DIR / "11.1" / "11.1.md"


def _table(path: Path, rows: list[list[str]], group_name: str = "") -> PlanTableData:
    return PlanTableData(
        markdown_path=path,
        headers=_HEADERS,
        rows=rows,
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={"Lerngruppe": f"[[{group_name}]]"} if group_name else {},
    )


class _FakePlanRepo:
    def __init__(self, courses: dict[Path, tuple[dict[str, str], PlanTableData]]) -> None:
        self._courses = courses

    def list_plan_markdown_files(self, base_dir: Path) -> list[Path]:
        return list(self._courses.keys())

    def load_plan_metadata(self, markdown_path: Path) -> dict[str, str]:
        return self._courses[markdown_path][0]

    def load_plan_table(self, markdown_path: Path) -> PlanTableData:
        return self._courses[markdown_path][1]


def _make_uc() -> tuple[SchoolWideCancellationPreviewUseCase, _FakePlanRepo]:
    courses = {
        _PATH_7A: (
            {"Stufe": "7"},
            _table(_PATH_7A, [["06-01-26", "[[abc]]", ""]], group_name="7a"),
        ),
        _PATH_11: (
            {"Stufe": "11"},
            _table(_PATH_11, [["06-01-26", "[[def]]", ""]], group_name="11.1"),
        ),
    }
    repo = _FakePlanRepo(courses)
    return SchoolWideCancellationPreviewUseCase(plan_repo=repo), repo


def test_filters_by_grade_level():
    uc, _repo = _make_uc()
    result = uc.compute(
        base_dir=_BASE_DIR,
        date_from=date(2026, 1, 6),
        date_to=date(2026, 1, 6),
        grade_levels=frozenset({7}),
    )
    assert {unit.markdown_path for unit in result.affected_units} == {_PATH_7A}


def test_no_grades_selected_matches_nothing():
    uc, _repo = _make_uc()
    result = uc.compute(
        base_dir=_BASE_DIR, date_from=date(2026, 1, 6), date_to=date(2026, 1, 6), grade_levels=frozenset()
    )
    assert result.affected_units == ()


def test_affected_course_count():
    uc, _repo = _make_uc()
    result = uc.compute(
        base_dir=_BASE_DIR,
        date_from=date(2026, 1, 6),
        date_to=date(2026, 1, 6),
        grade_levels=frozenset({7, 11}),
    )
    assert result.affected_course_count == 2


def test_date_outside_range_excluded():
    uc, _repo = _make_uc()
    result = uc.compute(
        base_dir=_BASE_DIR,
        date_from=date(2026, 2, 1),
        date_to=date(2026, 2, 28),
        grade_levels=frozenset({7}),
    )
    assert result.affected_units == ()


def test_detects_collision_with_other_active_entry():
    uc, _repo = _make_uc()
    other_entry = SchoolWideCancellationEntry(
        entry_id="other",
        reason="Pädagogischer Tag",
        date_from=date(2026, 1, 6),
        date_to=date(2026, 1, 6),
        grade_levels=frozenset({7}),
        created_at="",
        course_ledgers={
            course_key_for_path(_PATH_7A): CourseApplicationLedger(
                moves=(
                    UnitMove(
                        source=RowLocation(date="06-01-26", position_in_date=0), reference=None, target=None
                    ),
                )
            )
        },
    )
    result = uc.compute(
        base_dir=_BASE_DIR,
        date_from=date(2026, 1, 6),
        date_to=date(2026, 1, 6),
        grade_levels=frozenset({7}),
        other_entries=[other_entry],
    )
    unit = next(u for u in result.affected_units if u.markdown_path == _PATH_7A)
    assert unit.claimed_by_reason == "Pädagogischer Tag"


def test_exclude_entry_id_ignores_own_claims():
    uc, _repo = _make_uc()
    own_entry = SchoolWideCancellationEntry(
        entry_id="self",
        reason="Wandertag",
        date_from=date(2026, 1, 6),
        date_to=date(2026, 1, 6),
        grade_levels=frozenset({7}),
        created_at="",
        course_ledgers={
            course_key_for_path(_PATH_7A): CourseApplicationLedger(
                moves=(
                    UnitMove(
                        source=RowLocation(date="06-01-26", position_in_date=0), reference=None, target=None
                    ),
                )
            )
        },
    )
    result = uc.compute(
        base_dir=_BASE_DIR,
        date_from=date(2026, 1, 6),
        date_to=date(2026, 1, 6),
        grade_levels=frozenset({7}),
        other_entries=[own_entry],
        exclude_entry_id="self",
    )
    unit = next(u for u in result.affected_units if u.markdown_path == _PATH_7A)
    assert unit.claimed_by_reason is None
