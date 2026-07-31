from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.infrastructure.repositories.sequence_plan_repository import FileSystemSequencePlanRepository


def _build_table(plan_path: Path) -> PlanTableData:
    return PlanTableData(
        markdown_path=plan_path,
        headers=["Datum", "Stunden", "Inhalt"],
        rows=[["10-03-26", "2", "[[Einheit 1]]"]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=True,
        metadata={"Lerngruppe": "[[GK blau-1]]"},
    )


def test_sequence_document_brainstorming_and_table_update(tmp_path):
    plan_dir = tmp_path / "Unterricht" / "M GK blau-1 26-2"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / "M GK blau-1 26-2.md"
    plan_path.write_text("# Kursplan\n", encoding="utf-8")

    table = _build_table(plan_path)
    repo = FileSystemSequencePlanRepository()

    sequence_path = repo.ensure_sequence_document(table=table, sequence_name="Lineare Funktionen")

    assert sequence_path.exists()
    assert sequence_path.parent.name == "Sequenzen"

    text = sequence_path.read_text(encoding="utf-8")
    assert 'Kursplan: "[[M GK blau-1 26-2]]"' in text
    assert "## Brainstorming" in text
    assert "## Export" in text

    repo.write_brainstorming(
        sequence_path=sequence_path,
        brainstorming_text="Idee A\nIdee B",
    )
    assert repo.read_brainstorming(sequence_path) == "Idee A\nIdee B"

    table_lines = repo.render_markdown_table(
        headers=["Datum", "Thema"],
        rows=[["10-03-26", "Lineare Funktionen"]],
    )
    repo.replace_trailing_table(sequence_path=sequence_path, table_lines=table_lines)

    updated = sequence_path.read_text(encoding="utf-8")
    assert "| Datum | Thema |" in updated
    assert "| 10-03-26 | Lineare Funktionen |" in updated

    replacement_table = repo.render_markdown_table(
        headers=["Datum", "Thema"],
        rows=[["17-03-26", "Quadratische Funktionen"]],
    )
    repo.replace_trailing_table(sequence_path=sequence_path, table_lines=replacement_table)

    replaced = sequence_path.read_text(encoding="utf-8")
    assert replaced.count("| Datum | Thema |") == 1
    assert "| 17-03-26 | Quadratische Funktionen |" in replaced
    assert "| 10-03-26 | Lineare Funktionen |" not in replaced

    repo.write_brainstorming(
        sequence_path=sequence_path,
        brainstorming_text="Neu priorisieren",
    )
    final_text = sequence_path.read_text(encoding="utf-8")
    assert "Neu priorisieren" in final_text
    assert "| 17-03-26 | Quadratische Funktionen |" in final_text


def test_new_sequence_document_has_empty_goal_and_focus_competency(tmp_path):
    plan_dir = tmp_path / "Unterricht" / "M GK blau-1 26-2"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / "M GK blau-1 26-2.md"
    plan_path.write_text("# Kursplan\n", encoding="utf-8")

    table = _build_table(plan_path)
    repo = FileSystemSequencePlanRepository()
    sequence_path = repo.ensure_sequence_document(table=table, sequence_name="Lineare Funktionen")

    sequenzziel, leitkompetenz = repo.read_goal_and_focus_competency(sequence_path)
    assert sequenzziel == ""
    assert leitkompetenz == ""


def test_write_goal_and_focus_competency_round_trips_and_preserves_rest_of_file(tmp_path):
    plan_dir = tmp_path / "Unterricht" / "M GK blau-1 26-2"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / "M GK blau-1 26-2.md"
    plan_path.write_text("# Kursplan\n", encoding="utf-8")

    table = _build_table(plan_path)
    repo = FileSystemSequencePlanRepository()
    sequence_path = repo.ensure_sequence_document(table=table, sequence_name="Lineare Funktionen")

    repo.write_brainstorming(sequence_path=sequence_path, brainstorming_text="Idee A")
    table_lines = repo.render_markdown_table(headers=["Datum"], rows=[["10-03-26"]])
    repo.replace_trailing_table(sequence_path=sequence_path, table_lines=table_lines)

    repo.write_goal_and_focus_competency(
        sequence_path=sequence_path,
        sequenzziel="Steigungen sicher berechnen",
        leitkompetenz="Modellieren",
    )

    sequenzziel, leitkompetenz = repo.read_goal_and_focus_competency(sequence_path)
    assert sequenzziel == "Steigungen sicher berechnen"
    assert leitkompetenz == "Modellieren"

    text = sequence_path.read_text(encoding="utf-8")
    assert 'Kursplan: "[[M GK blau-1 26-2]]"' in text
    assert "Idee A" in text
    assert "| 10-03-26 |" in text

    repo.write_goal_and_focus_competency(
        sequence_path=sequence_path,
        sequenzziel="Geänderter Text",
        leitkompetenz="Modellieren",
    )
    updated_sequenzziel, _ = repo.read_goal_and_focus_competency(sequence_path)
    assert updated_sequenzziel == "Geänderter Text"
    assert sequence_path.read_text(encoding="utf-8").count("Sequenzziel:") == 1
