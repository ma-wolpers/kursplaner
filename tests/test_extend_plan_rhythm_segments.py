"""`ExtendPlanToNextVacationUseCase` mit segmentiertem und zweiwoechigem Rhythmus.

Verlaengern uebergibt den vollstaendigen Rhythmus an die Zeilengenerierung
(Vertrag von `planner.generate_rows`): Ein spaeteres ``ab``-Segment im
Verlaengerungszeitraum greift dort, und ein dabei weggefallener Wochentag
bekommt keine Zeilen mehr (Ganz-Segment-Regel).
"""

from __future__ import annotations

from datetime import date, timedelta

from kursplaner.core.usecases.create_plan_usecase import CreatePlanUseCase
from kursplaner.core.usecases.extend_plan_to_next_vacation_usecase import ExtendPlanToNextVacationUseCase
from kursplaner.infrastructure.repositories.plan_repository import FileSystemPlanRepository
from kursplaner.infrastructure.repositories.plan_table_file_repository import load_last_plan_table

HERBST_START = date(2026, 10, 12)


class _CalendarRepoStub:
    """Herbstferien 12.10.-23.10.2026 als Block und Einzeltage."""

    def load_calendar_data(self, calendar_dir, years):
        """Liefert synthetische Ferientage, -bloecke und keine Warnungen."""
        events = {HERBST_START + timedelta(days=offset): "Herbstferien" for offset in range(12)}
        blocks = [("Herbstferien", HERBST_START, date(2026, 10, 23))]
        return events, blocks, []


def _write_plan(path, rhythm_lines: list[str], row_dates: list[str]) -> None:
    """Schreibt eine minimale synthetische Plan-Datei."""
    items = "".join(f'  - "{line}"\n' for line in rhythm_lines)
    rows = "".join(f"| {row} |  |  |\n" for row in row_dates)
    path.write_text(
        f'---\nLerngruppe: "[[GK blau-1]]"\nKursfach: "Mathematik"\nStufe: 11\nRhythmus:\n{items}---\n\n'
        f"| Datum | Inhalt | Thema/Ausfall |\n| --- | --- | --- |\n{rows}",
        encoding="utf-8",
    )


def _extend(path) -> list[tuple[str, str]]:
    """Verlaengert den Plan bis zu den Herbstferien und liefert (Datum, Thema/Ausfall) je Zeile."""
    repo = FileSystemPlanRepository()
    usecase = ExtendPlanToNextVacationUseCase(
        plan_repo=repo,
        create_plan_usecase=CreatePlanUseCase(plan_repo=repo, calendar_repo=_CalendarRepoStub()),
    )
    usecase.execute(markdown_path=path, calendar_dir=path.parent)
    table = load_last_plan_table(path)
    return [(row[0].strip(), row[2].strip()) for row in table.rows]


def test_extend_honours_later_segment_and_drops_removed_weekday(tmp_path):
    plan = tmp_path / "M GK blau-1 26-2.md"
    _write_plan(plan, ["Mo 08:00 2", "ab 05-10-26 Do 07:50 2"], ["21-09-26", "28-09-26"])

    rows = _extend(plan)

    # Ab 05.10. gilt nur noch Do: kein Mo 05.10.; Ferienbeginn als Abschlusszeile.
    assert rows == [
        ("21-09-26", ""),
        ("28-09-26", ""),
        ("08-10-26", ""),
        ("12-10-26", "X Herbstferien X"),
    ]


def test_extend_with_biweekly_rhythm_only_adds_matching_weeks(tmp_path):
    plan = tmp_path / "M GK blau-1 26-2.md"
    _write_plan(plan, ["Mo 08:00 2 uKW"], ["21-09-26"])

    rows = _extend(plan)

    # 28.09. KW 40 (gerade) -> nein, 05.10. KW 41 -> ja, 12.10. KW 42 -> Abschlusszeile.
    assert rows == [
        ("21-09-26", ""),
        ("05-10-26", ""),
        ("12-10-26", "X Herbstferien X"),
    ]
