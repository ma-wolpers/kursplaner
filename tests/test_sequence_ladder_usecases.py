"""Sequenzleiter-Use-Cases mit echter Undo-Kette und echten Dateien (synthetische Daten in tmp_path).

Sprossen mit Unterrichts-Termin leben in ihren Einheiten (Stundenziel/Teilziele/Kompetenzen,
``## Ideen``), Sprossen jenseits der Termine in der Ablage der Sequenzdatei (§37).
"""

from __future__ import annotations

import pytest
from day_column_factory import make_day_column
from kompetenzgraph_test_support import make_bereich, make_node
from sequence_ladder_test_support import EBW_MARKER, make_ladder_env

from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from kursplaner.core.domain.sequence_ladder import BlockRef, LadderSide, LadderSlot
from kursplaner.core.domain.sequence_ladder_ops import (
    AddBlock,
    MoveBlock,
    RemoveBlock,
    RenameBlock,
    SetIdeas,
    StepBlock,
)
from kursplaner.core.domain.topic_sequence_runs import TopicSequenceRun
from kursplaner.core.usecases.lesson_edit_usecase import LessonEditUseCase
from kursplaner.core.usecases.load_sequence_ladder_usecase import RungKind, sequence_term_days
from kursplaner.infrastructure.repositories.lesson_repository import FileSystemLessonRepository
from kursplaner.infrastructure.repositories.plan_table_file_repository import load_linked_lesson_yaml

INH, PRO = LadderSide.INHALT, LadderSide.PROZESS


def _yaml(path):
    return load_linked_lesson_yaml(path).data


def _texts(files):
    return {path: path.read_text(encoding="utf-8") for path in files}


# -- Ablage (Sprossen ohne Termin) ---------------------------------------------------


def test_ablage_operations_are_one_undo_step_each_and_undo_restores_the_file(tmp_path):
    env = make_ladder_env(tmp_path)
    original = env.sequence_path.read_text(encoding="utf-8")
    assert env.execute(AddBlock(LadderSlot(0, INH, 0), "A")).applied
    assert env.execute(AddBlock(LadderSlot(0, INH, 1), "B")).applied
    after_two = env.sequence_path.read_text(encoding="utf-8")
    stepped = env.execute(StepBlock(BlockRef(0, INH, "B"), up=True))
    assert stepped.applied and stepped.focus == BlockRef(0, INH, "B")
    assert [e.label for e in env.history.undo_stack] == ["Baustein anlegen", "Baustein anlegen", "Baustein verschieben"]
    env.history.undo()
    assert env.sequence_path.read_text(encoding="utf-8") == after_two
    env.history.undo()
    env.history.undo()
    assert env.sequence_path.read_text(encoding="utf-8") == original
    env.history.redo()
    assert [b.text for b in env.sequence_repo.read_ladder_ablage(env.sequence_path).rung(0).inhalt] == ["A"]


def test_rule_errors_and_no_ops_create_no_entry(tmp_path):
    env = make_ladder_env(tmp_path)
    env.execute(AddBlock(LadderSlot(0, INH, 0), "A"))
    result = env.execute(AddBlock(LadderSlot(0, INH, 0), "a"))
    assert not result.applied and "bereits" in result.error
    assert not env.execute(StepBlock(BlockRef(0, INH, "A"), up=False)).applied
    assert not env.execute(RenameBlock(BlockRef(0, INH, "A"), "A")).applied
    assert not env.execute(AddBlock(LadderSlot(0, INH, 0), "---")).applied  # Listenvertrag
    assert len(env.history.undo_stack) == 1


def test_load_of_malformed_ablage_is_read_only_with_error(tmp_path):
    env = make_ladder_env(tmp_path, "U")
    text = env.sequence_path.read_text(encoding="utf-8")
    env.sequence_path.write_text(text.replace("## Export", "## Sequenzleiter\n\nkaputt\n\n## Export"), "utf-8")
    view = env.view()
    assert view.ladder is None and "Zeile 1" in view.error
    assert not env.execute(SetIdeas(0, ("x",))).applied


# -- Termine und Speicherorte ------------------------------------------------------------


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


def test_load_shows_unit_contents_labels_rungs_and_locks_markers(tmp_path):
    env = make_ladder_env(
        tmp_path, "UAL", u0={"ziel": "Brüche deuten", "teilziele": ("Teil",), "kompetenzen": ("Darstellen",)}
    )
    unit = env.units[0]
    unit.write_text(unit.read_text(encoding="utf-8") + "\n## Ideen\n\nPizza\n", encoding="utf-8")
    view = env.view()
    assert [(r.date_label, r.kind) for r in view.rungs] == [
        ("Mo 02.11.", RungKind.UNTERRICHT),
        ("Di 03.11.", RungKind.AUSFALL),
        ("Mi 04.11.", RungKind.LZK),
        ("??", RungKind.OFFEN),
    ]
    rung = view.ladder.rung(0)
    assert [b.text for b in rung.inhalt] == ["Brüche deuten", "Teil"]
    assert [b.text for b in rung.prozess] == ["Darstellen"] and rung.ideen == ("Pizza",)
    assert view.ladder.locked_rungs == frozenset({1, 2}) and view.error is None


def test_left_blocks_become_stundenziel_then_teilziele_and_body_stays(tmp_path):
    env = make_ladder_env(tmp_path, "UU")
    unit, other = env.units
    body_before = unit.read_text(encoding="utf-8").split("\n---", 1)[1]
    other_before = other.read_text(encoding="utf-8")
    sequence_before = env.sequence_path.read_text(encoding="utf-8")
    assert env.execute(AddBlock(LadderSlot(0, INH, 0), "Ziel")).written == (unit,)
    env.execute(AddBlock(LadderSlot(0, INH, 1), "Teil"))
    env.execute(AddBlock(LadderSlot(0, PRO, 0), "Modellieren"))
    data = _yaml(unit)
    assert (data["Stundenziel"], data["Teilziele"], data["Kompetenzen"]) == ("Ziel", ["Teil"], ["Modellieren"])
    assert unit.read_text(encoding="utf-8").split("\n---", 1)[1].endswith(body_before.split("\n", 1)[1])
    assert other.read_text(encoding="utf-8") == other_before  # unbeteiligte Einheit nie geschrieben
    assert env.sequence_path.read_text(encoding="utf-8") == sequence_before


def test_position_rule_promotes_the_next_block(tmp_path):
    env = make_ladder_env(tmp_path, "U", u0={"ziel": "Z", "teilziele": ("T1", "T2")})
    env.execute(RemoveBlock(BlockRef(0, INH, "Z")))
    assert (_yaml(env.units[0])["Stundenziel"], _yaml(env.units[0])["Teilziele"]) == ("T1", ["T2"])
    env.execute(MoveBlock(BlockRef(0, INH, "T2"), LadderSlot(0, INH, 0)))
    assert (_yaml(env.units[0])["Stundenziel"], _yaml(env.units[0])["Teilziele"]) == ("T2", ["T1"])


def test_ideas_live_under_ideen_heading_in_the_unit_body(tmp_path):
    env = make_ladder_env(tmp_path, "U")
    unit = env.units[0]
    before = unit.read_text(encoding="utf-8")
    env.execute(SetIdeas(0, ("Plakat", "Pizza")))
    text = unit.read_text(encoding="utf-8")
    assert text.startswith(before.rstrip("\n")) and text.endswith("## Ideen\n\nPlakat\nPizza\n")
    env.execute(SetIdeas(0, ()))
    assert "## Ideen" not in unit.read_text(encoding="utf-8")


def test_ebw_unit_keeps_its_blattwerk_marker_for_goals_and_ideas(tmp_path):
    env = make_ladder_env(tmp_path, "E")
    unit = env.units[0]
    env.execute(AddBlock(LadderSlot(0, INH, 0), "Ziel"))
    env.execute(SetIdeas(0, ("Idee",)))
    text = unit.read_text(encoding="utf-8")
    assert unit.suffix == ".ebw" and EBW_MARKER in text and "## Ideen" in text
    assert _yaml(unit)["Stundenziel"] == "Ziel"


def test_one_undo_restores_every_file_of_a_cross_unit_move(tmp_path):
    env = make_ladder_env(tmp_path, "UU", u0={"ziel": "Z", "teilziele": ("T",)})
    before = _texts(env.units)
    result = env.execute(MoveBlock(BlockRef(0, INH, "T"), LadderSlot(1, INH, 0)))
    assert result.applied and set(result.written) == set(env.units)
    assert _yaml(env.units[1])["Stundenziel"] == "T" and _yaml(env.units[0])["Teilziele"] == []
    assert len(env.history.undo_stack) == 1
    env.history.undo()
    assert _texts(env.units) == before


def test_failed_write_rolls_every_file_back_and_creates_no_entry(tmp_path, monkeypatch):
    env = make_ladder_env(tmp_path, "UU", u0={"ziel": "Z", "teilziele": ("T",)})
    before = _texts(env.units)
    original = LessonEditUseCase.set_lesson_fields
    calls = []

    def flaky(self, *args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise OSError("Platte voll")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(LessonEditUseCase, "set_lesson_fields", flaky)
    result = env.execute(MoveBlock(BlockRef(0, INH, "T"), LadderSlot(1, INH, 0)))
    assert not result.applied and "Platte voll" in result.error
    assert _texts(env.units) == before and env.history.undo_stack == []


def test_locked_rungs_take_nothing_and_steps_skip_them(tmp_path):
    env = make_ladder_env(tmp_path, "ULU", u0={"ziel": "Z"})
    lzk = env.days[1].link
    lzk_before = lzk.read_text(encoding="utf-8")
    result = env.execute(AddBlock(LadderSlot(1, INH, 0), "X"))
    assert not result.applied and "Sprosse 2" in result.error
    assert env.execute(StepBlock(BlockRef(0, INH, "Z"), up=True)).applied
    assert _yaml(env.units[1])["Stundenziel"] == "Z" and lzk.read_text(encoding="utf-8") == lzk_before


def test_import_lands_on_the_first_open_rung_above_the_highest_occupied(tmp_path):
    env = make_ladder_env(tmp_path, "ULU", u0={"kompetenzen": ("Alt",)})
    snapshot = build_kompetenz_graph_snapshot(
        [
            make_node("Mat-PL-1", primarer_bereich_id="P-Lösen", title="Probleme lösen"),
            make_node("Mat-X-1", primarer_bereich_id="?"),
        ],
        [make_bereich("P-Lösen", kind="prozessbereich")],
    )
    result = env.edit.import_competences(
        sequence_path=env.sequence_path,
        runs=env.runs,
        day_columns=env.days,
        snapshot=snapshot,
        kompetenz_ids=["Mat-PL-1", "Mat-X-1"],
    )
    assert result.applied and len(result.notes) == 1
    assert _yaml(env.units[1])["Kompetenzen"] == ["[[Mat-PL-1|Probleme lösen]]"]
    assert [e.label for e in env.history.undo_stack] == ["Kompetenzen übernehmen"]


def test_mixed_competences_go_to_the_chosen_column_and_semicolon_titles_stay_loadable(tmp_path):
    """Inhalt+Prozess → gewählte Spalte; Titel mit ';' (Mat-GF-28) als Teilziel bleibt ladbar."""
    env = make_ladder_env(tmp_path, "UU", u0={"ziel": "Z"})
    bereiche = [make_bereich("I-Funktionen", kind="inhaltsbereich"), make_bereich("P-Lösen", kind="prozessbereich")]
    nodes = [
        make_node(f"Mat-GF-{n}", primarer_bereich_id="I-Funktionen", prozessbereich_ids=("P-Lösen",), title=title)
        for n, title in ((28, "f(x)=x^n; n∈ℤ\\{0}"), (29, "Globalverhalten"))
    ]
    result = env.edit.import_competences(
        sequence_path=env.sequence_path,
        runs=env.runs,
        day_columns=env.days,
        snapshot=build_kompetenz_graph_snapshot(nodes, bereiche),
        kompetenz_ids=["Mat-GF-28", "Mat-GF-29"],
        mixed_side=INH,
    )
    assert result.applied
    assert _yaml(env.units[1])["Stundenziel"] == "[[Mat-GF-28|f(x)=x^n; n∈ℤ\\{0}]]"
    assert _yaml(env.units[1])["Teilziele"] == ["[[Mat-GF-29|Globalverhalten]]"]
    assert [b.kompetenz_id for b in env.view().ladder.rung(1).inhalt] == ["Mat-GF-28", "Mat-GF-29"]


def test_grid_edits_of_a_unit_show_up_on_the_next_load(tmp_path):
    env = make_ladder_env(tmp_path, "U")
    LessonEditUseCase(FileSystemLessonRepository()).set_lesson_field(
        env.units[0], "Kompetenzen", "", list_entries=["Argumentieren"]
    )
    assert [b.text for b in env.view().ladder.rung(0).prozess] == ["Argumentieren"]


def test_untouched_parts_of_a_unit_stay_as_stored(tmp_path):
    env = make_ladder_env(tmp_path, "U", u0={"teilziele": ("Nur Teilziel",)})
    env.execute(AddBlock(LadderSlot(0, PRO, 0), "Modellieren"))
    data = _yaml(env.units[0])
    assert (data["Stundenziel"], data["Teilziele"]) == ("", ["Nur Teilziel"])


# -- Altbestand-Doppelungen ----------------------------------------------------------------


def test_legacy_duplicates_are_marked_stay_editable_and_new_ones_are_refused(tmp_path):
    env = make_ladder_env(tmp_path, "UU", u0={"ziel": "Gleich"}, u1={"ziel": "Gleich"})
    view = env.view()
    assert view.duplicates == ((BlockRef(0, INH, "Gleich"), BlockRef(1, INH, "Gleich")),)
    assert env.execute(StepBlock(BlockRef(0, INH, "Gleich"), up=True)).applied  # verschiebbar
    assert not env.execute(AddBlock(LadderSlot(0, INH, 0), "gleich")).applied
    assert env.execute(RenameBlock(BlockRef(1, INH, "Gleich"), "Anders")).applied
    assert env.view().duplicates == ()


@pytest.mark.parametrize("entry", ["[[Notiz]]", "Tafelbild [[Skizze]]"])
def test_non_network_link_entries_survive_unchanged(tmp_path, entry):
    env = make_ladder_env(tmp_path, "U", u0={"teilziele": (entry,)})
    env.execute(AddBlock(LadderSlot(0, INH, 0), "Neu"))
    assert _yaml(env.units[0])["Teilziele"] == [entry]
