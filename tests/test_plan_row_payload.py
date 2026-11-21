"""Einheiten-Nutzlast einer Planzeile: Link und Thema-Zelle wandern gemeinsam, Termine bleiben (synthetisch)."""

from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.plan_row_payload import PayloadColumns, RowPayload, shift_moves, swap_payloads
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.plan_commands_usecase import PlanCommandsUseCase

HEADERS = ["Datum", "Inhalt", "Thema/Ausfall"]


def _table(*rows: tuple[str, str]) -> PlanTableData:
    """Tabelle aus ``(Inhalt, Thema)``-Paaren; Datum = laufende Nummer."""
    body = [[f"{i + 1:02d}-11-26", inhalt, thema] for i, (inhalt, thema) in enumerate(rows)]
    return PlanTableData(Path("plan.md"), list(HEADERS), body, 0, 0, [], True, {})


def _pairs(table: PlanTableData) -> list[tuple[str, str]]:
    return [(row[1], row[2]) for row in table.rows]


class _NoLinks:
    """Lesson-Repo ohne Dateien: keine Zeile ist eine LZK."""

    def resolve_row_link_path(self, _table, _row):
        return None


class _LzkAt(_NoLinks):
    """Lesson-Repo, das die Zeilen in *rows* als LZK-Dateien meldet."""

    def __init__(self, tmp_path: Path, rows: set[int]) -> None:
        self._files = {row: tmp_path / f"lzk{row}.md" for row in rows}
        for path in self._files.values():
            path.write_text("---\nStundentyp: LZK\n---\n", encoding="utf-8")

    def resolve_row_link_path(self, _table, row):
        return self._files.get(row)

    def load_lesson_yaml(self, path):
        class _Lesson:
            data = {"Stundentyp": "LZK"}

        return _Lesson()


def test_read_skips_a_slot_marker_and_write_never_overwrites_it():
    columns = PayloadColumns.of(_table())
    cancelled = ["01-11-26", "", "X Wandertag"]
    assert columns.read(cancelled) == RowPayload("", "")
    columns.write(cancelled, RowPayload("[[a]]", "[[g Brüche]]"))
    assert cancelled == ["01-11-26", "[[a]]", "X Wandertag"]
    columns.clear_slot_marker(cancelled)
    assert cancelled[2] == ""


def test_shift_moves_link_and_thema_together_up_to_the_first_free_slot():
    table = _table(("[[a]]", "[[g A]]"), ("[[b]]", "[[g B]]"), ("", ""), ("[[c]]", "[[g C]]"))
    assert PlanCommandsUseCase(_NoLinks()).shift_existing_lessons_forward(table, 0)
    assert _pairs(table) == [("", ""), ("[[a]]", "[[g A]]"), ("[[b]]", "[[g B]]"), ("[[c]]", "[[g C]]")]


def test_shift_jumps_over_cancelled_rows_and_lzk(tmp_path):
    table = _table(("[[a]]", "[[g A]]"), ("", "X Ferien X"), ("[[lzk]]", "LZK [[g A]]"), ("", ""))
    commands = PlanCommandsUseCase(_LzkAt(tmp_path, {2}))
    assert commands.plan_shift(table, 0) == ((0, 3),)
    assert commands.shift_existing_lessons_forward(table, 0)
    assert _pairs(table) == [("", ""), ("", "X Ferien X"), ("[[lzk]]", "LZK [[g A]]"), ("[[a]]", "[[g A]]")]


def test_an_explicitly_chosen_lzk_moves_itself(tmp_path):
    table = _table(("[[lzk]]", "LZK [[g A]]"), ("", ""))
    assert PlanCommandsUseCase(_LzkAt(tmp_path, {0})).shift_existing_lessons_forward(table, 0)
    assert _pairs(table) == [("", ""), ("[[lzk]]", "LZK [[g A]]")]


def test_a_row_with_only_a_planned_topic_is_not_free():
    table = _table(("[[a]]", "[[g A]]"), ("", "[[g B]]"), ("", ""))
    assert shift_moves(table, 0) == ((1, 2), (0, 1))


def test_no_free_slot_changes_nothing():
    table = _table(("[[a]]", "[[g A]]"), ("[[b]]", "[[g B]]"))
    before = _pairs(table)
    assert PlanCommandsUseCase(_NoLinks()).shift_existing_lessons_forward(table, 0) is False
    assert _pairs(table) == before


def test_swap_moves_both_cells_and_keeps_slot_markers():
    table = _table(("[[a]]", "[[g A]]"), ("[[b]]", "[[g B]]"), ("[[s]]", "X Krank"))
    swap_payloads(table, 0, 1)
    assert _pairs(table)[:2] == [("[[b]]", "[[g B]]"), ("[[a]]", "[[g A]]")]
    swap_payloads(table, 0, 2)
    assert _pairs(table) == [("[[s]]", ""), ("[[a]]", "[[g A]]"), ("[[b]]", "X Krank")]
