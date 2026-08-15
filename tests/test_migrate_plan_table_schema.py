from pathlib import Path

from tools.migrate_plan_table_schema import migrate_plan

FRONTMATTER = """---
Lerngruppe: "[[Test]]"
Kursfach: Mathematik
Stufe: 11
---
"""


def _write_plan(tmp_path: Path, table_rows: str) -> Path:
    course_dir = tmp_path / "Testkurs"
    course_dir.mkdir()
    plan_path = course_dir / "Testkurs.md"
    body = (
        FRONTMATTER
        + "\n| Datum | Stunden | Inhalt | Thema/Ausfall |\n"
        + "| --- | --- | --- | --- |\n"
        + table_rows
    )
    plan_path.write_text(body, encoding="utf-8")
    return plan_path


def test_migrate_plan_derives_consistent_rhythm(tmp_path):
    # 02-03-26 und 09-03-26 liegen genau eine Woche auseinander -> gleicher Wochentag.
    rows = "| 02-03-26 | 2 |  |  |\n| 09-03-26 | 2 |  |  |\n"
    plan_path = _write_plan(tmp_path, rows)

    status = migrate_plan(plan_path, dry_run=False)

    assert status.startswith("OK:")
    migrated_text = plan_path.read_text(encoding="utf-8")
    assert "Rhythmus:" in migrated_text
    assert "| Datum | Inhalt | Thema/Ausfall |" in migrated_text
    assert "| Datum | Stunden | Inhalt | Thema/Ausfall |" not in migrated_text


def test_migrate_plan_rejects_conflicting_hours_for_same_weekday(tmp_path):
    # Gleicher Wochentag (eine Woche Abstand), aber unterschiedliche Stundenzahl -> nicht eindeutig migrierbar.
    rows = "| 02-03-26 | 2 |  |  |\n| 09-03-26 | 1 |  |  |\n"
    plan_path = _write_plan(tmp_path, rows)
    original_text = plan_path.read_text(encoding="utf-8")

    status = migrate_plan(plan_path, dry_run=False)

    assert status.startswith("ERROR:")
    assert "Widersprüchliche historische Stundenwerte" in status
    # Datei bleibt bei einem Fehler unangetastet.
    assert plan_path.read_text(encoding="utf-8") == original_text


def test_migrate_plan_is_idempotent(tmp_path):
    rows = "| 02-03-26 | 2 |  |  |\n"
    plan_path = _write_plan(tmp_path, rows)

    first = migrate_plan(plan_path, dry_run=False)
    second = migrate_plan(plan_path, dry_run=False)

    assert first.startswith("OK:")
    assert second == "SKIP (bereits migriert)"


def test_migrate_plan_dry_run_does_not_write(tmp_path):
    rows = "| 02-03-26 | 2 |  |  |\n"
    plan_path = _write_plan(tmp_path, rows)
    original_text = plan_path.read_text(encoding="utf-8")

    status = migrate_plan(plan_path, dry_run=True)

    assert status.startswith("OK:")
    assert plan_path.read_text(encoding="utf-8") == original_text
