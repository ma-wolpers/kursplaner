from datetime import date, datetime
from pathlib import Path

from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData
from kursplaner.core.usecases.export_expected_horizon_usecase import (
    ExportExpectedHorizonResult,
    ExportExpectedHorizonUseCase,
)
from kursplaner.core.usecases.export_lzk_expected_horizon_usecase import ExportLzkExpectedHorizonUseCase
from kursplaner.infrastructure.export.expected_horizon_markdown_renderer import ExpectedHorizonMarkdownRenderer


class _LessonRepoStub:
    def __init__(self, lesson_by_path: dict[Path, LessonYamlData]):
        self._lesson_by_path = dict(lesson_by_path)
        self.saved: list[LessonYamlData] = []

    def load_lesson_yaml(self, path: Path) -> LessonYamlData:
        return self._lesson_by_path[path.resolve()]

    def save_lesson_yaml(self, lesson: LessonYamlData) -> None:
        self.saved.append(lesson)
        self._lesson_by_path[lesson.lesson_path.resolve()] = lesson


class _ExportUseCaseStub:
    def __init__(self):
        self.calls: list[Path] = []

    def execute(self, *, table, day_columns, selected_day_index, output_path, export_date):
        del table, day_columns, selected_day_index, export_date
        self.calls.append(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("ok", encoding="utf-8")
        return ExportExpectedHorizonResult(output_path=output_path, title="Kompetenzhorizont: Mengen", row_count=3)


def _table(plan_path: Path) -> PlanTableData:
    return PlanTableData(
        markdown_path=plan_path,
        headers=["Datum", "Stunden", "Inhalt"],
        rows=[["02-04-26", "2", "[[LZK 1]]"]],
        start_line=1,
        end_line=2,
        source_lines=[],
        had_trailing_newline=True,
        metadata={"Kursfach": "Mathematik", "Lerngruppe": "[[lila-4]]"},
    )


def test_execute_exports_md_and_pdf_and_updates_lesson_link(tmp_path):
    course_dir = tmp_path / "kurs"
    einheiten_dir = course_dir / "Einheiten"
    einheiten_dir.mkdir(parents=True)
    lesson_path = (einheiten_dir / "lzk.md").resolve()
    lesson_path.write_text("---\nStundentyp: LZK\n---\n", encoding="utf-8")

    lesson_repo = _LessonRepoStub(
        {
            lesson_path: LessonYamlData(
                lesson_path=lesson_path,
                data={
                    "Stundentyp": "LZK",
                    "Stundenthema": "LZK Sortieren",
                    "Oberthema": "Mengen & Folgen",
                    "Kompetenzhorizont": "",
                },
            )
        }
    )
    md_export = _ExportUseCaseStub()
    pdf_export = _ExportUseCaseStub()

    usecase = ExportLzkExpectedHorizonUseCase(
        lesson_repo=lesson_repo,
        export_markdown_usecase=md_export,
        export_pdf_usecase=pdf_export,
    )

    result = usecase.execute(
        table=_table(course_dir / "kurs.md"),
        day_columns=[{"is_lzk": True, "row_index": 0, "link": lesson_path}],
        selected_day_index=0,
        export_date=date(2026, 4, 2),
        created_at=datetime(2026, 4, 2, 13, 15, 0),
    )

    assert result.markdown_path.name == "KH-Mengen_Folgen.md"
    assert result.pdf_path.name == "KH-Mengen_Folgen.pdf"
    assert md_export.calls == [result.markdown_path]
    assert pdf_export.calls == [result.pdf_path]

    assert len(lesson_repo.saved) == 1
    saved_yaml = lesson_repo.saved[0].data
    assert saved_yaml["Kompetenzhorizont"] == "[[KH-Mengen_Folgen]]"
    assert saved_yaml["created_at"].startswith("2026-04-02T13:15:00")


def test_lzk_export_uses_same_markdown_merge_behavior_for_overwrite(tmp_path):
    course_dir = tmp_path / "kurs"
    einheiten_dir = course_dir / "Einheiten"
    einheiten_dir.mkdir(parents=True)
    lesson_path = (einheiten_dir / "lzk.md").resolve()
    lesson_path.write_text("---\nStundentyp: LZK\n---\n", encoding="utf-8")

    lesson_repo = _LessonRepoStub(
        {
            lesson_path: LessonYamlData(
                lesson_path=lesson_path,
                data={
                    "Stundentyp": "LZK",
                    "Stundenthema": "LZK Sortieren",
                    "Oberthema": "Mengen & Folgen",
                    "Kompetenzhorizont": "",
                },
            )
        }
    )

    markdown_export = ExportExpectedHorizonUseCase(renderer=ExpectedHorizonMarkdownRenderer())
    pdf_export = _ExportUseCaseStub()
    usecase = ExportLzkExpectedHorizonUseCase(
        lesson_repo=lesson_repo,
        export_markdown_usecase=markdown_export,
        export_pdf_usecase=pdf_export,
    )

    target_md = (course_dir / "KH-Mengen_Folgen.md").resolve()
    target_md.write_text(
        "\n".join(
            [
                "# Kompetenzhorizont: Mengen & Folgen",
                "",
                "Mathematik lila-4 2025/26 Hj. 2",
                "",
                "| Datum | Die SuS können ... | AFB | Aufg | Pkte |",
                "| --- | --- | --- | --- | --- |",
                "| **02.04.26** | **... Mengen beschreiben** | II | 1a | 2 |",
                "|  | ... Folgen fortsetzen | I | 1b | 1 |",
            ]
        ),
        encoding="utf-8",
    )

    day_columns = [
        {
            "row_index": 0,
            "datum": "02-04-26",
            "Stundentyp": "Unterricht",
            "yaml": {
                "Stundentyp": "Unterricht",
                "Oberthema": "Mengen & Folgen",
                "Stundenziel": "Mengen beschreiben",
                "Teilziele": [],
            },
            "is_lzk": False,
            "link": None,
        },
        {
            "row_index": 1,
            "datum": "09-04-26",
            "Stundentyp": "LZK",
            "yaml": {
                "Stundentyp": "LZK",
                "Oberthema": "Mengen & Folgen",
                "Stundenziel": "LZK Sortieren",
                "Teilziele": [],
            },
            "is_lzk": True,
            "link": lesson_path,
        },
    ]

    result = usecase.execute(
        table=_table(course_dir / "kurs 25-2.md"),
        day_columns=day_columns,
        selected_day_index=1,
        export_date=date(2026, 4, 2),
        created_at=datetime(2026, 4, 2, 13, 15, 0),
    )

    assert result.markdown_path.resolve() == target_md
    merged = target_md.read_text(encoding="utf-8")
    assert "| **02.04.26** | **... Mengen beschreiben** | II | 1a | 2 |" in merged
    assert "|  | ~~... Folgen fortsetzen~~ | I | 1b | 1 |" in merged
