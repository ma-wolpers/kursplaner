"""Tests für das Upgrade-Prüftool `tools/check_list_field_entries.py` (synthetische Daten)."""

from pathlib import Path

import pytest

from kursplaner.core.domain.lesson_yaml_policy import canonicalize_lesson_yaml
from kursplaner.core.domain.list_cell_text import ListFieldViolationError
from kursplaner.core.domain.yaml_registry import LESSON_SCHEMA, parse_yaml_frontmatter
from tools.check_list_field_entries import check_lesson_file, main, scan


def _course(root: Path, name: str = "Mat 7a 26-1") -> Path:
    course = root / name
    (course / "Einheiten").mkdir(parents=True)
    (course / f"{name}.md").write_text("---\nx: y\n---\n", encoding="utf-8")
    return course


def _lesson(course: Path, stem: str, body: str) -> Path:
    path = course / "Einheiten" / f"{stem}.md"
    path.write_text(f"---\nStundentyp: Unterricht\nDauer: 2\nStundenthema: X\n{body}---\n", encoding="utf-8")
    return path


def _sequence(course: Path, stem: str, body: str) -> Path:
    directory = course / "Sequenzen"
    directory.mkdir(exist_ok=True)
    path = directory / f"{stem}.md"
    path.write_text(
        f'---\nKursplan: "[[k]]"\nSequenzname: "S"\nLerngruppe: "g"\nHalbjahr: "26-1"\n{body}---\n',
        encoding="utf-8",
    )
    return path


def test_reports_all_violations_of_a_file_not_only_the_first(tmp_path):
    course = _course(tmp_path)
    path = _lesson(
        course,
        "s1",
        'Kompetenzen:\n  - "ok"\n  - "K1; K2"\nMaterial:\n  - " Rand"\n  - "gut"\n  - ""\n',
    )

    findings = check_lesson_file(path)

    assert [(f.field, f.entry) for f in findings] == [
        ("Kompetenzen", "K1; K2"),
        ("Material", " Rand"),
        ("Material", ""),
    ]


def test_parser_keeps_empty_items_so_they_are_reported(tmp_path):
    """Regression: der Parser verwarf `- ""`/`- ` früher still, jetzt erreichen sie die Prüfung."""
    course = _course(tmp_path)
    path = _lesson(course, "s1", 'Material:\n  - ""\n  -\n')

    assert [(f.field, f.entry) for f in check_lesson_file(path)] == [("Material", ""), ("Material", "")]


def test_messages_are_identical_to_runtime_errors(tmp_path):
    """Gleiche Regelquelle: Tool-Erklärung == Erklärung der Laufzeit-Exception."""
    course = _course(tmp_path)
    path = _lesson(course, "s1", 'Material:\n  - "a;b"\n')

    [finding] = check_lesson_file(path)
    data, _ = parse_yaml_frontmatter(path.read_text(encoding="utf-8"), LESSON_SCHEMA)
    with pytest.raises(ListFieldViolationError) as info:
        canonicalize_lesson_yaml(data, source_label=str(path))

    assert finding.reason == info.value.reason


def test_ignores_list_fields_the_lesson_type_does_not_use(tmp_path):
    course = _course(tmp_path)
    path = course / "Einheiten" / "a1.md"
    path.write_text(
        '---\nStundentyp: Ausfall\nDauer: 2\nStundenthema: X\nMaterial:\n  - "a;b"\n---\n', encoding="utf-8"
    )

    assert check_lesson_file(path) == []


def test_sequence_focus_competencies_must_be_a_list(tmp_path):
    course = _course(tmp_path)
    scalar = _sequence(course, "s-scalar", 'Leitkompetenzen: "Modellieren"\n')
    bad_entry = _sequence(course, "s-bad", 'Leitkompetenzen:\n  - "A; B"\n')
    ok = _sequence(course, "s-ok", 'Leitkompetenzen:\n  - "Modellieren"\n')

    findings = scan(tmp_path, include_archive=False)

    paths = [f.path for f in findings]
    assert scalar in paths and bad_entry in paths and ok not in paths


def test_unreadable_file_is_reported(tmp_path):
    course = _course(tmp_path)
    broken = course / "Einheiten" / "kaputt.md"
    broken.write_text("kein Frontmatter", encoding="utf-8")

    findings = scan(tmp_path, include_archive=False)

    assert len(findings) == 1
    assert findings[0].field == ""
    assert "nicht lesbar" in findings[0].reason


def test_main_exit_codes(tmp_path, capsys):
    course = _course(tmp_path)
    _lesson(course, "ok", 'Material:\n  - "AB"\n')
    assert main(["--unterricht-dir", str(tmp_path), "--no-archive"]) == 0

    _lesson(course, "bad", 'Material:\n  - "a;b"\n')
    assert main(["--unterricht-dir", str(tmp_path), "--no-archive"]) == 1
    assert "a;b" in capsys.readouterr().out


def test_tool_never_writes(tmp_path):
    course = _course(tmp_path)
    path = _lesson(course, "bad", 'Material:\n  - "a;b"\n')
    before = path.read_bytes()

    main(["--unterricht-dir", str(tmp_path), "--no-archive"])

    assert path.read_bytes() == before
