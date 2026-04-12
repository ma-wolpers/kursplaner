from __future__ import annotations

from datetime import date

from kursplaner.infrastructure.repositories.plan_repository import FileSystemPlanRepository
from kursplaner.infrastructure.repositories.plan_table_file_repository import load_last_plan_table


def test_append_plan_rows_extends_existing_last_table(tmp_path):
    plan_file = tmp_path / "M GK blau-1 26-1.md"
    plan_file.write_text(
        "---\n"
        'Lerngruppe: "[[GK blau-1]]"\n'
        'Kursfach: "Mathematik"\n'
        "Stufe: 11\n"
        "---\n\n"
        "| Datum | Stunden | Inhalt |\n"
        "| --- | --- | --- |\n"
        "| 10-03-26 | 2 | [[GK blau-1 0310 Einheit]] |\n",
        encoding="utf-8",
    )

    repo = FileSystemPlanRepository()
    repo.append_plan_rows(plan_file, [(date(2026, 3, 12), 2, "")])

    text = plan_file.read_text(encoding="utf-8")
    assert text.count("| Datum | Stunden | Inhalt |") == 1
    assert "| 12-03-26 | 2 |  |" in text

    table = load_last_plan_table(plan_file)
    assert len(table.rows) == 2
    assert table.rows[-1][0] == "12-03-26"
    assert table.rows[-1][1] == "2"
