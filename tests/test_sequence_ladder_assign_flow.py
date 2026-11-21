"""Dialogablauf „Sprosse zuordnen“ ohne Tk: Liste, Rückfragen je Zielart, Abbruch (synthetische Daten)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from day_column_factory import make_day_column

from kursplaner.adapters.gui.sequence_ladder_assign_flow import (
    MEMBER_HINT,
    NEW_UNIT_HINT,
    SUGGESTION_PREFIX,
    AssignRungFlow,
    target_options,
)
from kursplaner.core.domain.sequence_ladder_assign import TargetKind
from kursplaner.core.usecases.assign_ablage_rung_usecase import AssignCheck, AssignTarget, AssignTargets
from kursplaner.core.usecases.edit_sequence_ladder_usecase import EditSequenceLadderResult

K = TargetKind
DAYS = [
    make_day_column(row_index=0, datum="02-11-26", link=Path("u0.md"), yaml={"Stundenthema": "Brüche kürzen"}),
    make_day_column(row_index=1, datum="03-11-26", link=Path("u1.md"), yaml={"Stundenthema": "Erweitern"}),
    make_day_column(row_index=2, datum="04-11-26", thema_ausfall="X Wandertag"),
    make_day_column(row_index=3, datum="05-11-26", yaml={"Stundenthema": "Winkel", "Oberthema": "Geometrie"}),
    make_day_column(row_index=4, datum="06-11-26"),
    make_day_column(row_index=5, datum="09-11-26", yaml={"Stundenthema": "Offen"}),
]
KINDS = [K.MEMBER, K.MEMBER, K.BLOCKED, K.OCCUPIED, K.FREE, K.LOOSE_UNIT]
TARGETS = AssignTargets(tuple(AssignTarget(d, k) for d, k in zip(DAYS, KINDS)), suggested_row=3)


class _Dialogs:
    def __init__(self, choices=("4",), confirm=True):
        self.choices, self.answer = list(choices), confirm
        self.offered, self.confirms, self.errors, self.infos = [], [], [], []

    def choose(self, title, prompt, options):
        self.offered.append(list(options))
        return self.choices.pop(0) if self.choices else None

    def confirm(self, title, message):
        self.confirms.append(message)
        return self.answer

    def show_error(self, title, message):
        self.errors.append(message)

    def show_info(self, title, message):
        self.infos.append(message)


class _UseCase:
    def __init__(self, check: AssignCheck):
        self._check, self.checks, self.executed = check, [], []

    def targets(self, *, runs, day_columns):
        return TARGETS

    def check(self, **kwargs):
        self.checks.append(kwargs)
        return self._check

    def execute(self, **kwargs):
        self.executed.append(kwargs)
        return EditSequenceLadderResult(True, None, written=(Path("u0.md"),))


def _flow(check=AssignCheck(), **dialog_args):
    dialogs, usecase = _Dialogs(**dialog_args), _UseCase(check)
    flow = AssignRungFlow(usecase=usecase, dialogs=dialogs, sequence_path=Path("s.md"), table=lambda: object())
    return flow, dialogs, usecase


def _run(flow):
    return flow(6, ("Brüche", [], DAYS))


def test_list_is_chronological_with_members_merged_greyed_and_the_suggestion_emphasized():
    options = target_options(TARGETS)
    assert [o.key for o in options] == ["member:0", "2", "3", "4", "5"]
    members = options[0]
    assert (members.label, members.description, members.enabled) == (
        "Sprossen 1–2 · Mo 02.11. – Di 03.11.",
        MEMBER_HINT,
        False,
    )
    assert options[1].enabled is False and "Ausfall" in options[1].label and options[1].description
    suggestion = options[2]
    assert suggestion.label == SUGGESTION_PREFIX + "Do 05.11." and suggestion.emphasized and suggestion.enabled
    assert "Winkel" in suggestion.description and "„Geometrie“" in suggestion.description
    assert options[3].description == NEW_UNIT_HINT and not options[3].emphasized
    assert "ohne Oberthema" in options[4].description


def test_free_row_is_written_without_questions():
    flow, dialogs, usecase = _flow(AssignCheck(creates_file=True), choices=("4",))
    assert _run(flow).applied and dialogs.confirms == []
    assert (usecase.executed[0]["target_row"], usecase.executed[0]["merge"]) == (4, False)


def test_other_sequence_asks_before_shifting_and_declining_writes_nothing():
    flow, dialogs, usecase = _flow(AssignCheck(creates_file=True, shifted=3), choices=("3",), confirm=False)
    assert _run(flow) is None and usecase.executed == []
    assert "3 Einheiten rücken" in dialogs.confirms[0] and "LZKs bleiben stehen" in dialogs.confirms[0]


def test_loose_unit_offers_insert_or_merge():
    flow, dialogs, usecase = _flow(AssignCheck(creates_file=True, shifted=1), choices=("5", "insert"))
    assert _run(flow).applied and dialogs.confirms == [] and usecase.executed[0]["merge"] is False
    assert [o.key for o in dialogs.offered[1]] == ["insert", "merge"] and dialogs.offered[1][0].emphasized

    flow, dialogs, usecase = _flow(
        AssignCheck(warnings=("Kompetenzen werden ersetzt:\n  • K",)), choices=("5", "merge")
    )
    assert _run(flow).applied and usecase.executed[0]["merge"] is True
    assert "Kompetenzen werden ersetzt" in dialogs.confirms[0]


def test_loose_unit_without_free_slot_only_allows_merge():
    flow, dialogs, _usecase = _flow(AssignCheck(error="Bis zum Planende ist kein Termin frei"), choices=("5", None))
    assert _run(flow) is None
    insert = dialogs.offered[1][0]
    assert insert.enabled is False and "kein Termin frei" in insert.description


def test_error_is_shown_and_cancel_or_a_greyed_key_aborts():
    flow, dialogs, usecase = _flow(AssignCheck(error="kaputt"), choices=("4",))
    assert _run(flow) is None and dialogs.errors == ["kaputt"] and usecase.executed == []
    for key in (None, "member:0", "2"):
        flow, _dialogs, usecase = _flow(choices=(key,))
        assert _run(flow) is None and usecase.checks == [] and usecase.executed == []


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
        text_input=SimpleNamespace(),
        render=lambda *args: None,
        after_write=written.append,
        assign=assign,
    )
    controller.reload()
    controller.assign_rung(rung_key(1))
    assert calls == [(1, "Brüche")] and written == [(env.units[0],)]
