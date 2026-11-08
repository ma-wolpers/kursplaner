"""Dialogablauf „Sprosse zuordnen“ ohne Tk: Auswahl, Fehler, Rückfrage, Abbruch."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from day_column_factory import make_day_column

from kursplaner.adapters.gui.sequence_ladder_assign_flow import (
    NEW_UNIT_HINT,
    SUGGESTION_SUFFIX,
    AssignRungFlow,
    target_options,
)
from kursplaner.core.usecases.assign_ablage_rung_usecase import AssignCheck, AssignTargets
from kursplaner.core.usecases.edit_sequence_ladder_usecase import EditSequenceLadderResult

DAYS = [
    make_day_column(row_index=0, datum="02-11-26", link=Path("u0.md"), yaml={"Stundenthema": "Brüche kürzen"}),
    make_day_column(row_index=1, datum="05-11-26"),
]


class _Dialogs:
    def __init__(self, choice="1", confirm=True):
        self.choice, self.answer = choice, confirm
        self.offered, self.confirms, self.errors, self.infos = [], [], [], []

    def choose(self, title, prompt, options):
        self.offered = list(options)
        return self.choice

    def confirm(self, title, message):
        self.confirms.append(message)
        return self.answer

    def show_error(self, title, message):
        self.errors.append(message)

    def show_info(self, title, message):
        self.infos.append(message)


class _UseCase:
    def __init__(self, check: AssignCheck):
        self._check, self.executed = check, []

    def targets(self, *, runs, day_columns):
        return AssignTargets(tuple(day_columns), suggested_row=1)

    def check(self, **kwargs):
        return self._check

    def execute(self, **kwargs):
        self.executed.append(kwargs)
        return EditSequenceLadderResult(True, None, written=(Path("u0.md"),))


def _flow(check=AssignCheck(), **dialog_args):
    dialogs, usecase = _Dialogs(**dialog_args), _UseCase(check)
    flow = AssignRungFlow(usecase=usecase, dialogs=dialogs, sequence_path=Path("s.md"), table=lambda: object())
    return flow, dialogs, usecase


def test_options_mark_the_suggestion_and_explain_empty_rows():
    options = target_options(DAYS, suggested_row=1)
    assert options[0] == ("0", "Mo 02.11.", "Brüche kürzen")
    assert options[1] == ("1", "Do 05.11." + SUGGESTION_SUFFIX, NEW_UNIT_HINT)


def test_warning_declined_writes_nothing():
    flow, dialogs, usecase = _flow(AssignCheck(warnings=("Kompetenzen werden ersetzt:\n  • K",)), confirm=False)
    assert flow(2, ("Brüche", [], DAYS)) is None
    assert "Kompetenzen werden ersetzt" in dialogs.confirms[0] and usecase.executed == []


def test_error_is_shown_and_cancel_aborts():
    flow, dialogs, usecase = _flow(AssignCheck(error="Do 05.11.: LZK – dorthin kann keine Sprosse zugeordnet werden."))
    assert flow(2, ("Brüche", [], DAYS)) is None and "LZK" in dialogs.errors[0] and usecase.executed == []
    flow, _dialogs, usecase = _flow(choice=None)
    assert flow(2, ("Brüche", [], DAYS)) is None and usecase.executed == []


def test_confirmed_or_unproblematic_target_is_written_with_the_chosen_row():
    flow, dialogs, usecase = _flow(AssignCheck(creates_file=True))
    result = flow(2, ("Brüche", [], DAYS))
    assert result.applied and dialogs.confirms == []
    assert (usecase.executed[0]["rung"], usecase.executed[0]["target_row"]) == (2, 1)


def test_controller_finishes_an_assignment_like_every_other_action(tmp_path):
    from sequence_ladder_test_support import make_ladder_env

    from kursplaner.adapters.gui.sequence_ladder_board_mapping import rung_key
    from kursplaner.adapters.gui.sequence_ladder_controller import SequenceLadderController

    env = make_ladder_env(tmp_path, "U")
    written, calls = [], []

    def assign(rung, context):
        calls.append((rung, context[0]))
        return EditSequenceLadderResult(True, None, written=(env.units[0],))

    controller = SequenceLadderController(
        sequence_path=env.sequence_path,
        load=env.load,
        edit=env.edit,
        context=lambda: env.context,
        dialogs=SimpleNamespace(),
        render=lambda *args: None,
        after_write=written.append,
        assign=assign,
    )
    controller.reload()
    controller.assign_rung(rung_key(1))
    assert calls == [(1, "Brüche")] and written == [(env.units[0],)]
