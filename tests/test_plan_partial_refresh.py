"""Einziger Hauptfenster-Refresh nach Schreibvorgängen (`plan_partial_refresh`), statt Strg+R-Neuladen.

Snapshot und Diff-Refresh des Grids haben eigene Tests (`test_grid_change_refresh.py`);
hier werden sie als Protokolleinträge ``("snapshot",)``/``("refresh",)`` abgefangen.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import kursplaner.adapters.gui.plan_partial_refresh as plan_partial_refresh
from kursplaner.adapters.gui.plan_partial_refresh import (
    refresh_after_files_written,
    refresh_after_history_step,
    refresh_after_write,
)
from kursplaner.core.usecases.load_plan_detail_usecase import LoadPlanDetailUseCase


@pytest.fixture(autouse=True)
def _grid_diff_spy(monkeypatch):
    """Ersetzt Snapshot/Diff-Refresh durch Protokolleinträge in ``app.calls``."""
    monkeypatch.setattr(plan_partial_refresh, "capture_grid_snapshot", lambda app: app.calls.append(("snapshot",)))
    monkeypatch.setattr(
        plan_partial_refresh, "refresh_grid_changes", lambda app, before: app.calls.append(("refresh",))
    )


def _app(tmp_path: Path, calls: list):
    units = [tmp_path / "Einheiten" / f"{stem}.md" for stem in ("aaaaaa", "bbbbbb")]
    days = [
        SimpleNamespace(row_index=0, link=units[0].resolve()),
        SimpleNamespace(row_index=1, link=None),
        SimpleNamespace(row_index=2, link=units[1].resolve()),
        SimpleNamespace(row_index=3, link=units[0].resolve()),  # zweite Zeile mit derselben Datei
    ]

    def forbidden(name):
        return lambda *a, **k: calls.append(("VERBOTEN", name))

    app = SimpleNamespace(
        calls=calls,
        current_table=SimpleNamespace(markdown_path=tmp_path / "Kurs.md"),
        raw_day_columns=days,
        day_columns=days,
        selected_day_indices={0},
        _collect_day_columns=lambda rows=None: calls.append(("collect", rows)),
        _update_selected_column_label=lambda: calls.append(("label",)),
        _update_selected_lesson_metrics=lambda: calls.append(("metrics",)),
        _refresh_grid_content=forbidden("_refresh_grid_content"),
        _rebuild_grid=forbidden("_rebuild_grid"),
        overview_controller=SimpleNamespace(reload_keeping_view=forbidden("reload_keeping_view")),
        action_controller=SimpleNamespace(update_action_controls=lambda: calls.append(("actions",))),
    )
    return app, units


def test_only_rows_of_written_units_are_reread_without_full_reload(tmp_path):
    calls: list = []
    app, units = _app(tmp_path, calls)
    sequence_file = tmp_path / "Sequenzen" / "Brüche.md"

    refresh_after_files_written(app, (units[0], sequence_file))

    assert calls == [("snapshot",), ("collect", {0, 3}), ("refresh",)]


def test_ablage_only_write_leaves_the_grid_alone(tmp_path):
    calls: list = []
    app, _units = _app(tmp_path, calls)

    refresh_after_files_written(app, (tmp_path / "Sequenzen" / "Brüche.md",))

    assert calls == [("actions",)]


def test_written_plan_file_rederives_all_columns_without_full_reload(tmp_path):
    calls: list = []
    app, units = _app(tmp_path, calls)

    refresh_after_files_written(app, (tmp_path / "Kurs.md", units[1]))

    assert calls == [("snapshot",), ("collect", None), ("refresh",)]


def test_rows_linking_resolves_paths(tmp_path):
    _app_ns, units = _app(tmp_path, [])
    relative_style = units[1].parent / ".." / "Einheiten" / units[1].name

    assert LoadPlanDetailUseCase.rows_linking(_app_ns.raw_day_columns, [relative_style]) == {2}
    assert LoadPlanDetailUseCase.rows_linking(_app_ns.raw_day_columns, []) == set()


def test_refresh_after_write_snapshots_before_collect_then_selects_patches_and_updates_metrics(tmp_path):
    calls: list = []
    app, _units = _app(tmp_path, calls)

    refresh_after_write(app, selected_index=2, changed_rows={1, 2})

    assert calls == [("snapshot",), ("collect", {1, 2}), ("label",), ("refresh",), ("metrics",)]
    assert app.selected_day_indices == {2}


def test_refresh_after_write_without_known_rows_rereads_all_and_keeps_invalid_selection(tmp_path):
    calls: list = []
    app, _units = _app(tmp_path, calls)

    refresh_after_write(app, selected_index=99)

    assert calls == [("snapshot",), ("collect", None), ("refresh",), ("metrics",)]
    assert app.selected_day_indices == {0}


def _history_app(tmp_path: Path, calls: list, *, fresh_rows=None):
    """Offener Kurs mit Plan ``Kurs.md``, Einheiten ``Einheiten/`` und Sequenzordner; Plan-Reload protokolliert."""
    app, units = _app(tmp_path, calls)
    app.current_table = SimpleNamespace(
        markdown_path=tmp_path / "Kurs.md", rows=[["a"], ["b"], ["c"], ["d"]], headers=["Datum"], metadata={}
    )
    fresh = SimpleNamespace(
        markdown_path=tmp_path / "Kurs.md",
        rows=fresh_rows if fresh_rows is not None else [["a"], ["B"], ["c"], ["d"]],
        headers=["Datum"],
        metadata={},
    )

    def load_table(path):
        calls.append(("load_table", Path(path).name))
        return fresh

    app.gui_dependencies = SimpleNamespace(load_plan_detail_usecase=SimpleNamespace(load_table=load_table))
    return app, units, fresh


def _entry(*paths):
    return SimpleNamespace(deltas=[SimpleNamespace(path=path) for path in paths])


def test_history_step_in_course_rereads_only_plan_and_changed_rows(tmp_path):
    calls: list = []
    app, units, fresh = _history_app(tmp_path, calls)

    handled = refresh_after_history_step(app, _entry(tmp_path / "Kurs.md", units[1]))

    assert handled is True
    assert app.current_table is fresh
    # Zeile 1 im Plan geändert, Zeile 2 verlinkt die zurückgeschriebene Einheit.
    assert calls == [("load_table", "Kurs.md"), ("snapshot",), ("collect", {1, 2}), ("refresh",), ("metrics",)]


def test_history_step_with_new_unit_file_in_lesson_folder_stays_targeted(tmp_path):
    calls: list = []
    app, _units, _fresh = _history_app(tmp_path, calls)

    handled = refresh_after_history_step(app, _entry(tmp_path / "Kurs.md", tmp_path / "Einheiten" / "neu123.md"))

    assert handled is True


def test_history_step_with_only_sequence_file_rederives_without_plan_reload(tmp_path):
    calls: list = []
    app, _units, _fresh = _history_app(tmp_path, calls)

    handled = refresh_after_history_step(app, _entry(tmp_path / "Sequenzen" / "Brüche.md"))

    assert handled is True
    assert calls == [("snapshot",), ("collect", set()), ("refresh",), ("metrics",)]


def test_history_step_outside_course_needs_full_reload(tmp_path):
    calls: list = []
    app, _units, _fresh = _history_app(tmp_path, calls)

    assert refresh_after_history_step(app, _entry(tmp_path.parent / "UBs" / "UB 26-11-30.md")) is False
    assert calls == []


def test_history_step_with_changed_row_count_needs_full_reload(tmp_path):
    calls: list = []
    app, _units, _fresh = _history_app(tmp_path, calls, fresh_rows=[["a"], ["b"], ["c"]])
    old_table = app.current_table

    assert refresh_after_history_step(app, _entry(tmp_path / "Kurs.md")) is False
    assert app.current_table is old_table


def test_history_step_without_entry_or_plan_needs_full_reload(tmp_path):
    calls: list = []
    app, _units, _fresh = _history_app(tmp_path, calls)

    assert refresh_after_history_step(app, None) is False
    app.current_table = None
    assert refresh_after_history_step(app, _entry(tmp_path / "Kurs.md")) is False
