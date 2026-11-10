"""Einziger Tracked-Write-Weg des Hauptfensters (`plan_tracked_write`)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from kursplaner.adapters.gui.plan_tracked_write import run_plan_tracked_write


class _TrackedSpy:
    def __init__(self):
        self.calls: list[dict] = []

    def run_tracked_action(self, **kwargs):
        self.calls.append(kwargs)
        return kwargs["action"]()


def _app(*, table=True, selected=frozenset({1})):
    return SimpleNamespace(
        current_table=SimpleNamespace(markdown_path=Path("Kurs.md")) if table else None,
        day_columns=["a", "b", "c"],
        selected_day_indices=set(selected),
    )


def test_without_plan_runs_action_untracked():
    spy = _TrackedSpy()

    result = run_plan_tracked_write(_app(table=False), spy, label="x", action=lambda: 42)

    assert result == 42
    assert spy.calls == []


def test_forwards_plan_state_and_extras():
    spy = _TrackedSpy()
    app = _app()
    before = [Path("a.md")]

    result = run_plan_tracked_write(
        app, spy, label="Verschieben", action=lambda: "ok", extra_before=before, extra_after=[Path("b.md")]
    )

    assert result == "ok"
    (call,) = spy.calls
    assert call["label"] == "Verschieben"
    assert call["table"] is app.current_table
    assert call["day_columns"] is app.day_columns
    assert call["selected_day_indices"] == {1}
    assert call["extra_before"] == before
    assert call["extra_after"] == [Path("b.md")]
    assert call["extra_after_from_result"] is None


def test_include_day_index_adds_column_without_mutating_selection():
    spy = _TrackedSpy()
    app = _app(selected={1})

    run_plan_tracked_write(app, spy, label="Zelle", action=lambda: None, include_day_index=2)

    assert spy.calls[0]["selected_day_indices"] == {1, 2}
    assert app.selected_day_indices == {1}
