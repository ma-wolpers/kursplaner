"""Tests für den Abgleich der Sequenz-Links der Plantabelle beim Kursladen (synthetische Daten).

Prüft die eine Regel: Bei Zeilen mit Einheitendatei wird die Zelle ``Thema/Ausfall``
aus dem YAML-``Oberthema`` abgeleitet – aber nur, wenn sie leer ist oder genau einen
Sequenz-Link trägt. Gespeichert wird nur bei Änderungen.
"""

from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.reconcile_plan_topic_links_usecase import ReconcilePlanTopicLinksUseCase
from kursplaner.infrastructure.repositories.plan_table_file_repository import sync_thema_ausfall_to_plan_row
from tests.day_column_factory import make_day_column

GROUP = "[[ge5]]"


class _RecordingPlanRepo:
    """Minimaler Plan-Port: echte Ableitungsregel, gespeicherte Tabellen werden nur gezählt."""

    def __init__(self) -> None:
        self.saved: list[PlanTableData] = []

    def sync_thema_ausfall_to_plan_row(self, table, row_index, yaml_data, group_name) -> None:
        sync_thema_ausfall_to_plan_row(table, row_index, yaml_data, group_name)

    def save_plan_table(self, table: PlanTableData) -> None:
        self.saved.append(table)


def _unit(tmp_path: Path, stem: str) -> Path:
    unit_dir = tmp_path / "Einheiten"
    unit_dir.mkdir(exist_ok=True)
    path = unit_dir / f"{stem}.md"
    path.write_text("---\nStundentyp: Unterricht\n---\n", encoding="utf-8")
    return path


def _table(tmp_path: Path, cells: list[str]) -> PlanTableData:
    return PlanTableData(
        markdown_path=tmp_path / "Plan.md",
        headers=["Datum", "Inhalt", "Thema/Ausfall"],
        rows=[[f"0{i + 1}-12-26", "", cell] for i, cell in enumerate(cells)],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=True,
        metadata={"Lerngruppe": GROUP},
    )


def _run(table: PlanTableData, days):
    repo = _RecordingPlanRepo()
    result = ReconcilePlanTopicLinksUseCase(plan_repo=repo).execute(table=table, day_columns=days)
    return repo, result


def test_empty_and_stale_links_are_derived_from_yaml_and_saved_once(tmp_path):
    table = _table(tmp_path, ["", "[[ge5 Brüche]]", "[[ge5 Dezimalbrüche]]"])
    days = [
        make_day_column(row_index=i, link=_unit(tmp_path, f"u{i}"), yaml={"Oberthema": "Dezimalbrüche"})
        for i in range(3)
    ]

    repo, result = _run(table, days)

    assert result.changed_rows == (0, 1)
    assert [row[2] for row in table.rows] == ["[[ge5 Dezimalbrüche]]"] * 3
    assert len(repo.saved) == 1


def test_lzk_gets_prefixed_link_and_removed_oberthema_clears_the_cell(tmp_path):
    table = _table(tmp_path, ["", "[[ge5 Dezimalbrüche]]"])
    days = [
        make_day_column(
            row_index=0, link=_unit(tmp_path, "lzk"), yaml={"Stundentyp": "LZK", "Oberthema": ["[[ge5 Dezimalbrüche]]"]}
        ),
        make_day_column(row_index=1, link=_unit(tmp_path, "free"), yaml={"Stundentyp": "Unterricht", "Oberthema": ""}),
    ]

    _, result = _run(table, days)

    assert result.changed_rows == (0, 1)
    assert table.rows[0][2] == "LZK [[ge5 Dezimalbrüche]]"
    assert table.rows[1][2] == ""


def test_markers_free_text_and_rows_without_file_stay_untouched(tmp_path):
    cells = ["X Wandertag", "HO ge5 Besuch", "eigene Notiz", "[[ge5 Brüche]]"]
    table = _table(tmp_path, cells)
    days = [
        make_day_column(row_index=i, link=_unit(tmp_path, f"m{i}"), yaml={"Oberthema": "Dezimalbrüche"})
        for i in range(3)
    ]
    # Zeile ohne Einheitendatei: die Zelle ist dort die Quelle (Fallback), nicht der Spiegel.
    days.append(make_day_column(row_index=3, link=None, yaml={}))

    repo, result = _run(table, days)

    assert result.changed_rows == ()
    assert [row[2] for row in table.rows] == cells
    assert repo.saved == []


def test_is_derived_cell_recognises_only_empty_cells_and_sequence_links():
    use_case = ReconcilePlanTopicLinksUseCase
    assert use_case.is_derived_cell("", GROUP)
    assert use_case.is_derived_cell("[[ge5 Dezimalbrüche]]", GROUP)
    assert use_case.is_derived_cell("LZK [[ge5 Dezimalbrüche]]", "ge5")
    assert not use_case.is_derived_cell("X Wandertag", GROUP)
    assert not use_case.is_derived_cell("HO ge5 Besuch", GROUP)
