"""Tests für ArchivePastLessonFilesUseCase."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.archive_past_lesson_files_usecase import ArchivePastLessonFilesUseCase

_TODAY = date(2026, 3, 20)
_PAST = "10-03-26"  # 10 March 2026 → in der Vergangenheit
_FUTURE = "25-03-26"  # 25 March 2026 → in der Zukunft


def _make_table(plan_dir: Path, rows: list[list[str]]) -> PlanTableData:
    """Erstellt eine minimale PlanTableData mit 4-Spalten-Header."""
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_md = plan_dir / f"{plan_dir.name}.md"
    plan_md.write_text(
        "---\n"
        'Lerngruppe: "[[li2]]"\n'
        'Kursfach: "Informatik"\n'
        "Stufe: 10\n"
        "---\n",
        encoding="utf-8",
    )
    return PlanTableData(
        markdown_path=plan_md,
        headers=["Datum", "Stunden", "Inhalt", "Thema/Ausfall"],
        rows=rows,
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=True,
        metadata={"Lerngruppe": "[[li2]]"},
    )


def _make_lesson(einheiten: Path, stem: str) -> Path:
    einheiten.mkdir(parents=True, exist_ok=True)
    p = einheiten / f"{stem}.md"
    p.write_text("---\nStundentyp: Unterricht\n---\n", encoding="utf-8")
    return p


class TestArchivePastLessonFilesUseCase:
    """ArchivePastLessonFilesUseCase.execute: Archivierungslogik."""

    def test_past_lesson_is_moved_to_alteinheiten(self, tmp_path):
        """Datei mit vergangenem Datum wird nach Alteinheiten/ verschoben."""
        plan_dir = tmp_path / "M li2 26-1"
        einheiten = plan_dir / "Einheiten"
        lesson = _make_lesson(einheiten, "ab12cd")
        table = _make_table(plan_dir, [[_PAST, "2", f"[[ab12cd]]", ""]])

        moved = ArchivePastLessonFilesUseCase().execute(table, reference_date=_TODAY)

        assert moved == 1
        assert not lesson.exists()
        assert (plan_dir / "Alteinheiten" / "ab12cd.md").exists()

    def test_future_lesson_stays_in_einheiten(self, tmp_path):
        """Datei mit zukünftigem Datum bleibt in Einheiten/."""
        plan_dir = tmp_path / "M li2 26-1"
        einheiten = plan_dir / "Einheiten"
        lesson = _make_lesson(einheiten, "zz99aa")
        table = _make_table(plan_dir, [[_FUTURE, "2", "[[zz99aa]]", ""]])

        moved = ArchivePastLessonFilesUseCase().execute(table, reference_date=_TODAY)

        assert moved == 0
        assert lesson.exists()
        assert not (plan_dir / "Alteinheiten" / "zz99aa.md").exists()

    def test_today_lesson_stays_in_einheiten(self, tmp_path):
        """Datei mit heutigem Datum (= Referenzdatum) bleibt in Einheiten/."""
        plan_dir = tmp_path / "M li2 26-1"
        einheiten = plan_dir / "Einheiten"
        today_str = _TODAY.strftime("%d-%m-%y")
        lesson = _make_lesson(einheiten, "tt0day")
        table = _make_table(plan_dir, [[today_str, "2", "[[tt0day]]", ""]])

        moved = ArchivePastLessonFilesUseCase().execute(table, reference_date=_TODAY)

        assert moved == 0
        assert lesson.exists()

    def test_row_without_link_not_moved(self, tmp_path):
        """Zeilen ohne Wiki-Link erzeugen keine Verschiebung."""
        plan_dir = tmp_path / "M li2 26-1"
        table = _make_table(plan_dir, [[_PAST, "0", "", "X Ferien"]])

        moved = ArchivePastLessonFilesUseCase().execute(table, reference_date=_TODAY)

        assert moved == 0

    def test_already_in_alteinheiten_not_moved_again(self, tmp_path):
        """Dateien die schon in Alteinheiten/ liegen werden nicht erneut verschoben."""
        plan_dir = tmp_path / "M li2 26-1"
        alteinheiten = plan_dir / "Alteinheiten"
        alteinheiten.mkdir(parents=True, exist_ok=True)
        (alteinheiten / "already.md").write_text("---\nStundentyp: Unterricht\n---\n", encoding="utf-8")
        (plan_dir / "Einheiten").mkdir(parents=True, exist_ok=True)
        table = _make_table(plan_dir, [[_PAST, "2", "[[already]]", ""]])

        moved = ArchivePastLessonFilesUseCase().execute(table, reference_date=_TODAY)

        assert moved == 0
        assert (alteinheiten / "already.md").exists()

    def test_alteinheiten_dir_created_automatically(self, tmp_path):
        """Alteinheiten/ wird angelegt, wenn es noch nicht existiert."""
        plan_dir = tmp_path / "M li2 26-1"
        einheiten = plan_dir / "Einheiten"
        _make_lesson(einheiten, "new001")
        table = _make_table(plan_dir, [[_PAST, "2", "[[new001]]", ""]])

        ArchivePastLessonFilesUseCase().execute(table, reference_date=_TODAY)

        assert (plan_dir / "Alteinheiten").is_dir()

    def test_multiple_past_lessons_all_moved(self, tmp_path):
        """Alle vergangenen Lektionen einer Tabelle werden in einem Durchlauf archiviert."""
        plan_dir = tmp_path / "M li2 26-1"
        einheiten = plan_dir / "Einheiten"
        _make_lesson(einheiten, "aa1111")
        _make_lesson(einheiten, "bb2222")
        table = _make_table(
            plan_dir,
            [
                [_PAST, "2", "[[aa1111]]", ""],
                [_PAST, "2", "[[bb2222]]", ""],
                [_FUTURE, "2", "[[cc3333]]", ""],
            ],
        )

        moved = ArchivePastLessonFilesUseCase().execute(table, reference_date=_TODAY)

        assert moved == 2
        assert (plan_dir / "Alteinheiten" / "aa1111.md").exists()
        assert (plan_dir / "Alteinheiten" / "bb2222.md").exists()
