"""Diff-Refresh des Plan-Grids (`grid_change_refresh`): nur die nachweisliche Differenz wird gepatcht."""

from __future__ import annotations

from types import SimpleNamespace

from kursplaner.adapters.gui.grid_change_refresh import capture_grid_snapshot, refresh_grid_changes
from tests.day_column_factory import make_day_column


class _RendererSpy:
    def __init__(self, app, calls):
        self.app = app
        self.calls = calls
        self.layouts = {"inhalt": (2, False, False, "Inhalt"), "Stundenthema": (2, False, False, "Thema")}
        self.structure_ok = True
        self.next_unit_index = 0

    def apply_header_style(self, day_index):
        self.calls.append(("header", day_index))

    def row_layout_snapshot(self):
        return dict(self.layouts)

    def _grid_structure_matches_state(self):
        return self.structure_ok

    def set_next_unit_index(self, index):
        self.calls.append(("next_unit", index))
        self.next_unit_index = index

    def update_row_style(self, field_key):
        self.calls.append(("row_style", field_key))

    def update_column_cells(self, day_index):
        self.calls.append(("cells", day_index))

    def remount_sequence_fields(self):
        self.calls.append(("sequence_spans",))


def _app(days, *, selected=(0,), sequences=(), sequence_fields_visible=True, next_unit=0):
    calls: list = []
    app = SimpleNamespace(
        day_columns=list(days),
        selected_day_indices=set(selected),
        ui_state=SimpleNamespace(selected_cell=None),
        topic_sequence_plans=list(sequences),
        header_labels={idx: object() for idx in range(len(days))},
        _is_rebuilding_grid=False,
        sequence_fields_visible_var=SimpleNamespace(get=lambda: sequence_fields_visible),
        overview_controller=SimpleNamespace(_next_lesson_column_index=lambda: next_unit),
        _refresh_header_styles=lambda: calls.append(("ALL_HEADERS",)),
        _on_grid_inner_configure=lambda: calls.append(("scrollregion",)),
        _refresh_grid_content=lambda: calls.append(("FULL_REFRESH",)),
        _rebuild_grid=lambda: calls.append(("REBUILD",)),
        action_controller=SimpleNamespace(update_action_controls=lambda: calls.append(("actions",))),
    )
    app.grid_renderer = _RendererSpy(app, calls)
    return app, calls


def _days(*contents):
    return [make_day_column(row_index=idx, inhalt=text) for idx, text in enumerate(contents)]


def _sequence(oberthema, rows, ziel=""):
    return SimpleNamespace(
        run=SimpleNamespace(oberthema=oberthema, member_row_indices=tuple(rows)), sequenzziel=ziel, leitkompetenzen=()
    )


def test_swap_patches_only_the_two_swapped_columns_and_tail_once():
    app, calls = _app(_days("[[a]]", "[[b]]", "[[c]]", "[[d]]"), selected=(1,))
    before = capture_grid_snapshot(app)
    app.day_columns = _days("[[a]]", "[[c]]", "[[b]]", "[[d]]")
    app.selected_day_indices = {2}

    refresh_grid_changes(app, before)

    assert calls == [
        ("next_unit", 0),
        ("cells", 1),
        ("cells", 2),
        ("header", 0),  # unveränderte next_unit-Spalte: billig, aber nicht ausgelassen
        ("header", 1),
        ("header", 2),
        ("scrollregion",),
        ("actions",),
    ]


def test_moving_next_unit_restyles_old_and_new_next_unit_headers_only():
    app, calls = _app(_days("[[a]]", "[[b]]", "[[c]]", "[[d]]"), selected=(), next_unit=3)
    app.grid_renderer.next_unit_index = 1
    before = capture_grid_snapshot(app)

    refresh_grid_changes(app, before)

    assert [call for call in calls if call[0] == "header"] == [("header", 1), ("header", 3)]
    assert [call for call in calls if call[0] == "cells"] == []


def test_unchanged_columns_outside_selection_are_not_touched():
    app, calls = _app(_days("[[a]]", "[[b]]", "[[c]]"), selected=(0,))
    before = capture_grid_snapshot(app)

    refresh_grid_changes(app, before)

    assert [call for call in calls if call[0] == "cells"] == [("cells", 0)]


def test_changed_field_layout_restyles_that_row():
    app, calls = _app(_days("[[a]]", "[[b]]"), selected=())
    before = capture_grid_snapshot(app)
    app.grid_renderer.layouts["Stundenthema"] = (5, True, True, "▾ Thema")

    refresh_grid_changes(app, before)

    assert ("row_style", "Stundenthema") in calls
    assert ("row_style", "inhalt") not in calls


def test_different_visible_columns_fall_back_to_full_refresh():
    app, calls = _app(_days("[[a]]", "[[b]]", "[[c]]"))
    before = capture_grid_snapshot(app)
    app.day_columns = _days("[[a]]", "[[b]]")

    refresh_grid_changes(app, before)

    assert calls == [("FULL_REFRESH",)]


def test_structure_mismatch_falls_back_to_full_refresh():
    app, calls = _app(_days("[[a]]", "[[b]]"))
    before = capture_grid_snapshot(app)
    app.grid_renderer.structure_ok = False

    refresh_grid_changes(app, before)

    assert calls == [("FULL_REFRESH",)]


def test_changed_sequence_span_remounts_only_the_spans_then_patches_normally():
    app, calls = _app(_days("[[a]]", "[[b]]", "[[c]]"), selected=(), sequences=[_sequence("Brüche", (0, 1))])
    before = capture_grid_snapshot(app)
    app.topic_sequence_plans = [_sequence("Brüche", (1, 2))]

    refresh_grid_changes(app, before)

    assert calls[0] == ("sequence_spans",)
    assert ("REBUILD",) not in calls and ("FULL_REFRESH",) not in calls
    assert calls[-1] == ("actions",)


def test_changed_sequence_goal_remounts_but_hidden_sequence_fields_do_not():
    app, calls = _app(_days("[[a]]", "[[b]]"), sequences=[_sequence("Brüche", (0, 1), "alt")])
    before = capture_grid_snapshot(app)
    app.topic_sequence_plans = [_sequence("Brüche", (0, 1), "neu")]
    refresh_grid_changes(app, before)
    assert ("sequence_spans",) in calls

    hidden, hidden_calls = _app(
        _days("[[a]]", "[[b]]"), sequences=[_sequence("Brüche", (0, 1), "alt")], sequence_fields_visible=False
    )
    before_hidden = capture_grid_snapshot(hidden)
    hidden.topic_sequence_plans = [_sequence("Brüche", (0, 1), "neu")]
    refresh_grid_changes(hidden, before_hidden)
    assert ("sequence_spans",) not in hidden_calls


def test_sequence_rows_appearing_or_vanishing_rebuild_the_grid():
    app, calls = _app(_days("[[a]]", "[[b]]"), sequences=[])
    before = capture_grid_snapshot(app)
    app.topic_sequence_plans = [_sequence("Brüche", (0, 1))]

    refresh_grid_changes(app, before)

    assert calls == [("REBUILD",)]


def test_selected_cell_column_is_patched_before_and_after():
    app, calls = _app(_days("[[a]]", "[[b]]", "[[c]]"), selected=())
    app.ui_state.selected_cell = SimpleNamespace(day_index=0, field_key="inhalt")
    before = capture_grid_snapshot(app)
    app.ui_state.selected_cell = SimpleNamespace(day_index=2, field_key="inhalt")

    refresh_grid_changes(app, before)

    assert [call for call in calls if call[0] == "cells"] == [("cells", 0), ("cells", 2)]


def test_noop_while_grid_is_rebuilding():
    app, calls = _app(_days("[[a]]"))
    before = capture_grid_snapshot(app)
    app._is_rebuilding_grid = True

    refresh_grid_changes(app, before)

    assert calls == []
