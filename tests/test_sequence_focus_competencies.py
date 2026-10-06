"""Hard Cut ``Leitkompetenzen``: Liste im Datenmodell, kein Laufzeitpfad für den alten Key."""

from pathlib import Path

import pytest

from kursplaner.core.domain.list_cell_text import ListFieldViolationError
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.topic_sequence_runs import TopicSequenceRun
from kursplaner.core.usecases.sync_topic_sequence_plans_usecase import TopicSequencePlanView
from kursplaner.core.usecases.update_sequence_goal_field_usecase import UpdateSequenceGoalFieldUseCase
from kursplaner.infrastructure.repositories.sequence_plan_repository import FileSystemSequencePlanRepository


def _table(tmp_path: Path) -> PlanTableData:
    plan_dir = tmp_path / "Unterricht" / "M GK blau-1 26-2"
    plan_dir.mkdir(parents=True, exist_ok=True)
    return PlanTableData(
        markdown_path=plan_dir / "M GK blau-1 26-2.md",
        headers=["Datum", "Inhalt"],
        rows=[],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=True,
        metadata={"Lerngruppe": "[[GK blau-1]]"},
    )


def _sequence_file(tmp_path: Path, focus_block: str) -> Path:
    path = tmp_path / "s.md"
    path.write_text(
        f'---\nKursplan: "[[k]]"\nSequenzname: "S"\nLerngruppe: "g"\nHalbjahr: "26-2"\nSequenzziel: ""\n{focus_block}---\n',
        encoding="utf-8",
    )
    return path


def test_old_singular_key_is_not_supported_at_runtime(tmp_path):
    """Nicht migrierter Altbestand scheitert an der regulären Schema-Prüfung (Pflichtfeld)."""
    path = _sequence_file(tmp_path, 'Leitkompetenz: "Modellieren"\n')

    with pytest.raises(RuntimeError) as info:
        FileSystemSequencePlanRepository().read_goal_and_focus_competencies(path)

    assert "Leitkompetenzen" in str(info.value)


def test_scalar_focus_competencies_is_invalid_not_reinterpreted(tmp_path):
    path = _sequence_file(tmp_path, 'Leitkompetenzen: "Modellieren"\n')

    with pytest.raises(ListFieldViolationError):
        FileSystemSequencePlanRepository().read_goal_and_focus_competencies(path)


@pytest.mark.parametrize("bad", ['  - "A; B"\n', '  - " A"\n', '  - ""\n'])
def test_invalid_entry_is_rejected_with_explanation(tmp_path, bad):
    path = _sequence_file(tmp_path, f'Leitkompetenzen:\n  - "ok"\n{bad}')

    with pytest.raises(ListFieldViolationError) as info:
        FileSystemSequencePlanRepository().read_goal_and_focus_competencies(path)

    assert info.value.field == "Leitkompetenzen"
    assert str(path.resolve()) in str(info.value)


def test_write_rejects_invalid_entries_before_touching_the_file(tmp_path):
    path = _sequence_file(tmp_path, "Leitkompetenzen:\n")
    before = path.read_bytes()

    with pytest.raises(ListFieldViolationError):
        FileSystemSequencePlanRepository().write_goal_and_focus_competencies(
            sequence_path=path, sequenzziel="Z", leitkompetenzen=("A; B",)
        )

    assert path.read_bytes() == before


def test_update_use_case_parses_list_cell_text(tmp_path):
    repo = FileSystemSequencePlanRepository()
    usecase = UpdateSequenceGoalFieldUseCase(repo)

    result = usecase.execute(
        table=_table(tmp_path),
        oberthema="Vektoren",
        field_key="Leitkompetenzen",
        value="Modellieren; Argumentieren\n--\n[[K/Kommunizieren|Kommunizieren]]",
    )

    expected = ("Modellieren", "Argumentieren", "[[K/Kommunizieren|Kommunizieren]]")
    assert result.leitkompetenzen == expected
    assert repo.read_goal_and_focus_competencies(result.sequence_path)[1] == expected


def test_replacing_generated_table_leaves_frontmatter_and_brainstorming_untouched(tmp_path):
    repo = FileSystemSequencePlanRepository()
    path = repo.ensure_sequence_document(table=_table(tmp_path), sequence_name="Vektoren")
    repo.write_goal_and_focus_competencies(sequence_path=path, sequenzziel="Ziel", leitkompetenzen=("A", "B"))
    repo.write_brainstorming(sequence_path=path, brainstorming_text="Idee")
    repo.replace_trailing_table(
        sequence_path=path, table_lines=repo.render_markdown_table(headers=["X"], rows=[["alt1"], ["alt2"]])
    )
    frontmatter_before = path.read_text(encoding="utf-8").split("---")[1]

    repo.replace_trailing_table(
        sequence_path=path, table_lines=repo.render_markdown_table(headers=["X"], rows=[["neu"]])
    )

    text = path.read_text(encoding="utf-8")
    assert text.split("---")[1] == frontmatter_before
    assert "Idee" in text
    assert "neu" in text and "alt1" not in text and "alt2" not in text
    assert repo.read_goal_and_focus_competencies(path) == ("Ziel", ("A", "B"))


def test_plan_view_field_text_formats_both_fields():
    run = TopicSequenceRun(oberthema="V", member_row_indices=(0, 1))
    view = TopicSequencePlanView(run=run, sequence_path=Path("x.md"), sequenzziel="Ziel", leitkompetenzen=("A", "B"))

    assert view.field_text("Sequenzziel") == "Ziel"
    assert view.field_text("Leitkompetenzen") == "A\n--\nB"
    assert view.is_incomplete is False
    assert TopicSequencePlanView(run=run, sequence_path=Path("x.md"), sequenzziel="Z", leitkompetenzen=()).is_incomplete
