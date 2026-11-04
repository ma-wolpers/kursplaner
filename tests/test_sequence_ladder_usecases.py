"""Sequenzleiter-Use-Cases mit echter Undo-Kette und echter Datei (synthetische Daten in tmp_path)."""

from __future__ import annotations

import pytest
from day_column_factory import make_day_column
from kompetenzgraph_test_support import make_bereich, make_node
from test_sequence_plan_repository import _build_table

from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from kursplaner.core.domain.sequence_ladder import BlockRef, LadderSide, LadderSlot
from kursplaner.core.domain.sequence_ladder_ops import AddBlock, RenameBlock, StepBlock
from kursplaner.core.domain.topic_sequence_runs import TopicSequenceRun
from kursplaner.core.usecases.command_executor_usecase import CommandExecutorUseCase
from kursplaner.core.usecases.edit_sequence_ladder_usecase import EditSequenceLadderUseCase
from kursplaner.core.usecases.history_usecase import HistoryUseCase
from kursplaner.core.usecases.load_sequence_ladder_usecase import (
    LoadSequenceLadderUseCase,
    RungKind,
    sequence_term_days,
)
from kursplaner.core.usecases.tracked_write_usecase import TrackedWriteUseCase
from kursplaner.infrastructure.repositories.command_repository import FileSystemCommandRepository
from kursplaner.infrastructure.repositories.sequence_plan_repository import FileSystemSequencePlanRepository

INH = LadderSide.INHALT


@pytest.fixture
def env(tmp_path):
    plan_dir = tmp_path / "M GK test-1 26-2"
    plan_dir.mkdir()
    plan_path = plan_dir / "M GK test-1 26-2.md"
    plan_path.write_text("# Kursplan\n", encoding="utf-8")
    repo = FileSystemSequencePlanRepository()
    path = repo.ensure_sequence_document(table=_build_table(plan_path), sequence_name="Brüche")
    history = HistoryUseCase(CommandExecutorUseCase(command_repo=FileSystemCommandRepository()))
    edit = EditSequenceLadderUseCase(repo, TrackedWriteUseCase(history))
    return repo, path, history, edit


def test_each_operation_is_one_undo_step_and_undo_restores_the_file(env):
    repo, path, history, edit = env
    original = path.read_text(encoding="utf-8")
    assert edit.execute(sequence_path=path, operation=AddBlock(LadderSlot(0, INH, 0), "A")).applied
    assert edit.execute(sequence_path=path, operation=AddBlock(LadderSlot(0, INH, 1), "B")).applied
    after_two = path.read_text(encoding="utf-8")
    stepped = edit.execute(sequence_path=path, operation=StepBlock(BlockRef(0, INH, "B"), up=True))
    assert stepped.applied and stepped.focus == BlockRef(0, INH, "B")
    assert [e.label for e in history.undo_stack] == ["Baustein anlegen", "Baustein anlegen", "Baustein verschieben"]
    history.undo()
    assert path.read_text(encoding="utf-8") == after_two
    history.undo()
    history.undo()
    assert path.read_text(encoding="utf-8") == original
    history.redo()
    assert [b.text for b in repo.read_sequence_ladder(path).rung(0).inhalt] == ["A"]


def test_rule_errors_and_no_ops_create_no_entry(env):
    _repo, path, history, edit = env
    edit.execute(sequence_path=path, operation=AddBlock(LadderSlot(0, INH, 0), "A"))
    result = edit.execute(sequence_path=path, operation=AddBlock(LadderSlot(0, INH, 0), "a"))
    assert not result.applied and "bereits" in result.error
    assert not edit.execute(sequence_path=path, operation=StepBlock(BlockRef(0, INH, "A"), up=False)).applied
    assert not edit.execute(sequence_path=path, operation=RenameBlock(BlockRef(0, INH, "A"), "A")).applied
    assert len(history.undo_stack) == 1


def test_import_competences_reports_problems_and_places_by_area_kind(env):
    repo, path, history, edit = env
    snapshot = build_kompetenz_graph_snapshot(
        [
            make_node("Mat-PL-1", primarer_bereich_id="P-Lösen", title="Probleme lösen"),
            make_node("Mat-X-1", primarer_bereich_id="?"),
        ],
        [make_bereich("P-Lösen", kind="prozessbereich")],
    )
    result = edit.import_competences(sequence_path=path, snapshot=snapshot, kompetenz_ids=["Mat-PL-1", "Mat-X-1"])
    assert result.applied and len(result.notes) == 1
    block = repo.read_sequence_ladder(path).rung(0).prozess[0]
    assert (block.text, block.kompetenz_id) == ("Probleme lösen", "Mat-PL-1")
    assert [e.label for e in history.undo_stack] == ["Kompetenzen übernehmen"]


def test_term_days_cover_members_and_inner_cancellations_of_every_run():
    days = [
        make_day_column(row_index=0, datum="02-11-26", yaml={"Stundentyp": "Unterricht"}),
        make_day_column(row_index=1, datum="03-11-26", thema_ausfall="X Krank"),
        make_day_column(row_index=2, datum="04-11-26", yaml={"Stundentyp": "LZK"}),
        make_day_column(row_index=3, datum="05-11-26", yaml={"Stundentyp": "Unterricht"}),
        make_day_column(row_index=4, datum="06-11-26", yaml={"Stundentyp": "Hospitation"}),
    ]
    runs = [TopicSequenceRun("Brüche", (0, 2)), TopicSequenceRun("Brüche", (4,))]
    assert [d.row_index for d in sequence_term_days(days, runs)] == [0, 1, 2, 4]


def test_load_labels_rungs_and_adds_one_reserve_rung(env):
    repo, path, _history, edit = env
    edit.execute(sequence_path=path, operation=AddBlock(LadderSlot(3, INH, 0), "Oben"))
    lzk_file = path.parent.parent / "Einheiten" / "lzk.md"  # LZK zählt nur mit verlinkter Einheiten-Datei
    lzk_file.parent.mkdir()
    lzk_file.write_text("---\nStundentyp: LZK\n---\n", encoding="utf-8")
    days = [
        make_day_column(row_index=0, datum="02-11-26", yaml={"Stundentyp": "Unterricht"}),
        make_day_column(row_index=1, datum="03-11-26", thema_ausfall="X Krank"),
        make_day_column(row_index=2, datum="04-11-26", inhalt="[[lzk]]", link=lzk_file, yaml={"Stundentyp": "LZK"}),
    ]
    view = LoadSequenceLadderUseCase(repo).execute(
        sequence_path=path, oberthema="Brüche", runs=[TopicSequenceRun("Brüche", (0, 2))], day_columns=days
    )
    assert [(r.date_label, r.kind) for r in view.rungs] == [
        ("Mo 02.11.", RungKind.UNTERRICHT),
        ("Di 03.11.", RungKind.AUSFALL),
        ("Mi 04.11.", RungKind.LZK),
        ("??", RungKind.OFFEN),
        ("??", RungKind.OFFEN),
    ]
    assert view.error is None


def test_load_of_malformed_ladder_is_read_only_with_error(env):
    repo, path, _history, _edit = env
    path.write_text(
        path.read_text(encoding="utf-8").replace("## Export", "## Sequenzleiter\n\nkaputt\n\n## Export"),
        encoding="utf-8",
    )
    view = LoadSequenceLadderUseCase(repo).execute(sequence_path=path, oberthema="Brüche", runs=[], day_columns=[])
    assert view.ladder is None and "Zeile 1" in view.error
