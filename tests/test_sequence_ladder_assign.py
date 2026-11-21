"""Ablage-Sprosse einer Plan-Zeile zuordnen: Regeln (Domain) und Use Case mit echten Dateien in ``tmp_path``."""

from __future__ import annotations

import pytest
from day_column_factory import make_day_column
from sequence_ladder_test_support import make_ladder_env

from kursplaner.core.domain.lesson_naming import is_random_lesson_stem
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.sequence_ladder import (
    LadderBlock,
    LadderRung,
    LadderSide,
    LadderSlot,
    SequenceLadder,
    locked_message,
)
from kursplaner.core.domain.sequence_ladder_assign import TargetKind, merge_rung_into_unit, overwrite_warnings
from kursplaner.core.domain.sequence_ladder_homes import (
    MarkerHome,
    RungKind,
    UnitContent,
    UnitHome,
    locked_reason,
    term_home,
)
from kursplaner.core.domain.sequence_ladder_ops import AddBlock, SetIdeas
from kursplaner.core.domain.topic_sequence_runs import compute_topic_sequence_runs, group_into_sequences
from kursplaner.core.usecases.assign_ablage_rung_usecase import MEMBER_ERROR, AssignAblageRungUseCase
from kursplaner.core.usecases.lesson_edit_usecase import LessonEditUseCase
from kursplaner.core.usecases.load_sequence_ladder_usecase import sequence_term_days
from kursplaner.core.usecases.plan_commands_usecase import PlanCommandsUseCase
from kursplaner.core.usecases.sequence_ladder_source import SequenceLadderSource
from kursplaner.core.usecases.tracked_write_usecase import TrackedWriteUseCase
from kursplaner.infrastructure.repositories.lesson_repository import FileSystemLessonRepository
from kursplaner.infrastructure.repositories.plan_table_file_repository import load_linked_lesson_yaml

INH, PRO = LadderSide.INHALT, LadderSide.PROZESS


def _rung(left=(), right=(), ideen=()) -> LadderRung:
    return LadderRung(tuple(LadderBlock(t) for t in left), tuple(LadderBlock(t) for t in right), tuple(ideen))


# -- Domain -----------------------------------------------------------------------


def test_merge_replaces_only_sides_the_rung_carries_and_appends_ideas():
    old = UnitContent("Altes Ziel", ("Alt T",), ("Alt K",), ("Alte Idee",))
    merged = merge_rung_into_unit(_rung(left=("Neu Z", "Neu T"), ideen=("Neue Idee",)), old)
    assert (merged.stundenziel, merged.teilziele) == ("Neu Z", ("Neu T",))
    assert merged.kompetenzen == ("Alt K",)
    assert merged.ideen == ("Alte Idee", "Neue Idee")


def test_warnings_name_only_what_is_actually_overwritten():
    old = UnitContent("Ziel", (), ("K",), ("I",))
    assert overwrite_warnings(_rung(right=("K2",)), old, "Brüche", "Brüche") == ("Kompetenzen werden ersetzt:\n  • K",)
    assert overwrite_warnings(_rung(left=("Z2",)), UnitContent(), "", "Brüche") == ()
    texts = "\n".join(overwrite_warnings(_rung(left=("Z2",), ideen=("x",)), old, "Prozente", "Brüche"))
    assert (
        "Stunden-/Teilziele werden ersetzt" in texts and "angehängt" in texts and "„Prozente“ wird zu „Brüche“" in texts
    )


def test_without_rung_moves_upper_rungs_down():
    ladder = SequenceLadder((_rung(("a",)), _rung(("b",)), _rung(("c",))), frozenset({2}))
    shorter = ladder.without_rung(1)
    assert [r.inhalt[0].text for r in shorter.rungs] == ["a", "c"] and shorter.locked_rungs == {1}


def test_term_home_and_locked_reason(tmp_path):
    unit = tmp_path / "u.md"
    assert term_home(make_day_column(link=unit, yaml={"Stundentyp": "Unterricht"})) == UnitHome(unit)
    assert term_home(make_day_column()) == MarkerHome(RungKind.UNTERRICHT)
    assert "Termin ohne eigene" in locked_message(3, locked_reason(RungKind.UNTERRICHT))
    assert "(LZK)" in locked_message(0, locked_reason(RungKind.LZK))


# -- Use Case ---------------------------------------------------------------------


class _Plans:
    """Fake-Planrepository: Speichern schreibt die Zeilen in die Plan-Datei (Undo kann sie erfassen)."""

    def save_plan_table(self, table: PlanTableData) -> None:
        table.markdown_path.write_text(repr(table.rows), encoding="utf-8")


_AFTER_KINDS = {"G": ("Unterricht", "Geometrie"), "K": ("LZK", "Geometrie"), "N": ("Unterricht", "")}


def _after_row(einheiten, index: int, kind: str):
    """Zeile nach der Sequenz: ``-`` frei, ``G`` Einheit „Geometrie“, ``K`` LZK „Geometrie“, ``N`` ohne Oberthema."""
    datum = f"{index + 2:02d}-11-26"
    if kind == "-":
        return make_day_column(row_index=index, datum=datum)
    typ, topic = _AFTER_KINDS[kind]
    path = einheiten / f"x{index}.md"
    path.write_text(f"---\nStundentyp: {typ}\nDauer: 2\nStundenthema: x{index}\nOberthema: {topic}\n---\n", "utf-8")
    thema = f"[[test-1 {topic}]]" if topic else ""
    return make_day_column(row_index=index, datum=datum, inhalt=f"[[x{index}]]", thema_ausfall=thema, link=path,
                           yaml={"Stundentyp": typ, "Oberthema": topic, "Stundenthema": f"x{index}"})  # fmt: skip


@pytest.fixture
def assign_env(tmp_path):
    """Sequenz *kinds* (Standard „U L“) + Zeilen *after* (Standard 7 freie); Ablage-Sprosse mit Ziel, Kompetenz, Idee."""

    def factory(kinds="UL", after="-------", **units):
        env = make_ladder_env(tmp_path, kinds, **units)
        einheiten = env.units[0].parent
        plan_path = einheiten.parent / f"{einheiten.parent.name}.md"
        days = list(env.days) + [_after_row(einheiten, len(env.days) + i, k) for i, k in enumerate(after)]
        table = PlanTableData(plan_path, ["Datum", "Inhalt", "Thema/Ausfall"],
                              [[d.datum, d.inhalt, d.thema_ausfall] for d in days], 0, 0, [], True, {})  # fmt: skip
        ablage = len(env.days)
        env.execute(AddBlock(LadderSlot(ablage, INH, 0), "Neues Ziel"))
        env.execute(AddBlock(LadderSlot(ablage, PRO, 0), "Modellieren"))
        env.execute(SetIdeas(ablage, ("Kartenabfrage",)))
        lessons = FileSystemLessonRepository()
        usecase = AssignAblageRungUseCase(
            source=SequenceLadderSource(sequence_plan_repo=env.sequence_repo, lesson_repo=lessons),
            sequence_plan_repo=env.sequence_repo,
            lesson_repo=lessons,
            lesson_edit=LessonEditUseCase(lesson_repo=lessons),
            plan_repo=_Plans(),
            plan_commands=PlanCommandsUseCase(lesson_repo=lessons),
            tracked_write=TrackedWriteUseCase(env.history),
        )

        def run(step: str, target_row: int, rung: int = ablage, merge: bool = False):
            call = usecase.check if step == "check" else usecase.execute
            return call(table=table, sequence_path=env.sequence_path, oberthema="Brüche", runs=env.runs,
                        day_columns=days, rung=rung, target_row=target_row, merge=merge)  # fmt: skip

        return env, table, days, usecase, run

    return factory


def _ablage_text(env) -> str:
    return env.sequence_path.read_text(encoding="utf-8")


def _created(result):
    return next(p for p in result.written if p.parent.name == "Einheiten")


def _after_unit(env, row: int):
    """Datei einer Zeile nach der Sequenz (`_after_row`)."""
    return env.units[0].parent / f"x{row}.md"


def test_targets_are_chronological_with_kinds_and_the_suggestion_after_the_last_term(assign_env):
    env, _table, days, usecase, _run = assign_env(after="KG-N---")
    targets = usecase.targets(runs=env.runs, day_columns=days)
    kinds = [(t.day.row_index, t.kind) for t in targets.targets]
    assert kinds == [
        (0, TargetKind.MEMBER), (1, TargetKind.MEMBER), (2, TargetKind.BLOCKED), (3, TargetKind.OCCUPIED),
        (4, TargetKind.FREE), (5, TargetKind.LOOSE_UNIT), (6, TargetKind.FREE), (7, TargetKind.FREE),
    ]  # fmt: skip
    assert targets.suggested_row == 3


def test_members_blocked_and_wrong_rungs_write_nothing(assign_env):
    env, _table, _days, _usecase, run = assign_env(after="K------")
    before = _ablage_text(env)
    assert run("check", 0).error == MEMBER_ERROR
    assert "LZK" in run("check", 2).error
    assert "Nur Sprossen ohne Termin" in run("check", 3, rung=0).error
    assert "leer" in run("check", 3, rung=5).error
    assert run("execute", 2).applied is False and _ablage_text(env) == before


def test_a_later_free_row_becomes_part_of_the_sequence(assign_env):
    """Regression: früher fiel eine nicht direkt anschließende Einheit aus der Leiter."""
    env, table, days, _usecase, run = assign_env(after="G-----")
    result = run("execute", 3)
    assert result.applied
    created = _created(result)
    assert created.stem in table.rows[3][1]
    data = load_linked_lesson_yaml(created).data
    assert (data["Stundenziel"], data["Oberthema"]) == ("Neues Ziel", "Brüche")

    after = list(days)
    after[3] = make_day_column(row_index=3, datum=days[3].datum, inhalt=table.rows[3][1], link=created, yaml=data)
    [sequence] = [s for s in group_into_sequences(compute_topic_sequence_runs(after)) if s.oberthema == "Brüche"]
    assert 3 in {day.row_index for day in sequence_term_days(after, list(sequence.runs))}


def test_insert_before_another_sequence_shifts_it_but_the_lzk_stays_and_undo_restores(assign_env):
    env, table, _days, _usecase, run = assign_env(after="GKG---")
    rows_before = [list(row) for row in table.rows]
    check = run("check", 2)
    assert (check.creates_file, check.shifted, check.error) == (True, 2, None)

    result = run("execute", 2)

    assert result.applied
    assert _created(result).stem in table.rows[2][1]
    assert table.rows[3][1:] == rows_before[3][1:]  # LZK bleibt stehen
    assert table.rows[4][1:] == rows_before[2][1:]  # erstes G springt über die LZK
    assert table.rows[5][1:] == rows_before[4][1:]  # zweites G rückt in den freien Termin
    env.history.undo()
    assert "Neues Ziel" in _ablage_text(env) and not _created(result).exists()


def test_loose_unit_can_take_the_rung_in_place(assign_env):
    env, table, _days, _usecase, run = assign_env(after="N------")
    rows_before = [list(row) for row in table.rows]
    assert run("check", 2).shifted == 1
    result = run("execute", 2, merge=True)
    assert result.applied and table.rows == rows_before
    data = load_linked_lesson_yaml(_after_unit(env, 2)).data
    assert (data["Stundenziel"], data["Oberthema"]) == ("Neues Ziel", "Brüche")


def test_existing_member_unit_is_never_overwritten_and_warnings_still_work(assign_env):
    env, _table, _days, _usecase, run = assign_env(u0={"ziel": "Altes Ziel"})
    assert run("check", 0).error == MEMBER_ERROR
    assert load_linked_lesson_yaml(env.units[0]).data["Stundenziel"] == "Altes Ziel"


def test_empty_row_gets_a_new_unit_which_undo_removes_again(assign_env):
    env, table, _days, _usecase, run = assign_env()
    assert run("check", 3).creates_file is True

    result = run("execute", 3)

    assert result.applied
    created = _created(result)
    assert is_random_lesson_stem(created.stem) and created.exists()
    assert created.stem in table.rows[3][1] and table.markdown_path in result.written
    data = load_linked_lesson_yaml(created).data
    assert (data["Stundenziel"], data["Oberthema"], data["Stundenthema"]) == ("Neues Ziel", "Brüche", "")
    env.history.undo()
    assert not created.exists()


def test_failure_after_shifting_leaves_no_file_and_restores_the_whole_table(assign_env, monkeypatch):
    env, table, _days, usecase, run = assign_env(after="GG----")
    rows_before = [list(row) for row in table.rows]
    einheiten = env.units[0].parent
    files_before = set(einheiten.iterdir())

    def boom(*_args, **_kwargs):
        raise RuntimeError("Platte voll")

    monkeypatch.setattr(usecase._lesson_edit, "set_lesson_oberthemen", boom)
    result = run("execute", 2)

    assert not result.applied and "Platte voll" in result.error
    assert set(einheiten.iterdir()) == files_before
    assert table.rows == rows_before


def test_merge_with_only_competences_keeps_the_units_goals(assign_env):
    env, _table, _days, _usecase, run = assign_env(after="N------")
    env.execute(AddBlock(LadderSlot(len(env.days) + 1, PRO, 0), "Argumentieren"))
    result = run("execute", 2, rung=len(env.days) + 1, merge=True)
    assert result.applied
    data = load_linked_lesson_yaml(_after_unit(env, 2)).data
    assert data["Kompetenzen"] == ["Argumentieren"]
