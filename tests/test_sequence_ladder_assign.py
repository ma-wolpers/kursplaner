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
from kursplaner.core.domain.sequence_ladder_assign import merge_rung_into_unit, overwrite_warnings
from kursplaner.core.domain.sequence_ladder_homes import (
    MarkerHome,
    RungKind,
    UnitContent,
    UnitHome,
    locked_reason,
    term_home,
)
from kursplaner.core.domain.sequence_ladder_ops import AddBlock, SetIdeas
from kursplaner.core.usecases.assign_ablage_rung_usecase import AssignAblageRungUseCase
from kursplaner.core.usecases.lesson_edit_usecase import LessonEditUseCase
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


@pytest.fixture
def assign_env(tmp_path):
    """Sequenz „U L“ (Unterricht, LZK) + 7 freie Zeilen; Ablage-Sprosse 2 mit Ziel, Kompetenz und Idee."""

    def factory(kinds="UL", **units):
        env = make_ladder_env(tmp_path, kinds, **units)
        plan_path = env.units[0].parent.parent / f"{env.units[0].parent.parent.name}.md"
        free = [
            make_day_column(row_index=i, datum=f"{i + 2:02d}-11-26") for i in range(len(env.days), len(env.days) + 7)
        ]
        days = list(env.days) + free
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
            tracked_write=TrackedWriteUseCase(env.history),
        )

        def run(step: str, target_row: int, rung: int = ablage):
            call = usecase.check if step == "check" else usecase.execute
            extra = {} if step == "check" else {"table": table}
            return call(sequence_path=env.sequence_path, oberthema="Brüche", runs=env.runs, day_columns=days,
                        rung=rung, target_row=target_row, **extra)  # fmt: skip

        return env, table, days, usecase, run

    return factory


def _ablage_text(env) -> str:
    return env.sequence_path.read_text(encoding="utf-8")


def test_targets_offer_the_suggestion_first_then_terms_then_following_rows(assign_env):
    env, _table, days, usecase, _run = assign_env()
    targets = usecase.targets(runs=env.runs, day_columns=days)
    assert targets.suggested_row == 2
    assert [d.row_index for d in targets.days] == [2, 0, 1, 3, 4, 5, 6, 7]


def test_blocked_targets_and_wrong_rungs_write_nothing(assign_env):
    env, _table, _days, _usecase, run = assign_env()
    before = _ablage_text(env)
    assert "LZK" in run("check", 1).error
    assert "Nur Sprossen ohne Termin" in run("check", 2, rung=0).error
    assert "leer" in run("check", 2, rung=5).error
    assert run("execute", 1).applied is False and _ablage_text(env) == before


def test_existing_unit_warns_then_takes_goals_and_appends_ideas_in_one_undo_step(assign_env):
    env, _table, _days, _usecase, run = assign_env(u0={"ziel": "Altes Ziel"})
    check = run("check", 0)
    assert check.creates_file is False and "Altes Ziel" in check.warnings[0]
    undo_before = len(env.history.undo_stack)

    result = run("execute", 0)

    assert result.applied and env.units[0] in result.written
    data = load_linked_lesson_yaml(env.units[0]).data
    assert (data["Stundenziel"], data["Kompetenzen"], data["Oberthema"]) == ("Neues Ziel", ["Modellieren"], "Brüche")
    assert "Kartenabfrage" in env.units[0].read_text(encoding="utf-8")
    assert "Neues Ziel" not in _ablage_text(env)
    assert len(env.history.undo_stack) == undo_before + 1
    env.history.undo()
    assert load_linked_lesson_yaml(env.units[0]).data["Stundenziel"] == "Altes Ziel"
    assert "Neues Ziel" in _ablage_text(env)


def test_empty_row_gets_a_new_unit_which_undo_removes_again(assign_env):
    env, table, _days, _usecase, run = assign_env()
    assert run("check", 3).creates_file is True

    result = run("execute", 3)

    assert result.applied
    created = next(p for p in result.written if p.parent.name == "Einheiten")
    assert is_random_lesson_stem(created.stem) and created.exists()
    assert created.stem in table.rows[3][1] and table.markdown_path in result.written
    data = load_linked_lesson_yaml(created).data
    assert (data["Stundenziel"], data["Oberthema"], data["Stundenthema"]) == ("Neues Ziel", "Brüche", "")
    env.history.undo()
    assert not created.exists()


def test_failure_after_creating_leaves_no_file_and_restores_the_row(assign_env, monkeypatch):
    env, table, _days, usecase, run = assign_env()
    row_before = list(table.rows[3])
    einheiten = env.units[0].parent
    files_before = set(einheiten.iterdir())

    def boom(*_args, **_kwargs):
        raise RuntimeError("Platte voll")

    monkeypatch.setattr(usecase._lesson_edit, "set_lesson_oberthemen", boom)
    result = run("execute", 3)

    assert not result.applied and "Platte voll" in result.error
    assert set(einheiten.iterdir()) == files_before
    assert table.rows[3] == row_before


def test_rung_with_only_competences_keeps_the_units_goals(assign_env):
    env, _table, _days, _usecase, run = assign_env(u0={"ziel": "Bleibt"})
    env.execute(AddBlock(LadderSlot(len(env.days) + 1, PRO, 0), "Argumentieren"))
    result = run("execute", 0, rung=len(env.days) + 1)
    assert result.applied
    data = load_linked_lesson_yaml(env.units[0]).data
    assert (data["Stundenziel"], data["Kompetenzen"]) == ("Bleibt", ["Argumentieren"])
