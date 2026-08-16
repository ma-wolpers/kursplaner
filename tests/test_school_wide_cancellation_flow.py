from __future__ import annotations

from datetime import date
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.flows.school_wide_cancellation_flow import SchoolWideCancellationFlow
from kursplaner.core.ports.repositories import ConflictResolution
from kursplaner.core.usecases.bulk_cancellation_coordinator import BulkCancellationCoordinator
from kursplaner.core.usecases.school_wide_cancellation_apply_usecase import SchoolWideCancellationApplyUseCase
from kursplaner.core.usecases.school_wide_cancellation_preview_usecase import SchoolWideCancellationPreviewUseCase
from kursplaner.core.usecases.school_wide_cancellation_revert_usecase import SchoolWideCancellationRevertUseCase

_HEADERS = ["Datum", "Inhalt", "Thema/Ausfall"]
_BASE_DIR = Path("courses")
_PATH_7A = _BASE_DIR / "7a" / "7a.md"


def _table(rows: list[list[str]]) -> PlanTableData:
    return PlanTableData(
        markdown_path=_PATH_7A,
        headers=_HEADERS,
        rows=rows,
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={"Lerngruppe": "[[7a]]", "Stufe": "7"},
    )


class _InMemoryPlanRepo:
    """Faelscht Persistenz per In-Memory-Dict; jeder `load` liefert eine frische Kopie."""

    def __init__(self, tables: dict[Path, PlanTableData]) -> None:
        self._tables = tables

    def list_plan_markdown_files(self, base_dir: Path) -> list[Path]:
        return list(self._tables.keys())

    def load_plan_metadata(self, markdown_path: Path) -> dict[str, str]:
        return self._tables[markdown_path].metadata

    def load_plan_table(self, markdown_path: Path) -> PlanTableData:
        table = self._tables[markdown_path]
        return PlanTableData(
            markdown_path=table.markdown_path,
            headers=list(table.headers),
            rows=[list(row) for row in table.rows],
            start_line=table.start_line,
            end_line=table.end_line,
            source_lines=list(table.source_lines),
            had_trailing_newline=table.had_trailing_newline,
            metadata=dict(table.metadata),
        )

    def save_plan_table(self, table: PlanTableData) -> None:
        self._tables[table.markdown_path] = table


def _make_flow(rows: list[list[str]]):
    tables = {_PATH_7A: _table(rows)}
    repo = _InMemoryPlanRepo(tables)
    preview_uc = SchoolWideCancellationPreviewUseCase(plan_repo=repo)
    apply_uc = SchoolWideCancellationApplyUseCase(plan_repo=repo)
    revert_uc = SchoolWideCancellationRevertUseCase(plan_repo=repo)
    coordinator = BulkCancellationCoordinator(apply_uc=apply_uc, revert_uc=revert_uc)

    store: list = []

    flow = SchoolWideCancellationFlow(
        preview_uc=preview_uc,
        coordinator=coordinator,
        store_load=lambda: list(store),
        store_save=lambda entries: store.__setitem__(slice(None), entries),
    )
    return flow, tables, store


def _decide_skip(_ctx) -> ConflictResolution:
    return ConflictResolution.SKIP


def test_create_applies_and_persists_entry():
    flow, tables, store = _make_flow([["06-01-26", "[[abc]]", ""]])
    result = flow.create(
        base_dir=_BASE_DIR,
        date_from=date(2026, 1, 6),
        date_to=date(2026, 1, 6),
        grade_levels=frozenset({7}),
        reason="Wandertag",
        decide=_decide_skip,
    )
    assert not result.bulk_result.aborted
    assert result.entry is not None
    assert len(store) == 1
    assert tables[_PATH_7A].rows[0][2] == "X Wandertag"


def test_create_with_no_matching_courses_yields_empty_ledger():
    flow, _tables, _store = _make_flow([["06-01-26", "[[abc]]", ""]])
    result = flow.create(
        base_dir=_BASE_DIR,
        date_from=date(2026, 1, 6),
        date_to=date(2026, 1, 6),
        grade_levels=frozenset({11}),
        reason="Wandertag",
        decide=_decide_skip,
    )
    assert result.entry.course_ledgers == {}


def test_delete_reverts_and_removes_entry():
    flow, tables, store = _make_flow([["06-01-26", "[[abc]]", ""]])
    created = flow.create(
        base_dir=_BASE_DIR,
        date_from=date(2026, 1, 6),
        date_to=date(2026, 1, 6),
        grade_levels=frozenset({7}),
        reason="Wandertag",
        decide=_decide_skip,
    )
    flow.delete(entry_id=created.entry.entry_id, decide=_decide_skip)

    assert store == []
    assert tables[_PATH_7A].rows[0][1] == "[[abc]]"
    assert tables[_PATH_7A].rows[0][2] == ""


def test_edit_widens_range_and_applies_to_newly_matching_dates():
    flow, tables, _store = _make_flow(
        [
            ["06-01-26", "[[abc]]", ""],
            ["07-01-26", "[[def]]", ""],
        ]
    )
    created = flow.create(
        base_dir=_BASE_DIR,
        date_from=date(2026, 1, 6),
        date_to=date(2026, 1, 6),
        grade_levels=frozenset({7}),
        reason="Wandertag",
        decide=_decide_skip,
    )
    edited = flow.edit(
        entry_id=created.entry.entry_id,
        base_dir=_BASE_DIR,
        date_from=date(2026, 1, 6),
        date_to=date(2026, 1, 7),
        grade_levels=frozenset({7}),
        reason="Wandertag",
        decide=_decide_skip,
    )
    assert not edited.bulk_result.aborted
    assert tables[_PATH_7A].rows[0][2] == "X Wandertag"
    assert tables[_PATH_7A].rows[1][2] == "X Wandertag"


def test_edit_narrower_range_reverts_dropped_dates():
    flow, tables, _store = _make_flow(
        [
            ["06-01-26", "[[abc]]", ""],
            ["07-01-26", "[[def]]", ""],
        ]
    )
    created = flow.create(
        base_dir=_BASE_DIR,
        date_from=date(2026, 1, 6),
        date_to=date(2026, 1, 7),
        grade_levels=frozenset({7}),
        reason="Wandertag",
        decide=_decide_skip,
    )
    edited = flow.edit(
        entry_id=created.entry.entry_id,
        base_dir=_BASE_DIR,
        date_from=date(2026, 1, 6),
        date_to=date(2026, 1, 6),
        grade_levels=frozenset({7}),
        reason="Wandertag",
        decide=_decide_skip,
    )
    assert not edited.bulk_result.aborted
    assert tables[_PATH_7A].rows[0][2] == "X Wandertag"
    assert tables[_PATH_7A].rows[1][2] == ""
    assert tables[_PATH_7A].rows[1][1] == "[[def]]"


def test_list_entries_reflects_store():
    flow, _tables, _store = _make_flow([["06-01-26", "[[abc]]", ""]])
    assert flow.list_entries() == []
    created = flow.create(
        base_dir=_BASE_DIR,
        date_from=date(2026, 1, 6),
        date_to=date(2026, 1, 6),
        grade_levels=frozenset({7}),
        reason="Wandertag",
        decide=_decide_skip,
    )
    assert [e.entry_id for e in flow.list_entries()] == [created.entry.entry_id]
