"""Einziger Hauptfenster-Refresh nach Schreibvorgängen (`plan_partial_refresh`), statt Strg+R-Neuladen.

Snapshot und Diff-Refresh des Grids haben eigene Tests (`test_grid_change_refresh.py`);
hier werden sie als Protokolleinträge ``("snapshot",)``/``("refresh",)`` abgefangen.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import kursplaner.adapters.gui.plan_partial_refresh as plan_partial_refresh
from kursplaner.adapters.gui.plan_partial_refresh import refresh_after_files_written, refresh_after_write
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
