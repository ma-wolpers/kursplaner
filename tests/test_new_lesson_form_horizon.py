from __future__ import annotations

from datetime import date
from pathlib import Path

from kursplaner.core.usecases.new_lesson_form_usecase import NewLessonFormData, NewLessonFormUseCase


class _CalendarRepoStub:
    def infer_term_from_date(self, start_date, calendar_dir):
        return "26-1"

    def load_calendar_data(self, calendar_dir, years):
        blocks = [
            ("Osterferien", date(2026, 4, 1), date(2026, 4, 12)),
            ("Sommerferien", date(2026, 7, 10), date(2026, 8, 20)),
            ("Herbstferien", date(2026, 10, 5), date(2026, 10, 18)),
        ]
        return {}, blocks, []


class _KompetenzRepoStub:
    def default_manifest_path(self):
        return Path("manifest.json")

    def load_manifest_entries_from(self, manifest_path):
        return ()

    def list_manifest_entries(self):
        return ()


def _form(base: Path) -> NewLessonFormData:
    return NewLessonFormData(
        subject_raw="Mathematik",
        group_raw="blau-1",
        grade_raw="8",
        period_raw="2026-03-20",
        base_dir_raw=str(base),
        calendar_dir_raw=str(base),
        day_hours_raw={0: "2", 2: "2"},
        vacation_break_horizon_raw="2",
    )


def test_vacation_horizon_limits_and_preview_date(tmp_path):
    usecase = NewLessonFormUseCase(_CalendarRepoStub(), _KompetenzRepoStub())
    form = _form(tmp_path)

    limits = usecase.vacation_horizon_limits(form)
    assert limits == (1, 2)

    end_date = usecase.preview_vacation_end_date(form)
    assert end_date == date(2026, 7, 10)


def test_parse_vacation_horizon_rejects_non_numeric():
    usecase = NewLessonFormUseCase(_CalendarRepoStub(), _KompetenzRepoStub())

    try:
        usecase.parse_vacation_horizon("overnext")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for non-numeric horizon")


def test_build_start_request_rejects_horizon_beyond_halfyear_boundary(tmp_path):
    usecase = NewLessonFormUseCase(_CalendarRepoStub(), _KompetenzRepoStub())
    form = NewLessonFormData(
        subject_raw="Mathematik",
        group_raw="blau-1",
        grade_raw="8",
        period_raw="2026-03-20",
        base_dir_raw=str(tmp_path),
        calendar_dir_raw=str(tmp_path),
        day_hours_raw={0: "2", 2: "2"},
        vacation_break_horizon_raw="3",
    )

    try:
        usecase.build_start_request(form)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for horizon beyond halfyear boundary")
