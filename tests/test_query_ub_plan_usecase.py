from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.query_ub_plan_usecase import QueryUbPlanUseCase
from kursplaner.infrastructure.repositories.ub_repository import FileSystemUbRepository


@dataclass
class _FakePlanRepo:
    tables: list[PlanTableData]

    def load_plan_tables(self, base_dir: Path) -> list[PlanTableData]:
        del base_dir
        return list(self.tables)


def _write_ub(path: Path, *, domains: list[str], langentwurf: bool, einheit: str) -> None:
    domains_block = "\n".join(f'  - "{item}"' for item in domains)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "Bereich:\n"
        f"{domains_block}\n"
        f"Langentwurf: {'true' if langentwurf else 'false'}\n"
        "Beobachtungsschwerpunkt: Fokus\n"
        f'Einheit: "[[{einheit}]]"\n'
        "---\n\n"
        "# Reflexion\n",
        encoding="utf-8",
    )


def test_query_ub_plan_splits_upcoming_and_past(tmp_path, monkeypatch):
    workspace_root = tmp_path / "7thCloud"
    ub_root = workspace_root / "7thVault" / "🏫 Pädagogik" / "00 Orga" / "02 UBs"
    unterricht_root = workspace_root / "7thVault" / "Unterricht"
    unterricht_root.mkdir(parents=True)

    _write_ub(
        ub_root / "UB 26-05-18 Funktionen.md",
        domains=["Pädagogik", "Mathematik"],
        langentwurf=True,
        einheit="gruen-6 05-18 Funktionen",
    )
    _write_ub(
        ub_root / "UB 26-04-01 Wiederholung.md",
        domains=["Informatik"],
        langentwurf=False,
        einheit="gruen-6 04-01 Wiederholung",
    )

    table = PlanTableData(
        markdown_path=workspace_root / "7thVault" / "Unterricht" / "Inf Kurs" / "Inf Kurs.md",
        headers=["Datum", "Stunden", "Inhalt"],
        rows=[
            ["18-05-26", "2", "[[gruen-6 05-18 Funktionen]]"],
            ["01-04-26", "2", "[[gruen-6 04-01 Wiederholung]]"],
        ],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={},
    )

    class _FixedDateTime:
        @staticmethod
        def now():
            from datetime import datetime

            return datetime(2026, 4, 23, 10, 0)

    monkeypatch.setattr("kursplaner.core.usecases.query_ub_plan_usecase.datetime", _FixedDateTime)

    usecase = QueryUbPlanUseCase(
        ub_repo=FileSystemUbRepository(),
        plan_repo=_FakePlanRepo(tables=[table]),
    )
    result = usecase.execute(
        workspace_root=workspace_root,
        unterricht_base_dir=unterricht_root,
    )

    assert len(result.upcoming_rows) == 1
    assert len(result.past_rows) == 1
    assert result.upcoming_rows[0].datum == "18.05.26"
    assert result.upcoming_rows[0].plus == "+"
    assert result.upcoming_rows[0].kurs == "Inf Kurs"
    assert result.past_rows[0].datum == "01.04.26"
