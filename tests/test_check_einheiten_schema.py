"""CI-Schema-Check für Einheiten: Regeln kommen aus dem Code, geprüft an synthetischen Ordnern."""

from __future__ import annotations

from pathlib import Path

from tools.ci.check_einheiten_schema import check_lesson_files, lesson_files_under, main

_VALID = '---\nStundentyp: Unterricht\nDauer: 2\nStundenthema: ""\nSonderziele:\n---\n'


def _unit(root: Path, name: str, text: str = _VALID, folder: str = "Einheiten") -> Path:
    path = root / "Kurs" / folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_units_pass_including_empty_topic_and_ebw(tmp_path):
    _unit(tmp_path, "ab12cd.md")
    _unit(tmp_path, "cd34ef.ebw", _VALID.replace("---\n", "---\ndocument_type: kurzentwurf\n", 1))
    _unit(tmp_path, "ef56gh.md", folder="Alteinheiten")
    (tmp_path / "Kurs" / "Notiz.md").write_text("kein Einheitenordner", encoding="utf-8")

    files = lesson_files_under(tmp_path)

    assert len(files) == 3
    assert check_lesson_files(files) == []
    assert main([str(tmp_path)]) == 0


def test_violations_are_reported(tmp_path):
    bad_name = _unit(tmp_path, "Brüche 2.md")
    unknown_key = _unit(tmp_path, "ab12cd.md", _VALID.replace("Dauer: 2\n", "Dauer: 2\nErfunden: x\n"))
    no_dauer = _unit(tmp_path, "cd34ef.md", _VALID.replace("Dauer: 2\n", ""))
    bad_type = _unit(tmp_path, "ef56gh.md", _VALID.replace("Unterricht", "Exkursion"))

    errors = "\n".join(check_lesson_files(lesson_files_under(tmp_path)))

    assert f"Ungültiger Dateiname: {bad_name}" in errors
    assert f"Unerlaubtes YAML-Feld 'Erfunden' in {unknown_key}" in errors
    assert "Dauer" in errors and str(no_dauer) in errors
    assert "Stundentyp" in errors and str(bad_type) in errors
    assert main([str(tmp_path)]) == 1


def test_missing_root_skips(tmp_path):
    assert main([str(tmp_path / "fehlt")]) == 0
