from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData
from kursplaner.core.usecases.daily_course_log_usecase import DailyCourseLogUseCase


class _FakePlanRepo:
    def __init__(self, tables: list[PlanTableData]):
        self.tables = tables

    def load_plan_tables(self, _base_dir: Path) -> list[PlanTableData]:
        return list(self.tables)


class _FakeLessonRepo:
    def __init__(self, links_by_row: dict[int, Path], yaml_by_path: dict[Path, dict[str, object]]):
        self.links_by_row = links_by_row
        self.yaml_by_path = yaml_by_path

    def resolve_row_link_path(self, _table: PlanTableData, row_index: int) -> Path | None:
        return self.links_by_row.get(row_index)

    def load_lesson_yaml(self, path: Path) -> LessonYamlData:
        return LessonYamlData(lesson_path=path, data=dict(self.yaml_by_path[path]))


def _table_for_rows(plan_path: Path, rows: list[list[str]]) -> PlanTableData:
    return PlanTableData(
        markdown_path=plan_path,
        headers=["Datum", "Stunden", "Inhalt"],
        rows=rows,
        start_line=1,
        end_line=1,
        source_lines=[],
        had_trailing_newline=True,
        metadata={"Lerngruppe": "[[GK blau-1]]", "Kursfach": "Mathematik", "Stufe": "11"},
    )


def test_daily_export_includes_only_today_and_future_and_expands_hours(tmp_path, monkeypatch):
    unterricht_dir = tmp_path / "unterricht"
    einheiten_dir = unterricht_dir / "Mathematik" / "Einheiten"
    einheiten_dir.mkdir(parents=True)
    plan_path = unterricht_dir / "Mathematik" / "Mathematik.md"
    plan_path.write_text("# plan\n", encoding="utf-8")

    today = date(2026, 3, 31)
    yesterday = (today - timedelta(days=1)).strftime("%d-%m-%y")
    today_text = today.strftime("%d-%m-%y")

    lesson_path = einheiten_dir / "GK blau-1 03-31 Algebra.md"
    lesson_path.write_text("---\nStundentyp: Unterricht\n---\n", encoding="utf-8")

    table = _table_for_rows(
        plan_path,
        rows=[
            [yesterday, "1", "[[GK blau-1 03-30 Alt]]"],
            [today_text, "2", "[[GK blau-1 03-31 Algebra]]"],
        ],
    )

    plan_repo = _FakePlanRepo([table])
    lesson_repo = _FakeLessonRepo(
        links_by_row={1: lesson_path},
        yaml_by_path={
            lesson_path: {
                "Stundentyp": "Unterricht",
                "Dauer": "2",
                "Stundenthema": "Lineare Funktionen",
                "Oberthema": "Algebra",
                "Stundenziel": "Verstehen",
                "Kompetenzen": ["K1", "K2"],
                "Material": ["AB 1"],
            }
        },
    )
    usecase = DailyCourseLogUseCase(plan_repo=plan_repo, lesson_repo=lesson_repo)
    monkeypatch.setattr(DailyCourseLogUseCase, "_log_dir", staticmethod(lambda: tmp_path / "logs"))

    result = usecase.export_for_day(unterricht_dir=unterricht_dir, export_day=today)

    assert result.created is True
    payload = json.loads(result.log_path.read_text(encoding="utf-8"))
    assert payload["export_date"] == "2026-03-31"
    assert len(payload["courses"]) == 1
    assert len(payload["courses"][0]["units"]) == 1
    unit = payload["courses"][0]["units"][0]
    assert unit["cells"]["Stundenthema"] == "Lineare Funktionen"
    assert unit["cells"]["Kompetenzen"] == ["K1", "K2"]
    assert len(unit["hour_entries"]) == 2
    assert [entry["hour_index"] for entry in unit["hour_entries"]] == [1, 2]


def test_daily_export_writes_max_one_file_per_day(tmp_path, monkeypatch):
    unterricht_dir = tmp_path / "unterricht"
    einheiten_dir = unterricht_dir / "Mathematik" / "Einheiten"
    einheiten_dir.mkdir(parents=True)
    plan_path = unterricht_dir / "Mathematik" / "Mathematik.md"
    plan_path.write_text("# plan\n", encoding="utf-8")

    today = date(2026, 3, 31)
    lesson_path = einheiten_dir / "GK blau-1 03-31 Test.md"
    lesson_path.write_text("---\nStundentyp: Unterricht\n---\n", encoding="utf-8")
    table = _table_for_rows(
        plan_path,
        rows=[[today.strftime("%d-%m-%y"), "1", "[[GK blau-1 03-31 Test]]"]],
    )

    usecase = DailyCourseLogUseCase(
        plan_repo=_FakePlanRepo([table]),
        lesson_repo=_FakeLessonRepo(
            links_by_row={0: lesson_path},
            yaml_by_path={lesson_path: {"Stundentyp": "Unterricht", "Dauer": "1", "Stundenthema": "Test"}},
        ),
    )
    monkeypatch.setattr(DailyCourseLogUseCase, "_log_dir", staticmethod(lambda: tmp_path / "logs"))

    first = usecase.export_for_day(unterricht_dir=unterricht_dir, export_day=today)
    second = usecase.export_for_day(unterricht_dir=unterricht_dir, export_day=today)

    assert first.created is True
    assert second.created is False
    assert first.log_path == second.log_path


def test_daily_export_includes_ausfall_without_lesson_link(tmp_path, monkeypatch):
    unterricht_dir = tmp_path / "unterricht"
    fach_dir = unterricht_dir / "Mathematik"
    fach_dir.mkdir(parents=True)
    plan_path = fach_dir / "Mathematik.md"
    plan_path.write_text("# plan\n", encoding="utf-8")

    today = date(2026, 3, 31)
    table = _table_for_rows(
        plan_path,
        rows=[[today.strftime("%d-%m-%y"), "1", "X Krank"]],
    )
    usecase = DailyCourseLogUseCase(
        plan_repo=_FakePlanRepo([table]),
        lesson_repo=_FakeLessonRepo(links_by_row={}, yaml_by_path={}),
    )
    monkeypatch.setattr(DailyCourseLogUseCase, "_log_dir", staticmethod(lambda: tmp_path / "logs"))

    result = usecase.export_for_day(unterricht_dir=unterricht_dir, export_day=today)

    payload = json.loads(result.log_path.read_text(encoding="utf-8"))
    unit = payload["courses"][0]["units"][0]
    assert unit["status"] == "ausfall"
    assert unit["link_path"] == ""
    assert len(unit["hour_entries"]) == 1


def test_daily_export_serializes_paths_workspace_relative(tmp_path, monkeypatch):
    unterricht_dir = tmp_path / "unterricht"
    einheiten_dir = unterricht_dir / "Mathematik" / "Einheiten"
    einheiten_dir.mkdir(parents=True)
    plan_path = unterricht_dir / "Mathematik" / "Mathematik.md"
    plan_path.write_text("# plan\n", encoding="utf-8")

    today = date(2026, 3, 31)
    lesson_path = einheiten_dir / "GK blau-1 03-31 Relativ.md"
    lesson_path.write_text("---\nStundentyp: Unterricht\n---\n", encoding="utf-8")

    table = _table_for_rows(
        plan_path,
        rows=[[today.strftime("%d-%m-%y"), "1", "[[GK blau-1 03-31 Relativ]]"]],
    )

    usecase = DailyCourseLogUseCase(
        plan_repo=_FakePlanRepo([table]),
        lesson_repo=_FakeLessonRepo(
            links_by_row={0: lesson_path},
            yaml_by_path={lesson_path: {"Stundentyp": "Unterricht", "Dauer": "1", "Stundenthema": "Relativ"}},
        ),
    )
    monkeypatch.setattr(DailyCourseLogUseCase, "_log_dir", staticmethod(lambda: tmp_path / "logs"))

    result = usecase.export_for_day(unterricht_dir=unterricht_dir, export_day=today)
    payload = json.loads(result.log_path.read_text(encoding="utf-8"))

    source_dir = str(payload.get("source_unterricht_dir", ""))
    link_path = str(payload["courses"][0]["units"][0].get("link_path", ""))
    assert source_dir
    assert link_path
    assert ":\\" not in source_dir
    assert ":\\" not in link_path
    assert not source_dir.startswith("\\")
    assert not link_path.startswith("\\")
