"""Tests für das einmalige Migrationstool ``Leitkompetenz`` → ``Leitkompetenzen`` (synthetische Daten)."""

from pathlib import Path

import pytest

from kursplaner.core.domain.yaml_registry import SEQUENCE_PLAN_SCHEMA, parse_yaml_frontmatter
from tools.migrate_sequence_focus_competencies import (
    CONFLICT,
    MIGRATED,
    SKIPPED_ALREADY,
    SKIPPED_NOT_AFFECTED,
    main,
    migrate_file,
    migrate_text,
)

_HEAD = 'Kursplan: "[[k]]"\nSequenzname: "S"\nLerngruppe: "g"\nHalbjahr: "26-1"\nSequenzziel: "Ziel"\n'
_BODY = "\n# Titel\n\n## Brainstorming\n\nIdee\n\n## Export\n\n| a | b |\n| --- | --- |\n"


def _doc(fm_tail: str) -> str:
    return f"---\n{_HEAD}{fm_tail}---\n{_BODY}"


def _write(tmp_path: Path, text: str, *, raw: bytes | None = None, name: str = "s.md") -> Path:
    path = tmp_path / name
    path.write_bytes(raw if raw is not None else text.encode("utf-8"))
    return path


def _focus(text: str) -> object:
    data, _ = parse_yaml_frontmatter(text, SEQUENCE_PLAN_SCHEMA)
    return data["Leitkompetenzen"]


@pytest.mark.parametrize(
    "old, expected",
    [
        ('Leitkompetenz: "Modellieren, Argumentieren"\n', ["Modellieren, Argumentieren"]),
        ("Leitkompetenz: Modellieren\n", ["Modellieren"]),
        ('Leitkompetenz: ""\n', []),
        ("Leitkompetenz:\n", []),
        ('Leitkompetenz:\n  - "Modellieren"\n  - "Argumentieren"\n', ["Modellieren", "Argumentieren"]),
        ('Leitkompetenz :  "Modellieren"   \n', ["Modellieren"]),
        ('Leitkompetenz: "Thema \\"A\\""\n', None),  # Backslash → Konflikt (siehe eigener Test)
    ],
)
def test_supported_old_values(old, expected):
    result, new_text = migrate_text(_doc(old))
    if expected is None:
        assert result.status == CONFLICT
        return
    assert result.status == MIGRATED
    assert _focus(new_text) == expected
    assert "Leitkompetenz:" not in new_text.replace("Leitkompetenzen:", "")


@pytest.mark.parametrize(
    "old",
    [
        "Leitkompetenz: true\n",
        "Leitkompetenz: 42\n",
        "Leitkompetenz: 1.5\n",
        "Leitkompetenz: 2024-01-01\n",
        "Leitkompetenz:\n  a: b\n",
        'Leitkompetenz:\n  - "ok"\n  - 3\n',
        'Leitkompetenz:\n  - "ok"\n  - ""\n',
        'Leitkompetenz:\n  - " x"\n',
        'Leitkompetenz:\n  - "x "\n',
        'Leitkompetenz: " x "\n',
        'Leitkompetenz: "A; B"\n',
        'Leitkompetenz: "a\\\\b"\n',
        'Leitkompetenz: "x"\nLeitkompetenz: "y"\n',
        'Leitkompetenz: "x"\nLeitkompetenz : "y"\n',
        'Leitkompetenzen:\n  - "x"\nLeitkompetenzen:\n  - "y"\n',
        'Leitkompetenz: "x"\nLeitkompetenzen:\n  - "y"\n',
        'Sequenzziel2:\n  Leitkompetenz: "x"\n',
        "Leitkompetenz: [unvollständig\n",
        # PyYAML lehnt einen Tab vor einem Wert ab → nicht raten, sondern melden.
        'Leitkompetenz:\t"Modellieren"\n',
        'Leitkompetenz: "Modellieren"\t\n',
    ],
)
def test_conflicts_leave_file_byte_identical(tmp_path, old):
    path = _write(tmp_path, _doc(old))
    before = path.read_bytes()
    mtime = path.stat().st_mtime_ns

    result = migrate_file(path, dry_run=False)

    assert result.status == CONFLICT, result
    assert result.detail
    assert path.read_bytes() == before
    assert path.stat().st_mtime_ns == mtime


def test_already_migrated_is_skipped(tmp_path):
    path = _write(tmp_path, _doc('Leitkompetenzen:\n  - "Modellieren"\n'))
    before = path.read_bytes()

    assert migrate_file(path, dry_run=False).status == SKIPPED_ALREADY
    assert path.read_bytes() == before


def test_neither_key_is_skipped_and_nothing_inserted(tmp_path):
    path = _write(tmp_path, _doc(""))
    before = path.read_bytes()

    assert migrate_file(path, dry_run=False).status == SKIPPED_NOT_AFFECTED
    assert path.read_bytes() == before


def test_migration_is_idempotent(tmp_path):
    path = _write(tmp_path, _doc('Leitkompetenz: "Modellieren"\n'))

    assert migrate_file(path, dry_run=False).status == MIGRATED
    once = path.read_bytes()
    assert migrate_file(path, dry_run=False).status == SKIPPED_ALREADY
    assert path.read_bytes() == once


def test_dry_run_does_not_write(tmp_path):
    path = _write(tmp_path, _doc('Leitkompetenz: "Modellieren"\n'))
    before = path.read_bytes()

    assert migrate_file(path, dry_run=True).status == MIGRATED
    assert path.read_bytes() == before


def test_body_and_other_lines_stay_byte_identical_with_crlf_and_bom(tmp_path):
    text = _doc('Leitkompetenz: "Modellieren"\nZusatz: "bleibt"\n').replace("\n", "\r\n")
    path = _write(tmp_path, text, raw=b"\xef\xbb\xbf" + text.encode("utf-8"))

    assert migrate_file(path, dry_run=False).status == MIGRATED

    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    new_text = raw[3:].decode("utf-8")
    assert "\n" not in new_text.replace("\r\n", "")
    expected = text.replace('Leitkompetenz: "Modellieren"', 'Leitkompetenzen:\r\n  - "Modellieren"')
    assert new_text == expected


def test_quote_in_entry_roundtrips_through_project_parser():
    result, new_text = migrate_text(_doc("Leitkompetenz: 'Thema \"A\"'\n"))

    assert result.status == MIGRATED
    assert _focus(new_text) == ['Thema "A"']


def test_main_reports_summary_and_exit_codes(tmp_path, capsys):
    course = tmp_path / "Kurs"
    (course / "Sequenzen").mkdir(parents=True)
    (course / "Kurs.md").write_text("---\nx: y\n---\n", encoding="utf-8")
    ok = _write(course / "Sequenzen", _doc('Leitkompetenz: "M"\n'), name="a.md")
    _write(course / "Sequenzen", _doc(""), name="b.md")

    assert main(["--unterricht-dir", str(tmp_path), "--no-archive"]) == 0
    out = capsys.readouterr().out
    assert "1 migriert" in out and "1 nicht betroffen" in out
    assert _focus(ok.read_text(encoding="utf-8")) == ["M"]

    _write(course / "Sequenzen", _doc("Leitkompetenz: 42\n"), name="c.md")
    assert main(["--unterricht-dir", str(tmp_path), "--no-archive"]) == 1
