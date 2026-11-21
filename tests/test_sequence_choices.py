"""Sequenzliste für Dialog und Leiter-Auswahl sowie Plan-Zeile je Sprosse (synthetisch)."""

from __future__ import annotations

from pathlib import Path

from sequence_view_factory import make_plan_views

from kursplaner.adapters.gui.sequence_choices import sequence_choices, view_for_path, view_for_rows
from kursplaner.core.domain.topic_sequence_runs import TopicSequenceRun
from kursplaner.core.usecases.load_sequence_ladder_usecase import RungKind, rung_infos
from tests.day_column_factory import make_day_column


def _entry(path: str, oberthema: str, rows: tuple[int, ...]) -> tuple[TopicSequenceRun, Path]:
    return TopicSequenceRun(oberthema=oberthema, member_row_indices=rows), Path(path)


def test_runs_sharing_a_file_form_one_choice_with_count_and_span():
    days = [make_day_column(row_index=row, datum=f"0{row}-11-26") for row in (1, 2, 3, 5)]
    plans = make_plan_views(
        [_entry("a.md", "Algorithmen", (1, 2)), _entry("b.md", "Netze", (3,)), _entry("a.md", "Algorithmen", (5,))]
    )
    assert [view.sequence_path for view in plans] == [Path("a.md"), Path("b.md")]  # eine View je Sequenz
    assert view_for_path(plans, Path("a.md")).blocks[1].member_row_indices == (5,)
    first, second = sequence_choices(plans, days)
    assert (first.title, first.detail) == ("Algorithmen", "3 Einheiten · So 01.11. – Do 05.11.")
    assert first.label == "Algorithmen (3 Einheiten · So 01.11. – Do 05.11.)"
    assert second.title == "Netze"
    assert sequence_choices([], days) == []


def test_a_shared_multi_topic_lzk_counts_for_both_sequences():
    days = [make_day_column(row_index=row, datum=f"0{row}-11-26") for row in (1, 2, 3, 4)]
    plans = make_plan_views(
        [_entry("a.md", "Algorithmen", (1, 2, 3)), _entry("b.md", "Netze", (4,))],
        shared_rows={Path("b.md"): (3,)},
    )
    first, second = sequence_choices(plans, days)
    assert first.detail.startswith("3 Einheiten") and second.detail.startswith("2 Einheiten")
    # Die markierte LZK-Spalte gehört zuerst zur Sequenz, in deren Block sie steht.
    assert view_for_rows(plans, {3}).sequence_path == Path("a.md")
    assert view_for_rows(plans, {4}).sequence_path == Path("b.md")


def test_rungs_carry_their_plan_row_and_open_rungs_none():
    rungs = rung_infos([make_day_column(row_index=4, datum="02-11-26")], 2)
    assert [(rung.row_index, rung.kind) for rung in rungs] == [(4, RungKind.UNTERRICHT), (None, RungKind.OFFEN)]
