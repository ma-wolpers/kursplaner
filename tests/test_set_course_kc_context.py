"""Werkzeug `set_course_kc_context`: aktive und archivierte Kurse, nur fehlende Felder (synthetisch)."""

from __future__ import annotations

from kursplaner.core.domain.course_kc_context import CourseKcContext
from kursplaner.core.domain.course_lifecycle import course_archive_root
from tools.set_course_kc_context import run

IGS_NDS = CourseKcContext("Niedersachsen", "IGS")


def _course(root, name, extra=""):
    folder = root / name
    folder.mkdir(parents=True)
    plan = folder / f"{name}.md"
    plan.write_text(
        f'---\nLerngruppe: "[[gruppe-1]]"\nKursfach: "Mathematik"\nStufe: 8\n{extra}Rhythmus:\n  - "Mo 08:00 2"\n---\n',
        encoding="utf-8",
    )
    return plan


def test_fills_missing_fields_in_active_and_archived_courses(tmp_path):
    active = _course(tmp_path, "M gruppe-1 26-1")
    archived = _course(course_archive_root(tmp_path), "M gruppe-2 25-2", extra='Schulform: "Gymnasium"\n')

    dry = run(tmp_path, IGS_NDS, include_archive=True, dry_run=True)
    assert (dry.changed, dry.unchanged, dry.errors) == (2, 0, [])
    assert "Bundesland" not in active.read_text(encoding="utf-8")

    result = run(tmp_path, IGS_NDS, include_archive=True)
    assert (result.changed, result.errors) == (2, [])
    assert 'Bundesland: "Niedersachsen"\nSchulform: "IGS"' in active.read_text(encoding="utf-8")
    archived_text = archived.read_text(encoding="utf-8")
    assert 'Schulform: "Gymnasium"' in archived_text and 'Bundesland: "Niedersachsen"' in archived_text

    again = run(tmp_path, IGS_NDS, include_archive=True)
    assert (again.changed, again.unchanged) == (0, 2)


def test_overwrite_replaces_existing_values_and_archive_can_be_skipped(tmp_path):
    archived = _course(course_archive_root(tmp_path), "M gruppe-2 25-2", extra='Schulform: "Gymnasium"\n')
    assert run(tmp_path, IGS_NDS, include_archive=False, overwrite=True).changed == 0
    assert run(tmp_path, IGS_NDS, include_archive=True, overwrite=True).changed == 1
    assert 'Schulform: "IGS"' in archived.read_text(encoding="utf-8")


def test_broken_plan_files_are_reported_not_fatal(tmp_path):
    folder = tmp_path / "kaputt"
    folder.mkdir()
    (folder / "kaputt.md").write_text("kein Frontmatter\n", encoding="utf-8")
    result = run(tmp_path, IGS_NDS, include_archive=False)
    assert result.changed == 0 and len(result.errors) == 1
