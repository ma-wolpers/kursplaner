"""Plan-Zeile → Tagesspalte und Lauf-Spanne: je eine Quelle (synthetisch)."""

from __future__ import annotations

from kursplaner.core.domain.day_column import day_for_row, day_index_for_row, days_by_row
from kursplaner.core.domain.topic_sequence_runs import TopicSequenceRun
from tests.day_column_factory import make_day_column


def test_lookup_by_row_skips_foreign_entries_and_reports_missing_rows():
    days = [make_day_column(row_index=4), "keine Spalte", make_day_column(row_index=7)]
    assert day_index_for_row(days, 7) == 2
    assert day_for_row(days, 4) is days[0]
    assert day_index_for_row(days, 5) is None and day_for_row(days, 5) is None
    assert set(days_by_row(days)) == {4, 7}


def test_run_span_includes_gaps_between_first_and_last_member():
    run = TopicSequenceRun(oberthema="Algorithmen", member_row_indices=(2, 3, 6))
    assert [row for row in range(1, 8) if run.covers(row)] == [2, 3, 4, 5, 6]
    assert not TopicSequenceRun(oberthema="leer", member_row_indices=()).covers(0)
