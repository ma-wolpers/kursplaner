from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.update_sequence_goal_field_usecase import UpdateSequenceGoalFieldUseCase
from kursplaner.infrastructure.repositories.sequence_plan_repository import FileSystemSequencePlanRepository


def _table(tmp_path: Path) -> PlanTableData:
    plan_dir = tmp_path / "Unterricht" / "M GK blau-1 26-2"
    plan_dir.mkdir(parents=True, exist_ok=True)
    return PlanTableData(
        markdown_path=plan_dir / "M GK blau-1 26-2.md",
        headers=["Datum", "Stunden", "Inhalt"],
        rows=[],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=True,
        metadata={"Lerngruppe": "[[GK blau-1]]"},
    )


def test_writing_sequenzziel_does_not_clobber_existing_leitkompetenz(tmp_path):
    repo = FileSystemSequencePlanRepository()
    usecase = UpdateSequenceGoalFieldUseCase(sequence_plan_repo=repo)
    table = _table(tmp_path)

    usecase.execute(table=table, oberthema="Vektoren", field_key="Leitkompetenz", value="Modellieren")
    result = usecase.execute(table=table, oberthema="Vektoren", field_key="Sequenzziel", value="Vektoren verstehen")

    assert result.sequenzziel == "Vektoren verstehen"
    assert result.leitkompetenz == "Modellieren"

    sequenzziel, leitkompetenz = repo.read_goal_and_focus_competency(result.sequence_path)
    assert sequenzziel == "Vektoren verstehen"
    assert leitkompetenz == "Modellieren"


def test_writing_leitkompetenz_does_not_clobber_existing_sequenzziel(tmp_path):
    repo = FileSystemSequencePlanRepository()
    usecase = UpdateSequenceGoalFieldUseCase(sequence_plan_repo=repo)
    table = _table(tmp_path)

    usecase.execute(table=table, oberthema="Stochastik", field_key="Sequenzziel", value="Wahrscheinlichkeiten deuten")
    result = usecase.execute(table=table, oberthema="Stochastik", field_key="Leitkompetenz", value="Bewerten")

    assert result.sequenzziel == "Wahrscheinlichkeiten deuten"
    assert result.leitkompetenz == "Bewerten"
