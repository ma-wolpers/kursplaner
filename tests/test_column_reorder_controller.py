from types import SimpleNamespace

from kursplaner.adapters.gui.column_reorder_controller import MainWindowColumnReorderController
from tests.day_column_factory import make_day_column


class _TrackedWriteSpy:
    def __init__(self):
        self.labels: list[str] = []

    def run_tracked_action(
        self,
        *,
        label: str,
        action,
        table,
        day_columns,
        selected_day_indices,
        extra_before,
        extra_after,
        extra_after_from_result,
    ):
        self.labels.append(label)
        action()
        return SimpleNamespace(proceed=True)


class _MoveSelectedColumnsSpy:
    def __init__(self):
        self.calls: list[tuple[int, int]] = []
        self.plan_calls: list[tuple[int, int]] = []

    def find_swap_partner(self, day_columns, start_index: int, direction: int):
        probe = start_index + direction
        while 0 <= probe < len(day_columns):
            if not day_columns[probe].is_cancel():
                return probe
            probe += direction
        return None

    def build_move_plan(self, day_columns, selected_index: int, direction: int):
        self.plan_calls.append((selected_index, direction))
        partner = self.find_swap_partner(day_columns, selected_index, direction)
        if partner is None:
            return None
        return SimpleNamespace(partner_index=partner, row_a=selected_index, row_b=partner)

    def execute(self, table, row_a: int, row_b: int):
        self.calls.append((row_a, row_b))
        return None


class _ActionControllerSpy:
    def __init__(self):
        self.update_calls = 0

    def update_action_controls(self):
        self.update_calls += 1


def _build_app(
    *,
    selected_index: int,
    holiday_indices: set[int] | None = None,
    cancel_indices: set[int] | None = None,
    ub_link_by_index: dict[int, str] | None = None,
):
    if holiday_indices is None:
        holiday_indices = set()
    if cancel_indices is None:
        cancel_indices = set()
    if ub_link_by_index is None:
        ub_link_by_index = {}

    tracked = _TrackedWriteSpy()
    move_uc = _MoveSelectedColumnsSpy()
    action_controller = _ActionControllerSpy()

    rows = [
        {"id": "A"},
        {"id": "B"},
        {"id": "C"},
    ]
    day_columns = [
        make_day_column(
            row_index=idx,
            inhalt="Ferien" if idx in holiday_indices else "",
            thema_ausfall="X Ausfall" if idx in cancel_indices else "",
            yaml={"Unterrichtsbesuch": ub_link_by_index[idx]} if idx in ub_link_by_index else {},
        )
        for idx in range(3)
    ]

    app = SimpleNamespace(
        gui_dependencies=SimpleNamespace(tracked_write_usecase=tracked, move_selected_columns=move_uc),
        current_table=SimpleNamespace(rows=rows),
        day_columns=day_columns,
        selected_day_indices={selected_index},
        action_controller=action_controller,
        collect_calls=0,
        refresh_grid_calls=0,
        metrics_calls=0,
        label_calls=0,
        shown_errors=[],
    )

    def _is_holiday_column(day):
        return day.row_index in holiday_indices

    app._is_holiday_column = _is_holiday_column
    app._get_single_selected_or_warn = lambda: selected_index
    app._to_int = lambda value, default=0: int(value) if str(value).strip().lstrip("-").isdigit() else default
    app._collect_day_columns = lambda: setattr(app, "collect_calls", app.collect_calls + 1)
    app._update_selected_column_label = lambda: setattr(app, "label_calls", app.label_calls + 1)
    app._refresh_grid_content = lambda: setattr(app, "refresh_grid_calls", app.refresh_grid_calls + 1)
    app._update_selected_lesson_metrics = lambda: setattr(app, "metrics_calls", app.metrics_calls + 1)

    return app, tracked, move_uc, action_controller


def test_find_swap_partner_does_not_skip_holiday_columns_when_not_cancel():
    app, _tracked, _move_uc, _action_controller = _build_app(selected_index=0, holiday_indices={1})
    controller = MainWindowColumnReorderController(app)

    partner = controller.find_swap_partner(0, 1)

    assert partner == 1


def test_move_selected_columns_swaps_rows_runs_usecase_and_refreshes_ui():
    app, tracked, move_uc, action_controller = _build_app(selected_index=0)
    controller = MainWindowColumnReorderController(app)

    controller.move_selected_columns(1)

    assert move_uc.calls == [(0, 1)]
    assert move_uc.plan_calls == [(0, 1)]
    assert tracked.labels == ["Einheiten verschieben"]
    assert app.selected_day_indices == {1}
    assert app.collect_calls == 1
    assert app.label_calls == 1
    assert app.refresh_grid_calls == 1
    assert app.metrics_calls == 1
    assert action_controller.update_calls == 1


def test_move_selected_columns_skips_cancel_day_via_move_plan():
    app, tracked, move_uc, action_controller = _build_app(selected_index=0, cancel_indices={1})
    controller = MainWindowColumnReorderController(app)

    controller.move_selected_columns(1)

    assert move_uc.calls == [(0, 2)]
    assert tracked.labels == ["Einheiten verschieben"]
    assert app.selected_day_indices == {2}
    assert app.collect_calls == 1
    assert app.label_calls == 1
    assert app.refresh_grid_calls == 1
    assert app.metrics_calls == 1
    assert action_controller.update_calls == 1


def test_move_selected_columns_with_ub_link_requires_confirmation_and_aborts_on_no(monkeypatch):
    app, tracked, move_uc, action_controller = _build_app(
        selected_index=0, ub_link_by_index={1: "[[UB 26-02-27 Supertrumpf Kodierung]]"}
    )
    controller = MainWindowColumnReorderController(app)

    ask_calls = []

    def _askyesno(*args, **kwargs):
        ask_calls.append((args, kwargs))
        return False

    monkeypatch.setattr("kursplaner.adapters.gui.column_reorder_controller.messagebox.askyesno", _askyesno)

    controller.move_selected_columns(1)

    assert len(ask_calls) == 1
    assert move_uc.calls == []
    assert tracked.labels == []
    assert app.collect_calls == 0
    assert app.refresh_grid_calls == 0
    assert app.metrics_calls == 0
    assert action_controller.update_calls == 0


def test_move_selected_columns_with_ub_link_runs_on_yes(monkeypatch):
    app, tracked, move_uc, action_controller = _build_app(
        selected_index=0, ub_link_by_index={0: "[[UB 26-02-06 Fach-Diagnose]]"}
    )
    controller = MainWindowColumnReorderController(app)

    monkeypatch.setattr("kursplaner.adapters.gui.column_reorder_controller.messagebox.askyesno", lambda *a, **k: True)

    controller.move_selected_columns(1)

    assert move_uc.calls == [(0, 1)]
    assert tracked.labels == ["Einheiten verschieben"]
    assert app.selected_day_indices == {1}
    assert app.collect_calls == 1
    assert app.refresh_grid_calls == 1
    assert app.metrics_calls == 1
    assert action_controller.update_calls == 1
