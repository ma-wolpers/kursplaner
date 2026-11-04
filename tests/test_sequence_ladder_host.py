"""Leiter-Host ohne Fenster: Sequenz der Auswahl, Kontext, Sequenzübersicht, Übernahme-Ziele."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from day_column_factory import make_day_column

from kursplaner.adapters.gui import sequence_ladder_host as host_module
from kursplaner.adapters.gui.sequence_ladder_host import SequenceLadderHost
from kursplaner.core.domain.topic_sequence_runs import TopicSequenceRun
from kursplaner.core.usecases.sync_topic_sequence_plans_usecase import TopicSequencePlanView

A, B = Path("Sequenzen/a Brüche.md"), Path("Sequenzen/a Prozente.md")


def _app(selected=()):
    days = [make_day_column(row_index=i, datum=f"0{i + 2}-11-26") for i in range(6)]
    plans = [
        TopicSequencePlanView(TopicSequenceRun("Brüche", (0, 2)), A, "", ()),
        TopicSequencePlanView(TopicSequenceRun("Prozente", (3, 4)), B, "", ()),
        TopicSequencePlanView(TopicSequenceRun("Brüche", (5,)), A, "", ()),
    ]
    return SimpleNamespace(
        topic_sequence_plans=plans, raw_day_columns=days, day_columns=days, selected_day_indices=set(selected)
    )


def test_selected_column_inside_a_run_picks_its_sequence():
    assert SequenceLadderHost(_app(selected={1})).selected_sequence_path() == A
    assert SequenceLadderHost(_app(selected={4})).selected_sequence_path() == B
    assert SequenceLadderHost(_app()).selected_sequence_path() is None


def test_context_unites_all_runs_of_one_file():
    oberthema, runs, days = SequenceLadderHost(_app())._context(A)
    assert oberthema == "Brüche" and [r.member_row_indices for r in runs] == [(0, 2), (5,)]
    assert len(days) == 6
    assert SequenceLadderHost(_app())._context(Path("fehlt.md")) is None


def test_overview_offers_each_file_once_with_count_and_span(monkeypatch):
    seen = {}

    def fake_askchoice(self, title, message, options, **kw):
        seen["options"] = options
        return options[1].key

    monkeypatch.setattr(host_module.ChoiceDialogService, "askchoice", fake_askchoice)
    assert SequenceLadderHost(_app()).choose_sequence() == B
    first = seen["options"][0]
    assert (first.label, first.description) == ("Brüche", "3 Einheiten · Mo 02.11. – Sa 07.11.")


def test_free_target_asks_for_the_sequence_then_imports(monkeypatch):
    host = SequenceLadderHost(_app())
    calls = []
    monkeypatch.setattr(host, "choose_sequence", lambda **kw: B)
    monkeypatch.setattr(host, "import_into", lambda path, snapshot, ids: calls.append((path, list(ids))))
    target = host.free_import_target()
    assert target.button_label(2) == "Zu einer Sequenz hinzufügen… (2)"
    target.import_ids(["Mat-1", "Mat-2"], snapshot=None)
    assert calls == [(B, ["Mat-1", "Mat-2"])]
