from kursplaner.adapters.gui.sequence_field_grid_renderer import SequenceFieldGridRenderer


def test_run_span_bridges_marker_gap_between_member_columns():
    # Tag 0 -> grid_col 0, Marker -> grid_col 1 (kein Eintrag), Tag 1 -> grid_col 2.
    row_index_to_grid_col = {0: 0, 1: 2}

    span = SequenceFieldGridRenderer._run_span(row_index_to_grid_col, first_row_index=0, last_row_index=1)

    assert span == range(0, 3)


def test_run_span_bridges_skipped_ausfall_row():
    # row_index 1 (Ausfall) hat keinen Eintrag, gehört aber zur Lauf-Spanne.
    row_index_to_grid_col = {0: 0, 2: 2}

    span = SequenceFieldGridRenderer._run_span(row_index_to_grid_col, first_row_index=0, last_row_index=2)

    assert span == range(0, 3)


def test_run_span_single_member_is_span_of_one():
    row_index_to_grid_col = {5: 7}

    span = SequenceFieldGridRenderer._run_span(row_index_to_grid_col, first_row_index=5, last_row_index=5)

    assert span == range(7, 8)


def test_run_span_returns_none_when_no_member_visible():
    row_index_to_grid_col: dict[int, int] = {}

    span = SequenceFieldGridRenderer._run_span(row_index_to_grid_col, first_row_index=0, last_row_index=3)

    assert span is None
