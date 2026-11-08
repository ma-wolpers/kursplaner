"""Sequenzliste für Dialog und Leiter-Auswahl sowie Plan-Zeile je Sprosse (synthetisch)."""

from __future__ import annotations

from pathlib import Path

from kursplaner.adapters.gui.sequence_choices import sequence_choices, views_by_path
from kursplaner.core.domain.topic_sequence_runs import TopicSequenceRun
from kursplaner.core.usecases.load_sequence_ladder_usecase import RungKind, rung_infos
from kursplaner.core.usecases.sync_topic_sequence_plans_usecase import TopicSequencePlanView
from tests.day_column_factory import make_day_column


def _view(path: str, oberthema: str, rows: tuple[int, ...]) -> TopicSequencePlanView:
    return TopicSequencePlanView(
        run=TopicSequenceRun(oberthema=oberthema, member_row_indices=rows),
        sequence_path=Path(path),
        sequenzziel="",
        leitkompetenzen=(),
    )


def test_runs_sharing_a_file_form_one_choice_with_count_and_span():
    days = [make_day_column(row_index=row, datum=f"0{row}-11-26") for row in (1, 2, 3, 5)]
    plans = [_view("a.md", "Algorithmen", (1, 2)), _view("b.md", "Netze", (3,)), _view("a.md", "Algorithmen", (5,))]
    assert list(views_by_path(plans)) == [Path("a.md"), Path("b.md")]
    first, second = sequence_choices(plans, days)
    assert (first.title, first.detail) == ("Algorithmen", "3 Einheiten · So 01.11. – Do 05.11.")
    assert first.label == "Algorithmen (3 Einheiten · So 01.11. – Do 05.11.)"
    assert second.title == "Netze"
    assert sequence_choices([], days) == []


def test_rungs_carry_their_plan_row_and_open_rungs_none():
    rungs = rung_infos([make_day_column(row_index=4, datum="02-11-26")], 2)
    assert [(rung.row_index, rung.kind) for rung in rungs] == [(4, RungKind.UNTERRICHT), (None, RungKind.OFFEN)]
